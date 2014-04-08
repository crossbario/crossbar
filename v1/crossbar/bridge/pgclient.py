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


from twisted.python import log

from autobahn.wamp import json_dumps


class PgConnect:
   """
   PostgreSQL Connect.
   """

   def __init__(self,
                id,
                host,
                port,
                database,
                user,
                password,
                connectionTimeout):

      ## 2 connects are equal (unchanged) iff the following are equal (unchanged)
      self.id = str(id)
      self.host = str(host)
      self.port = int(port)
      self.database = str(database)
      self.user = str(user)
      self.password = str(password)

      self.connectionTimeout = connectionTimeout

   def __eq__(self, other):
      if isinstance(other, PgConnect):
         return self.id == other.id and \
                self.host == other.host and \
                self.port == other.port and \
                self.database == other.database and \
                self.user == other.user and \
                self.password == other.password
      return NotImplemented

   # http://jcalderone.livejournal.com/32837.html !!
   def __ne__(self, other):
      result = self.__eq__(other)
      if result is NotImplemented:
         return result
      return not result

   def __repr__(self):
      r = {'id': self.id,
           #'connectionTimeout': self.connectionTimeout,
           'host': self.host,
           'port': self.port,
           'database': self.database,
           'user': self.user,
           'password': self.password}
      return json_dumps(r)


class PgSchemaSetup:

   SQL_CREATE_TABLE_EVENT = """
CREATE TABLE event
(
   id             BIGINT         PRIMARY KEY,
   published_at   TIMESTAMP      NOT NULL,
   published_by   VARCHAR(100)   NOT NULL,
   dispatched_at  TIMESTAMP,
   topic          VARCHAR        NOT NULL,
   payload_str    VARCHAR,
   payload_json   JSON
)
"""

   SQL_CREATE_PROCEDURE_PUBLISH = """
CREATE OR REPLACE FUNCTION publish(topic IN VARCHAR, payload IN VARCHAR)
RETURNS void
AS
$$
DECLARE
l_now                   TIMESTAMP;
BEGIN
   l_now := NOW () AT TIME ZONE 'UTC';
   INSERT INTO event (published_at, published_by, topic, payload_str) VALUES (l_now, session_user, topic, payload);
   NOTIFY event_published;
END
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION publish(topic IN VARCHAR, payload IN JSON)
RETURNS void
AS
$$
DECLARE
l_now                   TIMESTAMP;
BEGIN
   l_now := NOW () AT TIME ZONE 'UTC';
   INSERT INTO event (published_at, published_by, topic, payload_json) VALUES (l_now, session_user, topic, payload);
   NOTIFY event_published;
END
$$ LANGUAGE plpgsql SECURITY DEFINER;
"""

   SQL_TABLES = [('event', SQL_CREATE_TABLE_EVENT)]
   SQL_SEQUENCES = [('event_id', "CREATE SEQUENCE event_id")]
   SQL_PROCEDURES = [('publish', SQL_CREATE_PROCEDURE_PUBLISH)]

   def __init__(self, connect, schema, recreate = False):
      self.connect = connect
      self.schema = schema
      self.recreate = recreate

   def run(self):
      log.msg("PgSchemaSetup started")

      try:
         import time, json
         import psycopg2

         conn = psycopg2.connect(user = self.connect.user,
                                 password = self.connect.password,
                                 database = self.connect.database,
                                 host = self.connect.host,
                                 port = self.connect.port)
         conn.autocommit = True
         cur = conn.cursor()

         if self.recreate:
            log.msg("Recreating schema objects")

            for o in self.SQL_PROCEDURES:
               try:
                  cur.execute("DROP PROCEDURE ?", [o[0]])
                  log.msg("PROCEDURE %s dropped" % o[0])
               except:
                  pass

            for o in self.SQL_SEQUENCES:
               try:
                  cur.execute("DROP SEQUENCE ?", [o[0]])
                  log.msg("SEQUENCE %s dropped" % o[0])
               except:
                  pass

            for o in self.SQL_TABLES:
               try:
                  cur.execute("DROP TABLE ?", [o[0]])
                  log.msg("TABLE %s dropped" % o[0])
               except:
                  pass

         for o in self.SQL_TABLES:
            cur.execute("SELECT 1 FROM SYS.TABLES WHERE schema_name = ? AND table_name = ?", [self.schema, o[0].upper()])
            if cur.fetchone() is None:
               cur.execute(o[1])
               log.msg("TABLE %s created" % o[0])
            else:
               log.msg("TABLE %s already exists" % o[0])

         for o in self.SQL_SEQUENCES:
            cur.execute("SELECT 1 FROM SYS.SEQUENCES WHERE schema_name = ? AND sequence_name = ?", [self.schema, o[0].upper()])
            if cur.fetchone() is None:
               cur.execute(o[1])
               log.msg("SEQUENCE %s created" % o[0])
            else:
               log.msg("SEQUENCE %s already exists" % o[0])

         for o in self.SQL_PROCEDURES:
            cur.execute("SELECT 1 FROM SYS.PROCEDURES WHERE schema_name = ? AND procedure_name = ?", [self.schema, o[0].upper()])
            if cur.fetchone() is None:
               cur.execute(o[1])
               log.msg("PROCEDURE %s created" % o[0])
            else:
               log.msg("PROCEDURE %s already exists" % o[0])


      except Exception, e:
         log.msg(e)
         raise e
