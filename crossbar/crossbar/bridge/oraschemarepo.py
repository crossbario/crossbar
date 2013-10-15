###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


__all__ = ["getSchemaVersion",
           "setupSchema",
           "reinstallSchema",
           "dropSchema",
           "upgradeSchema"]

import os
import pkg_resources

from twisted.python import log

from autobahn.util import utcnow
from autobahn.wamp import json_dumps

import dbschema
import oraschema


SCHEMAVERSION = 3


def getSchemaVersion(app, conn):
   return dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)


def _getPLJSONDDL(oracleMajorVersion, uninstallOnly = False):
   """
   Install PL/JSON from static files.

   Returns a list of 3-tuples (filename, blocknumber, sql), where there sql
   contains single SQL statements to be executed in list order.
   """
   ## root path to PL/JSON files from installed package
   root = pkg_resources.resource_filename("crossbar", "ddl/oracle/pljson")

   ## main install script. we parse this to get the list of individual files
   installfile = os.path.join(root, 'install.sql')

   installfiles = []

   if False:
      ## determine install files from parsing "install.sql"
      ##
      if uninstallOnly:
         files = ['uninstall.sql']
      else:
         files = ['uninstall.sql']
         for l in open(installfile).read().splitlines():
            if l.startswith('@@') and (not uninstallOnly or l.startswith('@@uninstall.sql')):
               i = l.find('--')
               if i > 0:
                  s = l[2:i]
               else:
                  s = l[2:]
               files.append(s.strip())
   else:
      ## manually create list of install files
      ##
      if uninstallOnly:
         files = ['uninstall.sql']
      else:
         files = ['uninstall.sql']
         files.extend(['json_value.sql',
                       'json_list.sql',
                       'json.sql',
                       'json_parser.sql',
                       'json_printer.sql',
                       'json_value_body.sql',
                       'json_ext.sql',
                       'json_body.sql',
                       'json_list_body.sql',
                       'json_ac.sql'])

         if oracleMajorVersion >= 11:
            files.append('addons/json_dyn_11g.sql')
         else:
            files.append('addons/json_dyn.sql')

         files.extend([#'addons/jsonml.sql',
                       #'addons/json_xml.sql',
                       #'addons/json_util_pkg.sql',
                       'addons/json_helper.sql'])

   for f in files:
      installfiles.append(os.path.join(root, f))

   tsql = []

   ## we need to split install files contents into individual SQL
   ## statements and clean away any SQLplus related stuff
   for fn in installfiles:
      try:
         f = open(fn, "rb")
         fc = f.read()
         block = 1
         sql = []
         for l in fc.splitlines():
            if l.startswith("sho") or l.startswith("set"):
               pass
            elif l.startswith("/") and l.strip() == "/":
               s = '\n'.join(sql).strip()
               sql = []
               if len(s) > 0:
                  tsql.append((fn, block, s))
                  block += 1
            else:
               sql.append(l)
      except Exception, e:
         em = "Error while processing %s [%s]" % (fn, e)
         log.msg(em)
         raise Exception(em)

   return tsql



