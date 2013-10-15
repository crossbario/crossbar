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

from twisted.python import log

from autobahn.wamp import json_loads, json_dumps

from autobahn.util import utcnow

import dbschema
import oraschema


SCHEMAVERSION = 13


def getSchemaVersion(app, conn):
   return dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)


def extractDDL(scriptdir, scriptfiles):
   tsql = []

   ## we need to split install files contents into individual SQL
   ## statements and clean away any SQLplus related stuff
   for fn in scriptfiles:
      try:
         f = open(os.path.join(scriptdir, fn), "rb")
         fc = f.read()
         block = 1
         sql = []
         for l in fc.splitlines():
            if l.lower().startswith("sho") or l.lower().startswith("set") or l.lower().startswith("exit"):
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


def executeDDL(cur, tsql):
   for fn, block, t in tsql:
      try:
         log.msg("executing %s block %d .." % (fn, block))
         cur.execute(t)
      except Exception, e:
         m = "error installing %s block %d (%s)" % (fn, block, e)
         log.msg(t)
         raise Exception(m)


def _setupSchema(app, conn, uninstallOnly = False):

   cf = os.path.join(app.webdata, "demo", "demo.json")
   try:
      cfo = json_loads(open(cf).read())
   except Exception, e:
      log.msg("Could not read Oracle demo schema spec [%s]" % e)
      raise e

   scriptdir = os.path.join(app.webdata, "demo")

   uninstalls = []
   installs = []
   for d in cfo["demos"].values():
      installs.extend(d["sqlInstall"])
      uninstalls.extend(d["sqlUninstall"])

   SCHEMAVERSION = cfo["version"]

   print scriptdir, installs, uninstalls, SCHEMAVERSION

   cur = conn.cursor()
   executeDDL(cur, extractDDL(scriptdir, uninstalls))

   TABLES = ['config']

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

   if not uninstallOnly:

      executeDDL(cur, extractDDL(scriptdir, installs))

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

      ## store database schema version
      ##
      config = [('schema-category', 'demo'),
                ('schema-version', SCHEMAVERSION),
                ('schema-created', utcnow())]
      for key, value in config:
         cur.execute("INSERT INTO config (key, value) VALUES (:1, :2)", [key, json_dumps(value)])
      conn.commit()

      log.msg("crossbar.io Demo schema created (version %d)!" % SCHEMAVERSION)

   else:

      log.msg("crossbar.io Demo schema dropped!")

   return dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)


def setupSchema(app, conn):
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is not None:
      raise Exception("crossbar.io Demo already installed")

   return _setupSchema(app, conn)


def reinstallSchema(app, conn):
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Demo not installed")

   return _setupSchema(app, conn)


def dropSchema(app, conn):
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Demo not installed")

   return _setupSchema(app, conn, uninstallOnly = True)


def upgradeSchema(app, conn):
   r = dbschema.getSchemaVersion(conn, oraschema.LATESTVERSIONS)

   if r['schema-version'] is None:
      raise Exception("crossbar.io Demo not installed")

   if not r['schema-needs-upgrade']:
      raise Exception("crossbar.io Demo needs no upgrade")

   return _setupSchema(app, conn)
