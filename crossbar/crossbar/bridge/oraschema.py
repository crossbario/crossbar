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


__all__ = ["getDatabaseInfo",
           "getCreateUsersScript",
           "getDropUsersScript",
           "LATESTVERSIONS"]

from twisted.python import log

import dbschema
import oraschemarepo
import oraschemademo

LATESTVERSIONS = {'repository': oraschemarepo.SCHEMAVERSION,
                  'demo': oraschemademo.SCHEMAVERSION}


def getDatabaseInfo(app, conn):
   """
   Get database information.
   """
   cur = conn.cursor()

   ## this information should be accessible by any user that can CONNECT
   ##
   cur.execute("""SELECT systimestamp AT TIME ZONE 'UTC',
                         (SELECT version FROM product_component_version WHERE product LIKE 'Oracle%' AND rownum < 2) AS product_version,
                         (SELECT * FROM v$version WHERE banner LIKE 'Oracle%' AND rownum < 2) AS product_version_str,
                         sys_context('USERENV', 'CURRENT_SCHEMA')
                  FROM dual""")

   rr = cur.fetchone()
   current_time = rr[0]
   version_str = str(rr[1]).strip()
   version = str(rr[2]).strip()
   current_schema = rr[3]

   ## the following seems to require "SELECT ANY DICTIONARY" grant
   ##
   try:
      cur.execute("SELECT startup_time FROM sys.v_$instance")
      rr = cur.fetchone()
      start_time = rr[0]
   except:
      start_time = None

   ## the following seems to require "SELECT ANY DICTIONARY" grant
   ##
   try:
      cur.execute("SELECT dbid FROM v$database")
      rr = cur.fetchone()
      sysuuid = str(rr[0]).strip()
   except:
      sysuuid = None

   dbinfo = {'current-schema': current_schema,
             # FIXME!!
             #'current-time': current_time,
             #'start-time': start_time,
             'current-time': None,
             'start-time': None,
             'version': version,
             'version-string': version_str,
             'uuid': sysuuid}

   schemainfo = dbschema.getSchemaVersion(conn, LATESTVERSIONS)

   return {'database': dbinfo, 'schema': schemainfo}


def getDropUsersScript(user, demoUser = None):
   script = """
BEGIN
   -- kick all sessions for crossbar.io Repository user
   --
   FOR r IN (SELECT s.sid, s.serial#
               FROM v$session s
              WHERE s.username = UPPER('%(user)s'))
   LOOP
      EXECUTE IMMEDIATE
         'ALTER SYSTEM KILL SESSION ''' || r.sid || ',' || r.serial# || '''';
   END LOOP;
END;
/

BEGIN
   -- drop public synonyms created by crossbar.io Repository user
   --
   FOR r IN (SELECT DISTINCT sname
               FROM synonyms
              WHERE creator = UPPER('%(user)s') AND syntype = 'PUBLIC')
   LOOP
      EXECUTE IMMEDIATE 'DROP PUBLIC SYNONYM ' || r.sname;
   END LOOP;
END;
/

DECLARE
   l_id   NUMBER;
BEGIN
   -- remove all pipes for crossbar.io Repository user
   --
   FOR r IN (SELECT name
               FROM v$db_pipes
              WHERE name LIKE UPPER('CROSSBAR#_%(user)s%%') ESCAPE '#')
   LOOP
      BEGIN
         l_id   := sys.DBMS_PIPE.remove_pipe (pipename => r.name);
      EXCEPTION
         WHEN OTHERS THEN
            NULL;
      END;
   END LOOP;
END;
/

BEGIN
   -- drop crossbar.io Repository user and all it's objects
   --
   EXECUTE IMMEDIATE 'DROP USER %(user)s CASCADE';
EXCEPTION WHEN OTHERS THEN
   NULL;
END;
/
""" % {'user': user.lower()}

   if demoUser is not None:
      script += """
BEGIN
   -- kick all sessions for crossbar.io Demo user
   --
   FOR r IN (SELECT s.sid, s.serial#
               FROM v$session s
              WHERE s.username = UPPER('%(user)s'))
   LOOP
      EXECUTE IMMEDIATE
         'ALTER SYSTEM KILL SESSION ''' || r.sid || ',' || r.serial# || '''';
   END LOOP;
END;
/

BEGIN
   -- drop crossbar.io Demo user and all it's objects
   --
   EXECUTE IMMEDIATE 'DROP USER %(user)s CASCADE';
EXCEPTION WHEN OTHERS THEN
   NULL;
END;
/
""" % {'user': demoUser.lower()}

   return script


def getCreateUsersScript(user,
                         password,
                         tablespace = 'users',
                         publicsyn = True,
                         demoUser = None,
                         demoPassword = None):
   """
   Generate DDL for setting up crossbar.io Connect repository user.

   :param user: Oracle user name.
   :type user: str
   :param password: Password for Oracle user.
   :type password: str
   :param tablespace: Default tablespace for Oracle user.
   :type tablespace: str
   :param publicsyn: Grant public synonym create/drop to user.
   :type publicsyn: bool
   :returns str -- User create DDL script.
   """
   script = """
--
-- Create crossbar.io Repository Schema
--
CREATE USER %(user)s IDENTIFIED BY %(password)s
/
ALTER USER %(user)s DEFAULT TABLESPACE %(tablespace)s QUOTA UNLIMITED ON %(tablespace)s
/

GRANT CREATE SESSION TO %(user)s
/
GRANT CREATE TABLE TO %(user)s
/
GRANT CREATE VIEW TO %(user)s
/
GRANT CREATE SEQUENCE TO %(user)s
/
GRANT CREATE TYPE TO %(user)s
/
GRANT CREATE PROCEDURE TO %(user)s
/
GRANT CREATE TRIGGER TO %(user)s
/

GRANT EXECUTE ON SYS.DBMS_PIPE TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_LOCK TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_SESSION TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_LOB TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_TYPES TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_STATS TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_SQL TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_UTILITY TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_XMLGEN TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_RANDOM TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_CRYPTO TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_OUTPUT TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_DB_VERSION TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_APPLICATION_INFO TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_AQADM TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_AQ TO %(user)s
/
""" % {'user': user.lower(),
       'password': password,
       'tablespace': tablespace.lower()}

   if publicsyn:
      script += """
GRANT CREATE PUBLIC SYNONYM TO %(user)s
/
GRANT DROP PUBLIC SYNONYM TO %(user)s
/
""" % {'user': user.lower()}


   if demoUser is not None and demoPassword is not None:
      script += """
--
-- Create crossbar.io Demo Schema
--
CREATE USER %(user)s IDENTIFIED BY %(password)s
/
ALTER USER %(user)s DEFAULT TABLESPACE %(tablespace)s QUOTA UNLIMITED ON %(tablespace)s
/

GRANT CREATE SESSION TO %(user)s
/
GRANT CREATE TABLE TO %(user)s
/
GRANT CREATE VIEW TO %(user)s
/
GRANT CREATE SEQUENCE TO %(user)s
/
GRANT CREATE PROCEDURE TO %(user)s
/
GRANT CREATE TRIGGER TO %(user)s
/

GRANT EXECUTE ON SYS.DBMS_STATS TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_RANDOM TO %(user)s
/
GRANT EXECUTE ON SYS.DBMS_OUTPUT TO %(user)s
/
""" % {'user': demoUser.lower(),
       'password': demoPassword,
       'tablespace': tablespace.lower()}

   return script