def _setupSchema(conn,
                 grantedusers = ['public'],
                 publicsyn = True,
                 uninstallOnly = False):
   """
   Setup crossbar.io Connect repository.

   :param conn: A connected cx_Oracle connection.
   :type conn: cx_Oracle.Connection
   :param grantedusers: List of user granted access to crossbar.io.
   :type grantedusers: List of str.
   :param publicsyn: Create public synonyms for crossbar.io objects.
   :type publicsyn: bool
   :returns dict -- Repository information.
   """

   log.msg("(Re-)creating crossbar.io database connect repository ...")

   import cx_Oracle
   cur = conn.cursor()

   ## Session User
   ##
   cur.execute("SELECT sys_context('USERENV', 'SESSION_USER') FROM dual")
   session_user = cur.fetchone()[0]

   ## Oracle Version
   ##
   cur.execute("SELECT version FROM product_component_version WHERE product LIKE 'Oracle%' AND rownum < 2")
   dbversion = cur.fetchone()[0]
   oracleMajorVersion = int(dbversion.split('.')[0])

   ## Set PL/SQL optimization level
   ##
   ## Note: Check via user_stored_settings / all_stored_settings:
   ##
   ## SELECT *
   ##   FROM all_stored_settings
   ##  WHERE     owner = 'crossbar'
   ##        AND param_name = 'plsql_optimize_level'
   ##        AND object_type LIKE '%BODY'
   ##
   if oracleMajorVersion >= 11:
      log.msg("Setting PL/SQL optimization level 3 + native")
      cur.execute("ALTER SESSION SET PLSQL_OPTIMIZE_LEVEL = 3")
      cur.execute("ALTER SESSION SET plsql_code_type = 'NATIVE'")
   else:
      log.msg("Setting PL/SQL optimization level 2")
      cur.execute("ALTER SESSION SET PLSQL_OPTIMIZE_LEVEL = 2")

   ## The maximum column size allowed is 4000 characters when the
   ## national character set is UTF8 and 2000 when it is AL16UTF16.
   ##
   cur.execute("SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_NCHAR_CHARACTERSET'")
   if cur.fetchone()[0] == 'AL16UTF16':
      nchar_maxlen = 2000
   else:
      nchar_maxlen = 4000

   log.msg("NCHAR MAXLEN = %d" % nchar_maxlen)

   ## (Re)install PL/JSON
   ##
   tsql = _getPLJSONDDL(oracleMajorVersion, uninstallOnly)
   for fn, block, t in tsql:
      try:
         log.msg("executing %s block %d .." % (fn, block))
         cur.execute(t)
      except Exception, e:
         m = "error installing %s block %d (%s)" % (fn, block, e)
         raise Exception(m)

   ## DBMS_PIPE based pipes
   ##
   ## Notes:
   ##   - pipe name are global for the instance
   ##   - v$db_pipes lists pipes, but needs extended privileges
   ##

   PIPE_ONPUBLISH = 'CROSSBAR_%s_ONPUBLISH' % session_user.upper()
   PIPE_ONEXPORT = 'CROSSBAR_%s_ONEXPORT' % session_user.upper()

   PLJSONOBJS = [# PL/JSON object types
                 'json',
                 'json_list',
                 'json_value',
                 'json_value_array',
                 # PL/JSON packages
                 'json_ext',
                 'json_parser',
                 'json_printer',
                 # addon packages
                 'json_ac',
                 'json_dyn',
                 'json_helper',
                 #'json_ml',
                 #'json_util_pkg',
                 #'json_xml',
                 ]

   PIPES = [PIPE_ONPUBLISH, PIPE_ONEXPORT]
   PACKAGES = ['crossbar']

   VIEWS = ['crossbar_event',
            'crossbar_endpoint']

   TABLES = ['config',
             'event',
             'endpoint']

   TYPES = ['crossbar_session',
            'crossbar_sessionids',
            'crossbar_authkeys',
            't_arg_types',
            't_arg_inouts']

   SEQUENCES = ['event_id',
                'endpoint_id']

   PUBSYNS = ['crossbar',
              'crossbar_event',
              'crossbar_endpoint',
              'crossbar_session',
              'crossbar_sessionids',
              'crossbar_authkeys']

   PUBSYNS.extend(PLJSONOBJS)

   USERGRANTS = [('EXECUTE', ['crossbar'] + TYPES + PLJSONOBJS),
                 ('SELECT', ['crossbar_event', 'crossbar_endpoint'])]

   if publicsyn or uninstallOnly:
      for o in PUBSYNS:
         try:
            cur.execute("""
                        BEGIN
                           EXECUTE IMMEDIATE 'DROP PUBLIC SYNONYM %s';
                        EXCEPTION
                           WHEN OTHERS THEN
                              IF SQLCODE != -1432 THEN
                                 RAISE;
                              END IF;
                        END;
                        """ % o)
            log.msg("public synonym '%s' dropped" % o)
         except:
            log.msg("warning: could not drop public synonym '%s'" % o)

   for p in PIPES:
      cur.execute("SELECT SYS.DBMS_PIPE.remove_pipe(pipename => :pipe) FROM dual", pipe = p)
      res = cur.fetchone()[0]
      if res != 0:
         raise Exception("could not remove pipe '%s' [%d]" % (p, res))
      else:
         log.msg("pipe %s removed" % p)

   for o in PACKAGES:
      cur.execute("""
                  BEGIN
                     EXECUTE IMMEDIATE 'DROP PACKAGE %s';
                  EXCEPTION
                     WHEN OTHERS THEN
                        IF SQLCODE != -4043 THEN
                           RAISE;
                        END IF;
                  END;
                  """ % o)
      log.msg("database package '%s' dropped" % o)

   for o in VIEWS:
      cur.execute("""
                  BEGIN
                     EXECUTE IMMEDIATE 'DROP VIEW %s';
                  EXCEPTION
                     WHEN OTHERS THEN
                        IF SQLCODE != -942 THEN
                           RAISE;
                        END IF;
                  END;
                  """ % o)
      log.msg("database view '%s' dropped" % o)

   for o in TABLES:
      cur.execute("""
                  BEGIN
                     EXECUTE IMMEDIATE 'DROP TABLE %s';
                  EXCEPTION
                     WHEN OTHERS THEN
                        IF SQLCODE != -942 THEN
                           RAISE;
                        END IF;
                  END;
                  """ % o)
      log.msg("database table '%s' dropped" % o)

   for o in SEQUENCES:
      cur.execute("""
                  BEGIN
                     EXECUTE IMMEDIATE 'DROP SEQUENCE %s';
                  EXCEPTION
                     WHEN OTHERS THEN
                        IF SQLCODE != -2289 THEN
                           RAISE;
                        END IF;
                  END;
                  """ % o)
      log.msg("database sequence '%s' dropped" % o)

   for o in TYPES:
      cur.execute("""
                  BEGIN
                     EXECUTE IMMEDIATE 'DROP TYPE %s FORCE';
                  EXCEPTION
                     WHEN OTHERS THEN
                        IF SQLCODE != -4043 THEN
                           RAISE;
                        END IF;
                  END;
                  """ % o)
      log.msg("database type '%s' dropped" % o)


   ## setup repository schema
   ##
   if not uninstallOnly:
      ## create TYPEs
      ##
      cur.execute("""
                  CREATE TYPE crossbar_sessionids IS TABLE OF VARCHAR2(16) NOT NULL
                  """)
      log.msg("database type '%s' created" % "crossbar_sessionids")

      cur.execute("""
                  CREATE TYPE crossbar_authkeys IS TABLE OF VARCHAR2(30)
                  """)
      log.msg("database type '%s' created" % "crossbar_authkeys")

      cur.execute("""
                  CREATE TYPE t_arg_types IS TABLE OF VARCHAR2(96)
                  """)
      log.msg("database type '%s' created" % "t_arg_types")

      cur.execute("""
                  CREATE TYPE t_arg_inouts IS TABLE OF VARCHAR2(9)
                  """)
      log.msg("database type '%s' created" % "t_arg_inouts")

      cur.execute("""
                  CREATE OR REPLACE TYPE crossbar_session AS OBJECT
                  (
                     sessionid   VARCHAR2(16),
                     authkey     VARCHAR2(30),
                     data        JSON
                  )
                  """)
      log.msg("database type '%s' created" % "crossbar_session")



      ## create SEQUENCEs
      ##
      for s in SEQUENCES:
         cur.execute("""
                     CREATE SEQUENCE %s
                     """ % s)
         log.msg("database sequence '%s' created" % s)


      ## CONFIG table
      ##
      cur.execute("""
                  CREATE TABLE config
                  (
                     key                 VARCHAR2(30)                     PRIMARY KEY,
                     value               VARCHAR2(4000)                   NOT NULL
                  )
                  """)
      log.msg("database table '%s' created" % "config")


      ## ENDPOINT table
      ##
      cur.execute("""
                  CREATE TABLE endpoint
                  (
                     id                  NUMBER(38)                       PRIMARY KEY,
                     created_at          TIMESTAMP                        NOT NULL,
                     created_by          VARCHAR2(30)                     NOT NULL,
                     modified_at         TIMESTAMP,
                     schema              VARCHAR2(30)                     NOT NULL,
                     package             VARCHAR2(30)                     NOT NULL,
                     procedure           VARCHAR2(30)                     NOT NULL,
                     object_id           NUMBER                           NOT NULL,
                     subprogram_id       NUMBER                           NOT NULL,
                     return_type         VARCHAR2(30),
                     args_cnt            NUMBER                           NOT NULL,
                     arg_types           t_arg_types,
                     arg_inouts          t_arg_inouts,
                     uri                 NVARCHAR2(%(nchar_maxlen)d)      NOT NULL,
                     authkeys            crossbar_authkeys
                  )
                  NESTED TABLE authkeys   STORE AS endpoint_authkeys
                  NESTED TABLE arg_types  STORE AS endpoint_arg_types
                  NESTED TABLE arg_inouts STORE AS endpoint_arg_inouts
                  """ % {'nchar_maxlen': nchar_maxlen})
      log.msg("database table '%s' created" % "endpoint")

      cur.execute("""
                  CREATE UNIQUE INDEX idx_endpoint1 ON endpoint (uri)
                  """)


      ## EVENT table
      ##
      cur.execute("""
                  CREATE TABLE event
                  (
                     id                  NUMBER(38)                       PRIMARY KEY,
                     published_at        TIMESTAMP                        NOT NULL,
                     published_by        VARCHAR2(30)                     NOT NULL,
                     processed_at        TIMESTAMP,
                     processed_status    INT,
                     processed_len       NUMBER(38),
                     processed_errmsg    VARCHAR2(4000),
                     dispatch_status     INT,
                     dispatch_success    NUMBER(38),
                     dispatch_failed     NUMBER(38),
                     topic               NVARCHAR2(%(nchar_maxlen)d)      NOT NULL,
                     qos                 INT                              NOT NULL,
                     payload_type        INT                              NOT NULL,
                     payload_str         NVARCHAR2(%(nchar_maxlen)d),
                     payload_lob         NCLOB,
                     exclude_sids        crossbar_sessionids,
                     eligible_sids       crossbar_sessionids
                  )
                  NESTED TABLE exclude_sids  STORE AS event_exclude_sids
                  NESTED TABLE eligible_sids STORE AS event_eligible_sids
                  """ % {'nchar_maxlen': nchar_maxlen})

      cur.execute("""
                  ALTER TABLE event ADD CONSTRAINT cstr_event_payload_type CHECK (payload_type IN (1, 2)) ENABLE
                  """)

      cur.execute("""
                  ALTER TABLE event ADD CONSTRAINT cstr_event_qos CHECK (qos IN (1)) ENABLE
                  """)

      cur.execute("""
                  ALTER TABLE event ADD CONSTRAINT cstr_event_processed_status CHECK (processed_status IN (0, 1, 2, 3, 4, 5)) ENABLE
                  """)

      cur.execute("""
                  ALTER TABLE event ADD CONSTRAINT cstr_event_dispatch_status CHECK (dispatch_status IN (0, 1)) ENABLE
                  """)

      cur.execute("""
                  CREATE INDEX idx_event1 ON event (published_by, published_at)
                  """)

      log.msg("database table '%s' created" % "event")


      ## views
      ##
      cur.execute("""
                  CREATE VIEW crossbar_event
                  AS
                  SELECT * FROM event
                  WHERE published_by = sys_context('USERENV', 'SESSION_USER')
                  """)
      log.msg("database view '%s' created" % "crossbar_event")

      cur.execute("""
                  CREATE VIEW crossbar_endpoint
                  AS
                  SELECT * FROM endpoint
                  WHERE created_by = sys_context('USERENV', 'SESSION_USER')
                  """)
      log.msg("database view '%s' created" % "crossbar_endpoint")


      ## pipes
      ##
      for p in PIPES:
         res = cur.callfunc("SYS.DBMS_PIPE.create_pipe", cx_Oracle.NUMBER, [], {'pipename': p, 'private': True, 'maxpipesize': 64 * 8192})
         if res != 0:
            raise Exception("could not create pipe '%s' [%d]" % (p, res))
         else:
            log.msg("pipe %s created" % p)


      ## packages
      ##
      cur.execute("""
CREATE OR REPLACE PACKAGE crossbar
AS
   /**
    * crossbar.io Oracle PL/SQL API.
    *
    * Copyright (C) 2011-2013 Tavendo GmbH.
    * Licensed under Apache 2.0 license (http://www.apache.org/licenses/LICENSE-2.0.html)
    *
    * Publish & Subscribe:
    *
    *   The package provides functions to publish events to crossbar.io from within
    *   Oracle which are dispatched to any clients subscribed and authorized
    *   to receive events on the respective topic.
    *
    * Remote Procedure Calls:
    *
    *   The package provides functions to export Oracle stored procedures which
    *   then can be called by clients authorized to do so. crossbar.io will forward
    *   client calls to stored procedure invocations.
    */

   /**
    * Event payload type is plain string.
    */
   PAYLOAD_TYPE_STRING   CONSTANT INTEGER := 1;

   /**
    * Event payload type is JSON.
    */
   PAYLOAD_TYPE_JSON     CONSTANT INTEGER := 2;

   /**
    * Event delivery quality-of-service is "best-effort".
    *
    * Any subscriber currently subscribed on the topic the event was
    * published to SHOULD receive the event once. However, there is
    * no strict guarantee for this to happen: the event may be delivered
    * once, more than once, or get lost completely.
    */
   QOS_BEST_EFFORT       CONSTANT INTEGER := 1;


   /**
    * crossbar.io repository user.
    */
   REPOUSER              CONSTANT VARCHAR2(30) := sys_context('USERENV', 'CURRENT_SCHEMA');


   /**
    * Publish event without payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event without payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with plain string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN NVARCHAR2,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with plain string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN NVARCHAR2,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with large string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN NCLOB,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with large string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN NCLOB,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (value) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON_VALUE,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (value) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON_VALUE,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (object) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (object) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (list) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON_LIST,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (list) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON_LIST,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Export a stored procedure or function for RPC.
    *
    * You may export a given stored procedure under different endpoint URIs,
    * but there can only be at most one export per given URI.
    *
    * @param p_schema           Schema (owner) of stored procedure to be exported.
    * @param p_package          Package containing stored procedure to be exported.
    * @param p_proc             Procedure within package to be exported.
    * @param p_uri              URI under which the endpoint will be reachable via WAMP RPC.
    * @param p_authkeys         List of authentication keys that may access this endpoint.
    * @return                   Endpoint ID.
    */
   FUNCTION export(p_schema    IN VARCHAR2,
                   p_package   IN VARCHAR2,
                   p_proc      IN VARCHAR2,
                   p_endpoint  IN NVARCHAR2,
                   p_authkeys  IN crossbar_authkeys      DEFAULT NULL) RETURN NUMBER;


   /**
    * Export a stored procedure or function for RPC.
    *
    * Convenience shortcut procedure.
    */
   PROCEDURE export(p_package   IN VARCHAR2,
                    p_proc      IN VARCHAR2,
                    p_endpoint  IN NVARCHAR2,
                    p_authkeys  IN crossbar_authkeys      DEFAULT NULL);

   /**
    * Delete existing RPC export of a stored procedure. To delete an export,
    * you need to be the owner (= original creator) of the exported endpoint.
    *
    * @param p_endpoint_id     ID of endpoint as returned from creating the export.
    */
   PROCEDURE remove_export(p_endpoint_id   IN NUMBER);

   /**
    * Delete all existing RPC exports for the given schema/package/procedure.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_schema          Schema name of exported procedures to delete or NULL for current schema.
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    * @return                  Number of exported endpoints deleted.
    */
   FUNCTION remove_exports(p_schema    IN VARCHAR2,
                           p_package   IN VARCHAR2,
                           p_proc      IN VARCHAR2) RETURN NUMBER;

   /**
    * Delete all existing RPC exports for the given schema/package/procedure.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_schema          Schema name of exported procedures to delete or NULL for current schema.
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    */
   PROCEDURE remove_exports(p_schema    IN VARCHAR2,
                            p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2 DEFAULT NULL);

   /**
    * Delete all existing RPC exports for the given package/procedure within the current schema.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    */
   PROCEDURE remove_exports(p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2 DEFAULT NULL);

   /**
    * Delete all existing RPC exports for stored procedures exported
    * under given URI pattern. The pattern is applied via a WHERE .. LIKE ..
    * expression. You must be owner (= original creator) of _all_ exported
    * endpoints for this to succeed.
    *
    * @param p_uri             URI of exported endpoints to delete.
    * @return                  Number of exported endpoints deleted.
    */
   FUNCTION remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2) RETURN NUMBER;

   /**
    * Delete all existing RPC exports for stored procedures exported
    * under given URI pattern. The pattern is applied via a WHERE .. LIKE ..
    * expression. You must be owner (= original creator) of _all_ exported
    * endpoints for this to succeed.
    *
    * @param p_uri             URI of exported endpoints to delete.
    */
   PROCEDURE remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON_VALUE,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON_LIST,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

END crossbar;""")

      cur.execute("""
CREATE OR REPLACE PACKAGE BODY crossbar
AS
   FUNCTION dopublish(p_topic         NVARCHAR2,
                      p_payload_type  INTEGER,
                      p_payload_str   NVARCHAR2,
                      p_payload_lob   NCLOB,
                      p_exclude       crossbar_sessionids,
                      p_eligible      crossbar_sessionids,
                      p_qos           INTEGER) RETURN NUMBER
   AS
      l_now    TIMESTAMP;
      l_user   VARCHAR2(30);
      l_id     NUMBER(38);
      l_status NUMBER;
   BEGIN
      --
      -- check args
      --
      IF p_qos NOT IN (QOS_BEST_EFFORT) THEN
         RAISE_APPLICATION_ERROR(-20001, 'illegal QoS mode ' || p_qos);
      END IF;

      --
      -- event metadata
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER'),
             event_id.nextval
         INTO
             l_now,
             l_user,
             l_id
         FROM dual;

      -- persist event
      --
      INSERT INTO event (id, published_at, published_by, topic, qos, payload_type, payload_str, payload_lob, exclude_sids, eligible_sids)
         VALUES
            (l_id, l_now, l_user, p_topic, p_qos, p_payload_type, p_payload_str, p_payload_lob, p_exclude, p_eligible);

      -- notify pipe
      --
      DBMS_PIPE.pack_message(l_id);
      l_status := DBMS_PIPE.send_message('%(PIPE_ONPUBLISH)s');

      -- commit and return event ID on success
      --
      IF l_status != 0 THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20001, 'could not pipe event');
      ELSE
         COMMIT;
         RETURN l_id;
      END IF;
   END dopublish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, NULL, NULL, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    NVARCHAR2,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, p_payload, NULL, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    NVARCHAR2,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    NCLOB,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, NULL, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    NCLOB,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON_VALUE,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON_VALUE,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON_LIST,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON_LIST,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE remove_export(p_endpoint_id   IN NUMBER)
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;
   BEGIN
      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      BEGIN
         SELECT created_by INTO l_created_by FROM endpoint WHERE id = p_endpoint_id;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no endpoint with ID ' || p_endpoint_id);
      END;

      IF l_created_by != l_user THEN
         RAISE_APPLICATION_ERROR(-20001, 'not allowed to delete export with ID ' || p_endpoint_id || ' (not owner)');
      END IF;

      DELETE FROM endpoint WHERE id = p_endpoint_id;
      COMMIT;

      -- notify pipe
      --
      DBMS_PIPE.pack_message(p_endpoint_id);
      l_status := DBMS_PIPE.send_message('%(PIPE_ONEXPORT)s');

   END remove_export;


   FUNCTION remove_exports(p_schema    IN VARCHAR2,
                           p_package   IN VARCHAR2,
                           p_proc      IN VARCHAR2) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_cnt              NUMBER;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;

      l_schema           VARCHAR2(30);
      l_package          VARCHAR2(30);
      l_proc             VARCHAR2(30);
   BEGIN
      --
      -- determine schema of remoted package procedure
      --
      IF p_schema IS NOT NULL THEN
         l_schema := UPPER(SUBSTR(p_schema, 1, 30));
      ELSE
         l_schema := sys_context('USERENV', 'SESSION_USER');
      END IF;

      IF p_package IS NOT NULL THEN
         l_package := UPPER(SUBSTR(p_package, 1, 30));
      ELSE
         l_package := NULL;
      END IF;

      IF p_proc IS NOT NULL THEN
         l_proc := UPPER(SUBSTR(p_proc, 1, 30));
      ELSE
         l_proc := NULL;
      END IF;

      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      SELECT COUNT(*) INTO l_cnt FROM endpoint e
         WHERE
            schema = l_schema AND
            package = NVL(l_package, e.package) AND
            procedure = NVL(l_proc, e.procedure) AND
            created_by != l_user;

      IF l_cnt > 0 THEN
         RAISE_APPLICATION_ERROR(-20001, 'cannot delete exports - ' || l_cnt || ' exported endpoint(s) not owned by current user');
      END IF;

      l_cnt := 0;
      FOR r IN (SELECT id FROM endpoint e
                   WHERE
                      schema = l_schema AND
                      package = NVL(l_package, e.package) AND
                      procedure = NVL(l_proc, e.procedure) AND
                      created_by = l_user)
      LOOP
         DELETE FROM endpoint WHERE id = r.id;
         COMMIT;
         DBMS_PIPE.pack_message(r.id);
         l_status := DBMS_PIPE.send_message('%(PIPE_ONEXPORT)s');
         l_cnt := l_cnt + 1;
      END LOOP;

      RETURN l_cnt;

   END remove_exports;


   PROCEDURE remove_exports(p_schema    IN VARCHAR2,
                            p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports(p_schema, p_package, p_proc);
   END remove_exports;


   PROCEDURE remove_exports(p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports(NULL, p_package, p_proc);
   END remove_exports;


   FUNCTION remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_cnt              NUMBER;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;
   BEGIN
      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      SELECT COUNT(*) INTO l_cnt FROM endpoint WHERE uri LIKE p_uri_pattern AND created_by != l_user;
      IF l_cnt > 0 THEN
         RAISE_APPLICATION_ERROR(-20001, 'cannot delete exports - ' || l_cnt || ' exported endpoint(s) not owned by current user');
      END IF;

      l_cnt := 0;
      FOR r IN (SELECT id FROM endpoint WHERE uri LIKE p_uri_pattern AND created_by = l_user)
      LOOP
         DELETE FROM endpoint WHERE id = r.id;
         COMMIT;
         DBMS_PIPE.pack_message(r.id);
         l_status := DBMS_PIPE.send_message('%(PIPE_ONEXPORT)s');
         l_cnt := l_cnt + 1;
      END LOOP;

      RETURN l_cnt;

   END remove_exports_by_uri;


   PROCEDURE remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports_by_uri(p_uri_pattern);
   END remove_exports_by_uri;


   FUNCTION export (p_schema      VARCHAR2,
                    p_package     VARCHAR2,
                    p_proc        VARCHAR2,
                    p_endpoint    NVARCHAR2,
                    p_authkeys    crossbar_authkeys) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_isnew            BOOLEAN := TRUE;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_authkeys         crossbar_authkeys;
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_object_id        NUMBER;
      l_subprogram_id    NUMBER;
      l_overload_cnt     NUMBER;
      l_sessobj_cnt      NUMBER;
      l_status           NUMBER;
      l_schema           VARCHAR2(30);
      l_package          VARCHAR2(30) := UPPER(p_package);
      l_proc             VARCHAR2(30) := UPPER(p_proc);

      -- existing metadata (for updating)
      l_cur_return_type  VARCHAR2(30);
      l_cur_args_cnt     NUMBER;
      l_cur_arg_types    t_arg_types;
      l_cur_arg_inouts   t_arg_inouts;

      -- new metadata
      l_return_type      VARCHAR2(30) := NULL;
      l_args_cnt         NUMBER := 0;
      l_arg_types        t_arg_types := t_arg_types();
      l_arg_inouts       t_arg_inouts := t_arg_inouts();
      l_data_type        VARCHAR2(30);
   BEGIN
      --
      -- determine schema of remoted package procedure
      --
      IF p_schema IS NULL THEN
         l_schema := sys_context('USERENV', 'SESSION_USER');
      ELSE
         l_schema := UPPER(p_schema);
      END IF;

      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      --
      -- check if package exists and if we have execute grants on it
      --
      BEGIN
         SELECT object_id INTO l_object_id FROM all_procedures
            WHERE owner = l_schema AND object_name = l_package AND object_type = 'PACKAGE' AND subprogram_id = 0;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no package ' || l_schema || '.' || l_package || ' or no execute grant on package');
      END;

      --
      -- check if package procedure/function exists
      --
      BEGIN
         SELECT MAX(subprogram_id), COUNT(*) INTO l_subprogram_id, l_overload_cnt FROM all_procedures
            WHERE owner = l_schema AND object_name = l_package AND procedure_name = l_proc AND object_type = 'PACKAGE' AND subprogram_id > 0
            GROUP BY owner, object_name, procedure_name;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no procedure or function ' || l_schema || '.' || l_package || '.' || l_proc);
      END;

      --
      -- check for overloaded SP
      --
      IF l_overload_cnt > 1 THEN
         RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' is overloaded [' || l_overload_cnt || ' overloads]');
      END IF;

      --
      -- check for SP with multiple session object parameters
      --
      SELECT COUNT(*) INTO l_sessobj_cnt
        FROM all_arguments
       WHERE     object_id = l_object_id
             AND subprogram_id = l_subprogram_id
             AND data_type = 'OBJECT'
             AND type_owner = 'PUBLIC'
             AND type_name = 'CROSSBAR_SESSION';
      IF l_sessobj_cnt > 1 THEN
         RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses more than 1 session object parameter [' || l_sessobj_cnt || ' session object parameters]');
      END IF;

      --
      -- check SP arguments
      --
      FOR r IN (SELECT position,
                       argument_name,
                       data_type,
                       type_owner,
                       type_name,
                       defaulted,
                       in_out FROM all_arguments
                 WHERE object_id = l_object_id AND
                       subprogram_id = l_subprogram_id
              ORDER BY position ASC)
      LOOP
         --
         -- check for stuff we (currently) don't supports
         --
         IF r.position = 0 AND r.in_out != 'OUT' THEN
            -- should not happen anyway (it seems that functions are the only items having arg (= return value) in position 0)
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses IN/INOUT parameter in position 0');
         END IF;
         IF r.position > 0 AND r.in_out != 'IN' THEN
            IF r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name = 'CROSSBAR_SESSION' THEN
               -- session info is the only parameter type allowed to be IN or IN/OUT (but not OUT)
               IF r.in_out NOT IN ('IN', 'IN/OUT') THEN
                  RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses session object parameter of OUT (only IN or IN/OUT allowed)');
               END IF;
            ELSE
               RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses OUT/INOUT parameters');
            END IF;
         END IF;
         IF r.defaulted != 'N' THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses parameters defaults');
         END IF;
         IF r.position = 0 AND
            r.data_type != 'NUMBER' AND
            r.data_type != 'VARCHAR2' AND
            r.data_type != 'NVARCHAR2' AND
            r.data_type != 'CHAR' AND
            r.data_type != 'NCHAR' AND
            r.data_type != 'BINARY_FLOAT' AND
            r.data_type != 'BINARY_DOUBLE' AND
            r.data_type != 'DATE' AND
            r.data_type != 'TIMESTAMP' AND
            r.data_type != 'TIMESTAMP WITH TIME ZONE' AND
            r.data_type != 'TIMESTAMP WITH LOCAL TIME ZONE' AND
            r.data_type != 'INTERVAL DAY TO SECOND' AND
            --r.data_type != 'INTERVAL YEAR TO MONTH' AND
            NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('JSON', 'JSON_VALUE', 'JSON_LIST')) AND
            r.data_type != 'REF CURSOR'
            THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses unsupported return type');
         END IF;
         IF r.position > 0 AND
            r.data_type != 'NUMBER' AND
            r.data_type != 'VARCHAR2' AND
            r.data_type != 'NVARCHAR2' AND
            r.data_type != 'CHAR' AND
            r.data_type != 'NCHAR' AND
            r.data_type != 'BINARY_FLOAT' AND
            r.data_type != 'BINARY_DOUBLE' AND
            r.data_type != 'DATE' AND
            r.data_type != 'TIMESTAMP' AND
            r.data_type != 'TIMESTAMP WITH TIME ZONE' AND
            r.data_type != 'TIMESTAMP WITH LOCAL TIME ZONE' AND
            r.data_type != 'INTERVAL DAY TO SECOND' AND
            --r.data_type != 'INTERVAL YEAR TO MONTH' AND
            NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION', 'JSON', 'JSON_VALUE', 'JSON_LIST'))
            THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses unsupported parameter type');
         END IF;

         --
         -- remember return type (if a function) and number of (IN) args
         --
         IF r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION', 'JSON', 'JSON_VALUE', 'JSON_LIST') THEN
            l_data_type := r.type_name;
         ELSE
            l_data_type := r.data_type;
         END IF;

         --
         -- remember arg types
         --
         IF r.position = 0 THEN
            l_return_type := l_data_type;
         ELSE
            -- don't count injected args
            --
            IF NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION')) THEN
               l_args_cnt := l_args_cnt + 1;
            END IF;

            IF l_data_type IS NOT NULL THEN
               l_arg_types.extend(1);
               l_arg_types(l_arg_types.last) := l_data_type;
               l_arg_inouts.extend(1);
               l_arg_inouts(l_arg_inouts.last) := r.in_out;
            END IF;
         END IF;
      END LOOP;

      BEGIN
         SELECT id, created_by, authkeys, return_type, args_cnt, arg_types, arg_inouts INTO l_id, l_created_by, l_authkeys, l_cur_return_type, l_cur_args_cnt, l_cur_arg_types, l_cur_arg_inouts FROM endpoint
            WHERE schema = l_schema AND package = l_package AND procedure = l_proc AND uri = p_endpoint;

         IF l_created_by != l_user THEN
            RAISE_APPLICATION_ERROR(-20001, 'endpoint already exists, but was created by different user: not allowed to modify endpoint');
         END IF;

         l_isnew := FALSE;

         IF l_authkeys != p_authkeys OR
            (l_authkeys IS NULL     AND p_authkeys IS NOT NULL) OR
            (l_authkeys IS NOT NULL AND p_authkeys IS NULL) OR
            l_cur_return_type != l_return_type OR
            (l_cur_return_type IS NULL     AND l_return_type IS NOT NULL) OR
            (l_cur_return_type IS NOT NULL AND l_return_type IS NULL) OR
            l_cur_args_cnt != l_args_cnt OR
            l_arg_types != l_cur_arg_types OR
            (l_arg_types IS NULL     AND l_cur_arg_types IS NOT NULL) OR
            (l_arg_types IS NOT NULL AND l_cur_arg_types IS NULL) OR
            l_arg_inouts != l_cur_arg_inouts OR
            (l_arg_inouts IS NULL     AND l_cur_arg_inouts IS NOT NULL) OR
            (l_arg_inouts IS NOT NULL AND l_cur_arg_inouts IS NULL)
            THEN

            UPDATE endpoint
               SET
                  modified_at = l_now,
                  authkeys    = p_authkeys,
                  return_type = l_return_type,
                  args_cnt    = l_args_cnt,
                  arg_types   = l_arg_types,
                  arg_inouts  = l_arg_inouts
               WHERE
                  id = l_id;
            COMMIT;

            -- notify via pipe
            --
            --DBMS_PIPE.pack_message(l_id);
            --l_status := DBMS_PIPE.send_message('%(PIPE_ONEXPORT)s');
         END IF;

      EXCEPTION WHEN NO_DATA_FOUND THEN

         SELECT endpoint_id.nextval INTO l_id FROM dual;

         INSERT INTO endpoint
            (id, created_at, created_by, schema, package, procedure, object_id, subprogram_id, return_type, args_cnt, arg_types, arg_inouts, uri, authkeys) VALUES
               (l_id, l_now, l_user, l_schema, l_package, l_proc, l_object_id, l_subprogram_id, l_return_type, l_args_cnt, l_arg_types, l_arg_inouts, p_endpoint, p_authkeys);
         COMMIT;

         -- notify via pipe
         --
         --DBMS_PIPE.pack_message(l_id);
         --l_status := DBMS_PIPE.send_message('%(PIPE_ONEXPORT)s');
      END;

      RETURN l_id;

   END export;


   PROCEDURE export(p_package   IN VARCHAR2,
                    p_proc      IN VARCHAR2,
                    p_endpoint  IN NVARCHAR2,
                    p_authkeys  IN crossbar_authkeys      DEFAULT NULL)
   IS
      l_id   NUMBER;
   BEGIN
      l_id := export(NULL, p_package, p_proc, p_endpoint, p_authkeys);
   END export;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON_VALUE, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON_LIST, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;

END crossbar;""" % {'PIPE_ONPUBLISH': PIPE_ONPUBLISH,
                 'PIPE_ONEXPORT': PIPE_ONEXPORT})

      log.msg("database package '%s' created" % "crossbar")


      ## public synonyms
      ##
      if publicsyn:
         for s in PUBSYNS:
            try:
               cur.execute("CREATE PUBLIC SYNONYM %s FOR %s" % (s, s))
               log.msg("public synonym '%s' created for '%s'" % (s, s))
            except:
               log.msg("warning: could not create public synonym '%s' for '%s'" % (s, s))


      ## public grants
      ##
      for grant, objects in USERGRANTS:
         for object in objects:
            for user in grantedusers:
               try:
                  cur.execute("GRANT %s ON %s TO %s" % (grant, object, user))
                  log.msg("granted %s on '%s' to '%s'" % (grant, object, user))
               except:
                  log.msg("warning: could not grant %s on '%s' to '%s'" % (grant, object, user))


      ## store database schema version
      ##
      created = utcnow()
      config = [('schema-category', 'repository'),
                ('schema-version', SCHEMAVERSION),
                ('schema-created', utcnow())]
      for key, value in config:
         cur.execute("INSERT INTO config (key, value) VALUES (:1, :2)", [key, json_dumps(value)])
      conn.commit()

      log.msg("crossbar.io Repository schema created (version %d)!" % SCHEMAVERSION)

   else:

      log.msg("crossbar.io Repository schema dropped!")

   return dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)


def setupSchema(app,
                conn,
                grantedusers = ['public'],
                publicsyn = True):
   """
   Setup crossbar.io Connect repository.

   :param conn: A connected cx_Oracle connection.
   :type conn: cx_Oracle.Connection
   :param grantedusers: List of user granted access to crossbar.io.
   :type grantedusers: List of str.
   :param publicsyn: Create public synonyms for crossbar.io objects.
   :type publicsyn: bool
   :returns dict -- Repository information.
   """
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is not None:
      raise Exception("crossbar.io Repository already installed")

   return _setupSchema(conn, grantedusers, publicsyn)


def reinstallSchema(app,
                    conn,
                    grantedusers = ['public'],
                    publicsyn = True):
   """
   Reinstall crossbar.io Connect repository.

   :param conn: A connected cx_Oracle connection.
   :type conn: cx_Oracle.Connection
   :param grantedusers: List of user granted access to crossbar.io.
   :type grantedusers: List of str.
   :param publicsyn: Create public synonyms for crossbar.io objects.
   :type publicsyn: bool
   :returns dict -- Repository information.
   """
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Repository not installed")

   return _setupSchema(conn, grantedusers, publicsyn)


def dropSchema(app, conn):
   """
   Drop crossbar.io repository.
   """
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Repository not installed")

   return _setupSchema(conn, uninstallOnly = True)


def upgradeSchema(app, conn):
   """
   Upgrades crossbar.io repository.
   """
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Repository not installed")

   if not r['schema-needs-upgrade']:
      raise Exception("crossbar.io Repository needs no upgrade")

   ## FIXME
   raise Exception("crossbar.io Repository upgrade not implemented")



if __name__ == '__main__':

   ## Test setup of PL/JSON
   ##
   tsql = _getPLJSONDDL()
   for fn, block, t in tsql:
      print fn, block, t

   import cx_Oracle

   dsn = cx_Oracle.makedsn("127.0.0.1", 1521, "orcl")
   conn = cx_Oracle.connect("crossbar", "secret", dsn, threaded = True)
   cur = conn.cursor()

   for fn, block, t in tsql:
      try:
         cur.execute(t)
      except Exception, e:
         print fn, block
         print t
         print e
         raise
