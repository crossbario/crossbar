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


import sqlite3, os, time, datetime

from twisted.python import log
from twisted.enterprise import adbapi

import pkg_resources, shutil

from autobahn.util import utcnow, newid
from autobahn.wamp import json_loads, json_dumps

from cryptoutil import verify_and_decrypt
from crossbar.x509util import generate_rsa_key

from crossbar.adminwebmodule.uris import URI_ERROR


def oldtable(tablename):
   now = datetime.datetime.utcnow()
   return now.strftime(tablename + "_%Y%m%d_%H%M%S")




#class Database(service.Service):
class Database:
   """
   Crossbar.io service database.
   """

   SERVICENAME = "Database"

   DBVERSION = 80
   """
   Database version. This needs to be incremented on structural changes.
   """

   WEBMQ_LICENSE_CA_PUBKEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnrLrHYISb0Rd9AiUlYXE
BBvkMoz3a+eF8N8JYkcjmW8uvOjM1o1fKWFJW57TOjbJmOdyf0GNxAvldbQecZCF
yqICmCY9xF4KcPpMJ4RqBHGDVTycCkLoIhUg8hB2Zb5BkL2fxN28ZvBXGuuLkdOu
83Oo882/8DZgFei6HHC5+ISdno8dHcCaw4EieZdsNiFin6qG65Wkr6EMhKupihHS
+7HA/wVQWX1bAFJdkL1Jidt3M4iPSjpI4Edg++yNRI+UdT461j7tpkUq4csLh7fc
LqlHJZhL4Xr6/pikVxjB1ZwU5+NMJrngPasannkp1tfOd/rnSHqkf2jfNDgAAQn3
OQIDAQAB
-----END PUBLIC KEY-----
"""


   ## Package list considered for updating crossbar.io
   ##
   ##
   CROSSBAR_UPDATE_URL = "http://www.tavendo.de/download/webmq/release/eggs/"

   ## Hosts considered for updating crossbar.io
   ##
   ## Note, that we only have Tavendo server here, since pointing to servers
   ## no controlled by us might lead to compromised/unwanted software be installed!!!
   ##
   ## http://packages.python.org/distribute/easy_install.html#restricting-downloads-with-allow-hosts
   ## ie.: "*.myintranet.example.com,*.python.org"
   ##
   #CROSSBAR_UPDATE_HOST = "www.tavendo.de,pypi.python.org"
   CROSSBAR_UPDATE_HOST = "www.tavendo.de"

   ## The following command will get executed:
   ##
   ## ./app/bin/easy_install -H www.tavendo.de -U -v -f http://www.tavendo.de/download/webmq/release/eggs/ WebMQ
   ##

   SERVICES = [
               ## admin API and UI
               "service-enable-adminui", # this should be "not editable" in UI

               ## main application WebSocket/Web network service
               "service-enable-appws",
               "service-enable-appweb", # formerly called 'ws-enable-webserver'

               ## auxiliary network services
               "service-enable-flashpolicy",
               "service-enable-echows",
               "service-enable-ftp",

               ## system monitoring services
               "service-enable-netstat",
               "service-enable-vmstat",

               ## integration services
               "service-enable-restpusher",
               "service-enable-restremoter",
               "service-enable-pgpusher",
               "service-enable-pgremoter",
               "service-enable-orapusher",
               "service-enable-oraremoter",
               "service-enable-hanapusher",
               "service-enable-hanaremoter",
               "service-enable-extdirectremoter",
               # there is no 'extdirectpusher' service!
               ]

   NETPORTS = ["ssh-port",
               "hub-web-port",
               "hub-websocket-port",
               "admin-web-port",
               "admin-websocket-port",
               "flash-policy-port",
               "echo-websocket-port",
               "ftp-port",
               "ftp-passive-port-start",
               "ftp-passive-port-end"]
   """
   Database config keys for network ports. Service network listening ports database keys.
   """

   NETPORTS_READONLY = ["ssh-port"]
   """
   Database config keys for read-only network ports.
   """

   NETPORTS_TLS_PREFIXES = ["hub-web",
                            "hub-websocket",
                            "admin-web",
                            "admin-websocket",
                            "echo-websocket"]
   """
   Prefixes of database config keys for network services capable of TLS.
   """

   NETPORTS_TLS_FLAGS = [x + "-tls" for x in NETPORTS_TLS_PREFIXES]
   """
   Database config keys of enable flags for network services capable of TLS.
   """

   NETPORTS_TLS_KEYS = [x + "-tlskey" for x in NETPORTS_TLS_PREFIXES]
   """
   Database config keys of key/certs for network services (URIs pointing to database
   table "servicekeys") capable of TLS.
   """

   @staticmethod
   def parseLicense(instanceKey, payload):

      if type(payload) not in [str, unicode]:
         raise Exception("invalid license payload type (expected string, got %s" % type(payload))

      arr = payload.split(',')
      if len(arr) != 4:
         raise Exception("invalid license payload (expected 4 elements, got %d" % len(arr))

      # encrypted message, symmetric encryption key and signature
      (msg, key, dig, sig) = arr

      try:
         cmsg = verify_and_decrypt(msg,
                                   key,
                                   dig,
                                   sig,
                                   Database.WEBMQ_LICENSE_CA_PUBKEY,
                                   instanceKey)
      except Exception, e:
         raise Exception("could not decrypt license (%s)" % str(e))

      try:
         license = json_loads(cmsg)
      except Exception, e:
         raise Exception("could not parse license (%s)" % str(e))

      ## check all fields are present and convert Unicode to normal str
      required_fields = ['license-id',
                         'host-id',
                         'instance-id',
                         'valid-from',
                         'valid-to',
                         'type',
                         'connection-cap',
                         'tls-enabled']
      for f in required_fields:
         if not license.has_key(f):
            raise Exception("missing license field '%s'" % f)
         else:
            license[f] = str(license[f])

      return license



   def __init__(self, services):
      """
      Ctor.

      :param services: Crossbar.io services.
      :type services: dict
      """

      self.services = services
      self.isRunning = False

      self.licenseOptions = None
      self.installedOptions = None

      ## Crossbar.io data directory
      self.cbdata = services["master"].cbdata
      self.dbfile = os.path.join(self.cbdata, "crossbar.dat")


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)

      ## create application data directory if it does not exist
      ##
      if not os.path.isdir(self.cbdata):
         log.msg("application data directory %s does not exist - creating" % self.cbdata)
         os.mkdir(self.cbdata)
      else:
         log.msg("starting application from application data directory %s" % self.cbdata)

      self.createOrUpgrade()
      self.checkIntegrity()

      cfg = self.getConfig(includeTls = True)

      ## Create Dir structure
      ##
      dirs = ["log-dir", "export-dir", "import-dir", "web-dir"]
      for d in dirs:
         dir = str(cfg[d])
         if not os.path.isdir(dir):
            if d == "web-dir":
               self.scratchWebDir(dir)
               log.msg("copied web template to application data subdirectory %s" % dir)
            else:
               os.mkdir(dir)
               log.msg("created application data subdirectory %s" % dir)

      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def scratchWebDir(self, dir = None, init = True):

      if init:
         log.msg("scratching and initializing web directory %s" % dir)
      else:
         log.msg("scratching web directory %s" % dir)

      if dir is None:
         dir = self.services["config"]["web-dir"]
      dst = os.path.abspath(dir)

      if os.path.isdir(dst):
         try:
            shutil.rmtree(dst)
         except Exception, e:
            raise Exception(URI_ERROR + "execution-error", "Could not remove web directory [%s]." % str(e))

      if init:
         try:
            import crossbardemo
            log.msg("Found crossbardemo package v%s" % crossbardemo.__version__)
         except ImportError:
            os.mkdir(dst)
            log.msg("Skipping web directory init (crossbardemo package not installed)")
         else:
            try:
               src = os.path.abspath(pkg_resources.resource_filename("crossbardemo", "web"))
               shutil.copytree(src, dst)
            except Exception, e:
               raise Exception(URI_ERROR + "execution-error", "Could not init web directory [%s]." % str(e))
            log.msg("scratched and initialized web directory %s" % dst)
      else:
         try:
            os.mkdir(dst)
         except Exception, e:
            raise Exception(URI_ERROR + "execution-error", "Could not create web directory [%s]." % str(e))
         log.msg("scratched web directory %s" % dst)

      def dowalk(dir):
         nfiles = 0
         fsize = 0
         for root, dirs, files in os.walk(dir):
            nfiles += len(files)
            fsize += sum(os.path.getsize(os.path.join(root, name)) for name in files)
            for d in dirs:
               _nfiles, _fsize = dowalk(d)
               nfiles += _nfiles
               fsize += _fsize
         return nfiles, fsize

      return dowalk(dst)


   def createPool(self):
      """
      Create Twisted database connection pool.
      """
      return adbapi.ConnectionPool('sqlite3',
                                   self.dbfile,
                                   check_same_thread = False # http://twistedmatrix.com/trac/ticket/3629
                                   )


   def checkIntegrity(self):
      db = sqlite3.connect(self.dbfile)
      cur = db.cursor()

      cur.execute("SELECT value FROM config WHERE key = ?", ['instance-priv-key'])
      res = cur.fetchone()
      instanceKey = str(json_loads(res[0]))

      invalidLicenseIds = []

      cur.execute("SELECT license_id, license, host_id, instance_id, valid_from, valid_to, license_type, connection_cap, tls_enabled FROM license WHERE enabled = 1")
      res = cur.fetchall()
      for r in res:
         payload = r[1]
         r = list(r)
         r[8] = True if r[8] != 0 else False
         try:
            license = Database.parseLicense(instanceKey, payload)
            errs = []
            i = 2
            for a in ['host-id', 'instance-id', 'valid-from', 'valid-to', 'type', 'connection-cap', 'tls-enabled']:
               if str(r[i]) != str(license[a]):
                  errs.append("%s mismatch (%s / %s)" % (a, r[i], license[a]))
               i += 1
            if len(errs) > 0:
               invalidLicenseIds.append((r[0], errs))
         except Exception, e:
            invalidLicenseIds.append((r[0], str(e)))

      if len(invalidLicenseIds) > 0:
         log.msg("CORRUPT license(s) in database. Disabling corrupt licenses:")
         log.msg(invalidLicenseIds)
         for l in invalidLicenseIds:
            cur.execute("UPDATE license SET enabled = 0 WHERE license_id = ?", [l[0]])
            db.commit()



   def createOrUpgrade(self):
      """
      Create or upgrade application database.
      """
      if not os.path.isfile(self.dbfile):
         log.msg("database does not exist")
         self.createDatabase()
         self.initDatabase()
         log.msg("database created and initialized")
      else:
         info = self.getDatabaseInfo()
         if info is None:
            log.msg("database file exists, but database is corrupt - removing file")
            os.remove(self.dbfile)
            self.createOrUpgrade()
         else:
            version = info["database-version"]
            if version < Database.DBVERSION:
               log.msg("database needs upgrade (from %d to %d)" % (version, Database.DBVERSION))
               self.upgradeDatabase(version, Database.DBVERSION)
            else:
               log.msg("database exists in current version %d" % version)


   def upgradeDatabase(self, currentVersion, newVersion):
      if False:
         ## recreate database from scratch
         os.remove(self.dbfile)
         self.createOrUpgrade()
      else:
         ## graceful upgrade
         db = sqlite3.connect(self.dbfile)
         cur = db.cursor()

         while currentVersion < newVersion:
            log.msg("upgrading database from %d to %d" % (currentVersion, currentVersion + 1))

            if currentVersion == 64:
               ## upgrade: 64 => 65
               ##
               CONFIG = {
                   ## Echo WS service
                   ##
                   "echo-websocket-port": 7000,
                   "echo-websocket-tls": False,
                   "echo-websocket-tlskey": None
                   }
               for k in CONFIG:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
               db.commit()

            elif currentVersion == 65:
               ## upgrade: 65 => 66
               ##
               cur.execute("""
                           CREATE TABLE extdirectremote (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              require_appcred_id   TEXT,
                              base_uri             TEXT     NOT NULL,
                              server_url           TEXT     NOT NULL,
                              api_path             TEXT     NOT NULL,
                              api_object           TEXT     NOT NULL,
                              timeout              INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_extdirectremote AS SELECT * FROM extdirectremote ORDER BY id")

            elif currentVersion == 66:
               ## upgrade: 66 => 67
               ##
               cur.execute("""DROP VIEW d_extdirectremote""")
               cur.execute("""DROP TABLE extdirectremote""")
               cur.execute("""
                           CREATE TABLE extdirectremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              rpc_base_uri               TEXT     NOT NULL,
                              router_url                 TEXT     NOT NULL,
                              api_url                    TEXT     NOT NULL,
                              api_object                 TEXT     NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL,
                              max_persistent_conns       INTEGER  NOT NULL,
                              persistent_conn_timeout    INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_extdirectremote AS SELECT * FROM extdirectremote ORDER BY id")

            elif currentVersion == 67:
               ## upgrade: 67 => 68
               ##
               cur.execute("""
                           CREATE TABLE restremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              rpc_base_uri               TEXT     NOT NULL,
                              rest_base_url              TEXT     NOT NULL,
                              payload_format             TEXT     NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL,
                              max_persistent_conns       INTEGER  NOT NULL,
                              persistent_conn_timeout    INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_restremote AS SELECT * FROM restremote ORDER BY id")

            if currentVersion == 68:
               ## upgrade: 68 => 69
               ##
               CONFIG = {
                  "ws-accept-queue-size": 5000,
                  "ws-enable-webserver": True,
                  "ws-websocket-path": "ws",
                  "web-dir": os.path.join(self.cbdata, "web")
               }
               for k in CONFIG:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
               db.commit()

               cur.execute("DROP VIEW d_restremote")
               cur.execute("ALTER TABLE restremote RENAME TO tmp_restremote")
               cur.execute("""
                           CREATE TABLE restremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              rpc_base_uri               TEXT     NOT NULL,
                              rest_base_url              TEXT     NOT NULL,
                              payload_format             TEXT     NOT NULL,
                              forward_cookies            INTEGER  NOT NULL,
                              redirect_limit             INTEGER  NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL,
                              max_persistent_conns       INTEGER  NOT NULL,
                              persistent_conn_timeout    INTEGER  NOT NULL)
                           """)
               cur.execute("""INSERT INTO restremote (
                                    id,
                                    created,
                                    modified,
                                    require_appcred_id,
                                    rpc_base_uri,
                                    rest_base_url,
                                    payload_format,
                                    forward_cookies,
                                    redirect_limit,
                                    connection_timeout,
                                    request_timeout,
                                    max_persistent_conns,
                                    persistent_conn_timeout
                                    ) SELECT
                                    id,
                                    created,
                                    modified,
                                    require_appcred_id,
                                    rpc_base_uri,
                                    rest_base_url,
                                    payload_format,
                                    1,
                                    0,
                                    connection_timeout,
                                    request_timeout,
                                    max_persistent_conns,
                                    persistent_conn_timeout
                                    FROM tmp_restremote""")
               cur.execute("CREATE VIEW d_restremote AS SELECT * FROM restremote ORDER BY id")
               cur.execute("DROP TABLE tmp_restremote")

               cur.execute("DROP VIEW d_extdirectremote")
               cur.execute("ALTER TABLE extdirectremote RENAME TO tmp_extdirectremote")
               cur.execute("""
                           CREATE TABLE extdirectremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              rpc_base_uri               TEXT     NOT NULL,
                              router_url                 TEXT     NOT NULL,
                              api_url                    TEXT     NOT NULL,
                              api_object                 TEXT     NOT NULL,
                              forward_cookies            INTEGER  NOT NULL,
                              redirect_limit             INTEGER  NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL,
                              max_persistent_conns       INTEGER  NOT NULL,
                              persistent_conn_timeout    INTEGER  NOT NULL)
                           """)
               cur.execute("""INSERT INTO extdirectremote (
                                    id,
                                    created,
                                    modified,
                                    require_appcred_id,
                                    rpc_base_uri,
                                    router_url,
                                    api_url,
                                    api_object,
                                    forward_cookies,
                                    redirect_limit,
                                    connection_timeout,
                                    request_timeout,
                                    max_persistent_conns,
                                    persistent_conn_timeout
                                    ) SELECT
                                    id,
                                    created,
                                    modified,
                                    require_appcred_id,
                                    rpc_base_uri,
                                    router_url,
                                    api_url,
                                    api_object,
                                    1,
                                    0,
                                    connection_timeout,
                                    request_timeout,
                                    max_persistent_conns,
                                    persistent_conn_timeout
                                    FROM tmp_extdirectremote""")
               cur.execute("CREATE VIEW d_extdirectremote AS SELECT * FROM extdirectremote ORDER BY id")
               cur.execute("DROP TABLE tmp_extdirectremote")

            if currentVersion == 69:
               ## upgrade: 69 => 70
               ##
               CONFIG = {"ftp-passive-public-ip": None}
               for k in CONFIG:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
               db.commit()

            if currentVersion == 70:
               ## upgrade: 70 => 71
               ##
               cur.execute("""
                           CREATE TABLE hanaconnect (
                              id                TEXT     PRIMARY KEY,
                              created           TEXT     NOT NULL,
                              modified          TEXT,
                              label             TEXT     NOT NULL,
                              driver            TEXT     NOT NULL,
                              host              TEXT     NOT NULL,
                              port              INTEGER  NOT NULL,
                              database          TEXT     NOT NULL,
                              user              TEXT     NOT NULL,
                              password          TEXT     NOT NULL)
                           """)
               cur.execute("""CREATE VIEW d_hanaconnect AS
                                 SELECT id,
                                        created,
                                        modified,
                                        label,
                                        driver,
                                        host,
                                        port,
                                        database,
                                        user,
                                        length(password) AS length_password FROM hanaconnect ORDER BY id""")

            if currentVersion == 71:
               ## upgrade: 71 => 72
               ##
               cur.execute("""
                           CREATE TABLE hanapushrule (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              hanaconnect_id       TEXT     NOT NULL,
                              user                 TEXT,
                              topic_uri            TEXT     NOT NULL,
                              match_by_prefix      INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_hanapushrule AS SELECT * FROM hanapushrule ORDER BY id")

            if currentVersion == 72:
               ## upgrade: 72 => 73
               ##
               cur.execute("""
                           CREATE TABLE pgconnect (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              label                TEXT     NOT NULL,
                              host                 TEXT     NOT NULL,
                              port                 INTEGER  NOT NULL,
                              database             TEXT     NOT NULL,
                              user                 TEXT     NOT NULL,
                              password             TEXT     NOT NULL,
                              connection_timeout   INTEGER  NOT NULL
                              )
                           """)
               cur.execute("""CREATE VIEW d_pgconnect AS
                                 SELECT id,
                                        created,
                                        modified,
                                        label,
                                        host,
                                        port,
                                        database,
                                        user,
                                        length(password) AS length_password,
                                        connection_timeout
                                        FROM pgconnect ORDER BY id""")
               cur.execute("""
                           CREATE TABLE pgpushrule (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              pgconnect_id         TEXT     NOT NULL,
                              user                 TEXT,
                              topic_uri            TEXT     NOT NULL,
                              match_by_prefix      INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_pgpushrule AS SELECT * FROM pgpushrule ORDER BY id")

            if currentVersion == 73:
               ## upgrade: 73 => 74
               ##
               cur.execute("""
                           CREATE TABLE oraconnect (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              label                TEXT     NOT NULL,
                              host                 TEXT     NOT NULL,
                              port                 INTEGER  NOT NULL,
                              sid                  TEXT     NOT NULL,
                              user                 TEXT     NOT NULL,
                              password             TEXT     NOT NULL,
                              connection_timeout   INTEGER  NOT NULL
                              )
                           """)
               cur.execute("""CREATE VIEW d_oraconnect AS
                                 SELECT id,
                                        created,
                                        modified,
                                        label,
                                        host,
                                        port,
                                        sid,
                                        user,
                                        length(password) AS length_password,
                                        connection_timeout
                                        FROM oraconnect ORDER BY id""")

               cur.execute("""
                           CREATE TABLE orapushrule (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              oraconnect_id        TEXT     NOT NULL,
                              user                 TEXT,
                              topic_uri            TEXT     NOT NULL,
                              match_by_prefix      INTEGER  NOT NULL)
                           """)
               cur.execute("CREATE VIEW d_orapushrule AS SELECT * FROM orapushrule ORDER BY id")

            if currentVersion == 74:
               ## upgrade: 74 => 75
               ##
               cur.execute("""
                           CREATE TABLE hanaremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              hanaconnect_id             TEXT     NOT NULL,
                              schema_list                TEXT     NOT NULL,
                              rpc_base_uri               TEXT     NOT NULL,
                              connection_pool_min_size   INTEGER  NOT NULL,
                              connection_pool_max_size   INTEGER  NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL)
                           """)
               cur.execute("""CREATE VIEW d_hanaremote AS
                                 SELECT id,
                                        created,
                                        modified,
                                        require_appcred_id,
                                        hanaconnect_id,
                                        schema_list,
                                        rpc_base_uri,
                                        connection_pool_min_size,
                                        connection_pool_max_size,
                                        connection_timeout,
                                        request_timeout FROM hanaremote ORDER BY id""")

               cur.execute("""
                           CREATE TABLE pgremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              pgconnect_id               TEXT     NOT NULL,
                              schema_list                TEXT     NOT NULL,
                              rpc_base_uri               TEXT     NOT NULL,
                              connection_pool_min_size   INTEGER  NOT NULL,
                              connection_pool_max_size   INTEGER  NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL)
                           """)
               cur.execute("""CREATE VIEW d_pgremote AS
                                 SELECT id,
                                        created,
                                        modified,
                                        require_appcred_id,
                                        pgconnect_id,
                                        schema_list,
                                        rpc_base_uri,
                                        connection_pool_min_size,
                                        connection_pool_max_size,
                                        connection_timeout,
                                        request_timeout FROM pgremote ORDER BY id""")

               cur.execute("""
                           CREATE TABLE oraremote (
                              id                         TEXT     PRIMARY KEY,
                              created                    TEXT     NOT NULL,
                              modified                   TEXT,
                              require_appcred_id         TEXT,
                              oraconnect_id              TEXT     NOT NULL,
                              schema_list                TEXT     NOT NULL,
                              rpc_base_uri               TEXT     NOT NULL,
                              connection_pool_min_size   INTEGER  NOT NULL,
                              connection_pool_max_size   INTEGER  NOT NULL,
                              connection_timeout         INTEGER  NOT NULL,
                              request_timeout            INTEGER  NOT NULL)
                           """)
               cur.execute("""CREATE VIEW d_oraremote AS
                                 SELECT id,
                                        created,
                                        modified,
                                        require_appcred_id,
                                        oraconnect_id,
                                        schema_list,
                                        rpc_base_uri,
                                        connection_pool_min_size,
                                        connection_pool_max_size,
                                        connection_timeout,
                                        request_timeout FROM oraremote ORDER BY id""")

            if currentVersion == 75:
               ## upgrade: 75 => 76
               ##
               for k in Database.SERVICES:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(True)])
               db.commit()

            if currentVersion == 76:
               ## upgrade: 76 => 77
               ##
               try:
                  cur.execute("DROP VIEW d_oraconnect")
               except:
                  pass

               tmp = oldtable("oraconnect")
               cur.execute("ALTER TABLE oraconnect RENAME TO %s" % tmp)
               log.msg("renamed table 'oraconnect' to temp table '%s'" % tmp)

               cur.execute("""
                           CREATE TABLE oraconnect (
                              id                   TEXT     PRIMARY KEY,
                              created              TEXT     NOT NULL,
                              modified             TEXT,
                              label                TEXT     NOT NULL,
                              host                 TEXT     NOT NULL,
                              port                 INTEGER  NOT NULL,
                              sid                  TEXT     NOT NULL,
                              user                 TEXT     NOT NULL,
                              password             TEXT     NOT NULL,
                              demo_user            TEXT,
                              demo_password        TEXT,
                              connection_timeout   INTEGER  NOT NULL
                              )
                           """)
               cur.execute("""CREATE VIEW d_oraconnect AS
                                 SELECT id,
                                        created,
                                        modified,
                                        label,
                                        host,
                                        port,
                                        sid,
                                        user,
                                        length(password) AS length_password,
                                        demo_user,
                                        length(demo_password) AS length_demo_password,
                                        connection_timeout
                                        FROM oraconnect ORDER BY id""")

               cur.execute("INSERT INTO oraconnect (id, created, modified, label, host, port, sid, user, password, connection_timeout) SELECT id, created, modified, label, host, port, sid, user, password, connection_timeout FROM %s" % tmp)
               db.commit()
               log.msg("inserted data from temp table '%s' into oraconnect" % tmp)

               cur.execute("DROP TABLE %s" % tmp)
               log.msg("dropped temp table '%s'" % tmp)

            if currentVersion == 77:
               ## upgrade: 77 => 78
               ##
               cur.execute("""
                           CREATE TABLE objstore (
                              uri               TEXT     PRIMARY KEY,
                              obj               TEXT     NOT NULL)
                           """)
               cur.execute("""CREATE VIEW d_objstore AS
                              SELECT uri, obj FROM objstore ORDER BY uri
                           """)

            if currentVersion == 78:
               ## upgrade: 78 => 79
               ##
               CONFIG = {
                  "ws-enable-permessage-deflate": True,
                  "ws-permessage-deflate-window-size": 0,
                  "ws-permessage-deflate-require-window-size": False
               }
               for k in CONFIG:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
               db.commit()

            if currentVersion == 79:
               ## upgrade: 79 => 80
               ##
               CONFIG = {
                   ## CGI Processor
                   ##
                   "appweb-cgi-enable": False,
                   "appweb-cgi-path": "cgi",
                   "appweb-cgi-processor": ""
                   }
               for k in CONFIG:
                  cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
               db.commit()

            ## set new database version
            ##
            currentVersion += 1
            cur.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(currentVersion), "database-version"])
            db.commit()


   def createDatabase(self):
      """
      Create WebMQ service database from scratch.
      """
      log.msg("creating database at %s .." % self.dbfile)
      db = sqlite3.connect(self.dbfile)

      cur = db.cursor()

      cur.execute("""
                  CREATE TABLE config (
                     key               TEXT     PRIMARY KEY,
                     value             TEXT     NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_config AS
                     SELECT * FROM
                     (
                        SELECT key,
                               value FROM config WHERE key NOT IN ('admin-password', 'instance-priv-key')
                        UNION ALL
                        SELECT key,
                               length(value) AS VALUE FROM config WHERE key IN ('admin-password', 'instance-priv-key')
                     ) ORDER BY key""")

      cur.execute("""
                  CREATE TABLE objstore (
                     uri               TEXT     PRIMARY KEY,
                     obj               TEXT     NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_objstore AS
                     SELECT uri, obj FROM objstore ORDER BY uri
                  """)

      cur.execute("""
                  CREATE TABLE appcredential (
                     id                TEXT     PRIMARY KEY,
                     created           TEXT     NOT NULL,
                     modified          TEXT,
                     label             TEXT     NOT NULL,
                     key               TEXT     NOT NULL UNIQUE,
                     secret            TEXT     NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_appcredential AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               key,
                               length(secret) AS length_secret FROM appcredential ORDER BY id""")

      cur.execute("""
                  CREATE TABLE ftpuser (
                     id                TEXT     PRIMARY KEY,
                     created           TEXT     NOT NULL,
                     modified          TEXT,
                     label             TEXT     NOT NULL,
                     user              TEXT     NOT NULL UNIQUE,
                     password          TEXT     NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_ftpuser AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               user,
                               length(password) AS length_password FROM ftpuser ORDER BY id""")

      cur.execute("""
                  CREATE TABLE postrule (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     position             FLOAT    NOT NULL UNIQUE,
                     topic_uri            TEXT     NOT NULL,
                     match_by_prefix      INTEGER  NOT NULL,
                     filter_ip            INTEGER  NOT NULL,
                     filter_ip_network    TEXT,
                     require_signature    INTEGER  NOT NULL,
                     require_appcred_id   TEXT,
                     action               TEXT     NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_postrule AS SELECT * FROM postrule ORDER BY id")

      cur.execute("""
                  CREATE TABLE clientperm (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     topic_uri            TEXT     NOT NULL,
                     match_by_prefix      INTEGER  NOT NULL,
                     require_appcred_id   TEXT,
                     filter_expr          TEXT,
                     allow_publish        INTEGER  NOT NULL,
                     allow_subscribe      INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_clientperm AS SELECT * FROM clientperm ORDER BY id")

      cur.execute("""
                  CREATE TABLE extdirectremote (
                     id                         TEXT     PRIMARY KEY,
                     created                    TEXT     NOT NULL,
                     modified                   TEXT,
                     require_appcred_id         TEXT,
                     rpc_base_uri               TEXT     NOT NULL,
                     router_url                 TEXT     NOT NULL,
                     api_url                    TEXT     NOT NULL,
                     api_object                 TEXT     NOT NULL,
                     forward_cookies            INTEGER  NOT NULL,
                     redirect_limit             INTEGER  NOT NULL,
                     connection_timeout         INTEGER  NOT NULL,
                     request_timeout            INTEGER  NOT NULL,
                     max_persistent_conns       INTEGER  NOT NULL,
                     persistent_conn_timeout    INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_extdirectremote AS SELECT * FROM extdirectremote ORDER BY id")

      cur.execute("""
                  CREATE TABLE restremote (
                     id                         TEXT     PRIMARY KEY,
                     created                    TEXT     NOT NULL,
                     modified                   TEXT,
                     require_appcred_id         TEXT,
                     rpc_base_uri               TEXT     NOT NULL,
                     rest_base_url              TEXT     NOT NULL,
                     payload_format             TEXT     NOT NULL,
                     forward_cookies            INTEGER  NOT NULL,
                     redirect_limit             INTEGER  NOT NULL,
                     connection_timeout         INTEGER  NOT NULL,
                     request_timeout            INTEGER  NOT NULL,
                     max_persistent_conns       INTEGER  NOT NULL,
                     persistent_conn_timeout    INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_restremote AS SELECT * FROM restremote ORDER BY id")

      cur.execute("""
                  CREATE TABLE servicekey (
                     id                      TEXT     PRIMARY KEY,
                     created                 TEXT     NOT NULL,
                     modified                TEXT,
                     label                   TEXT     NOT NULL,
                     key_priv                TEXT     NOT NULL,
                     key_pub                 TEXT     NOT NULL,
                     key_length              INTEGER  NOT NULL,
                     key_fingerprint         TEXT     NOT NULL UNIQUE,
                     cert                    TEXT,
                     cert_text               TEXT,
                     cert_fingerprint        TEXT,
                     is_cert_selfsigned      INTEGER,
                     selfsigned_cert_serial  INTEGER
                  )
                  """)
      cur.execute("""CREATE VIEW d_servicekey AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               length(key_priv) AS length_key_priv,
                               key_pub,
                               key_length,
                               key_fingerprint,
                               cert,
                               cert_text,
                               cert_fingerprint,
                               is_cert_selfsigned,
                               selfsigned_cert_serial
                        FROM servicekey ORDER BY id""")

      cur.execute("""
                  CREATE TABLE cookie (
                     created              TEXT     NOT NULL,
                     username             TEXT     NOT NULL,
                     value                TEXT     NOT NULL UNIQUE)
                  """)
      cur.execute("""CREATE VIEW d_cookie AS
                        SELECT created,
                               username,
                               length(value) AS length_value
                        FROM cookie ORDER BY created, username""")

      # {"valid-from": "2012-04-19T07:31:33Z",
      #  "valid-to": "2012-06-30T00:00:00Z",
      #  "license-id": "83152182-b583-454d-826f-37b2e3f18544",
      #  "host-id": "00000000-0000-0000-0000-ac50849784fa",
      #  "connection-cap": 0,
      #  "tls-enabled": true,
      #  "type": "BETA",
      #  "instance-id": "32:84:71:98:A4:CF:60:1D:00:22:F6:A2:E7:82:C2:72:91:8D:69:A3"}
      cur.execute("""
                  CREATE TABLE license (
                     created              TEXT     NOT NULL,
                     license              TEXT     NOT NULL,
                     enabled              INTEGER  NOT NULL,
                     license_id           TEXT     NOT NULL UNIQUE,
                     host_id              TEXT     NOT NULL,
                     instance_id          TEXT     NOT NULL,
                     valid_from           TEXT     NOT NULL,
                     valid_to             TEXT     NOT NULL,
                     license_type         TEXT     NOT NULL,
                     connection_cap       INTEGER  NOT NULL,
                     tls_enabled          INTEGER  NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_license AS
                        SELECT created,
                               license,
                               enabled,
                               license_id,
                               host_id,
                               instance_id,
                               valid_from,
                               valid_to,
                               license_type,
                               connection_cap,
                               tls_enabled
                        FROM license ORDER BY instance_id, valid_from""")


      ## SAP HANA Database Integration Support
      ##
      cur.execute("""
                  CREATE TABLE hanaconnect (
                     id                TEXT     PRIMARY KEY,
                     created           TEXT     NOT NULL,
                     modified          TEXT,
                     label             TEXT     NOT NULL,
                     driver            TEXT     NOT NULL,
                     host              TEXT     NOT NULL,
                     port              INTEGER  NOT NULL,
                     database          TEXT     NOT NULL,
                     user              TEXT     NOT NULL,
                     password          TEXT     NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_hanaconnect AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               driver,
                               host,
                               port,
                               database,
                               user,
                               length(password) AS length_password FROM hanaconnect ORDER BY id""")

      cur.execute("""
                  CREATE TABLE hanapushrule (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     hanaconnect_id       TEXT     NOT NULL,
                     user                 TEXT,
                     topic_uri            TEXT     NOT NULL,
                     match_by_prefix      INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_hanapushrule AS SELECT * FROM hanapushrule ORDER BY id")

      cur.execute("""
                  CREATE TABLE hanaremote (
                     id                         TEXT     PRIMARY KEY,
                     created                    TEXT     NOT NULL,
                     modified                   TEXT,
                     require_appcred_id         TEXT,
                     hanaconnect_id             TEXT     NOT NULL,
                     schema_list                TEXT     NOT NULL,
                     rpc_base_uri               TEXT     NOT NULL,
                     connection_pool_min_size   INTEGER  NOT NULL,
                     connection_pool_max_size   INTEGER  NOT NULL,
                     connection_timeout         INTEGER  NOT NULL,
                     request_timeout            INTEGER  NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_hanaremote AS
                        SELECT id,
                               created,
                               modified,
                               require_appcred_id,
                               hanaconnect_id,
                               schema_list,
                               rpc_base_uri,
                               connection_pool_min_size,
                               connection_pool_max_size,
                               connection_timeout,
                               request_timeout FROM hanaremote ORDER BY id""")


      ## PostgreSQL Database Integration Support
      ##
      cur.execute("""
                  CREATE TABLE pgconnect (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     label                TEXT     NOT NULL,
                     host                 TEXT     NOT NULL,
                     port                 INTEGER  NOT NULL,
                     database             TEXT     NOT NULL,
                     user                 TEXT     NOT NULL,
                     password             TEXT     NOT NULL,
                     connection_timeout   INTEGER  NOT NULL
                     )
                  """)
      cur.execute("""CREATE VIEW d_pgconnect AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               host,
                               port,
                               database,
                               user,
                               length(password) AS length_password,
                               connection_timeout
                               FROM pgconnect ORDER BY id""")

      cur.execute("""
                  CREATE TABLE pgpushrule (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     pgconnect_id         TEXT     NOT NULL,
                     user                 TEXT,
                     topic_uri            TEXT     NOT NULL,
                     match_by_prefix      INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_pgpushrule AS SELECT * FROM pgpushrule ORDER BY id")

      cur.execute("""
                  CREATE TABLE pgremote (
                     id                         TEXT     PRIMARY KEY,
                     created                    TEXT     NOT NULL,
                     modified                   TEXT,
                     require_appcred_id         TEXT,
                     pgconnect_id               TEXT     NOT NULL,
                     schema_list                TEXT     NOT NULL,
                     rpc_base_uri               TEXT     NOT NULL,
                     connection_pool_min_size   INTEGER  NOT NULL,
                     connection_pool_max_size   INTEGER  NOT NULL,
                     connection_timeout         INTEGER  NOT NULL,
                     request_timeout            INTEGER  NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_pgremote AS
                        SELECT id,
                               created,
                               modified,
                               require_appcred_id,
                               pgconnect_id,
                               schema_list,
                               rpc_base_uri,
                               connection_pool_min_size,
                               connection_pool_max_size,
                               connection_timeout,
                               request_timeout FROM pgremote ORDER BY id""")

      ## Oracle Database Integration Support
      ##
      cur.execute("""
                  CREATE TABLE oraconnect (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     label                TEXT     NOT NULL,
                     host                 TEXT     NOT NULL,
                     port                 INTEGER  NOT NULL,
                     sid                  TEXT     NOT NULL,
                     user                 TEXT     NOT NULL,
                     password             TEXT     NOT NULL,
                     demo_user            TEXT,
                     demo_password        TEXT,
                     connection_timeout   INTEGER  NOT NULL
                     )
                  """)
      cur.execute("""CREATE VIEW d_oraconnect AS
                        SELECT id,
                               created,
                               modified,
                               label,
                               host,
                               port,
                               sid,
                               user,
                               length(password) AS length_password,
                               demo_user,
                               length(demo_password) AS length_demo_password,
                               connection_timeout
                               FROM oraconnect ORDER BY id""")

      cur.execute("""
                  CREATE TABLE orapushrule (
                     id                   TEXT     PRIMARY KEY,
                     created              TEXT     NOT NULL,
                     modified             TEXT,
                     oraconnect_id        TEXT     NOT NULL,
                     user                 TEXT,
                     topic_uri            TEXT     NOT NULL,
                     match_by_prefix      INTEGER  NOT NULL)
                  """)
      cur.execute("CREATE VIEW d_orapushrule AS SELECT * FROM orapushrule ORDER BY id")

      cur.execute("""
                  CREATE TABLE oraremote (
                     id                         TEXT     PRIMARY KEY,
                     created                    TEXT     NOT NULL,
                     modified                   TEXT,
                     require_appcred_id         TEXT,
                     oraconnect_id              TEXT     NOT NULL,
                     schema_list                TEXT     NOT NULL,
                     rpc_base_uri               TEXT     NOT NULL,
                     connection_pool_min_size   INTEGER  NOT NULL,
                     connection_pool_max_size   INTEGER  NOT NULL,
                     connection_timeout         INTEGER  NOT NULL,
                     request_timeout            INTEGER  NOT NULL)
                  """)
      cur.execute("""CREATE VIEW d_oraremote AS
                        SELECT id,
                               created,
                               modified,
                               require_appcred_id,
                               oraconnect_id,
                               schema_list,
                               rpc_base_uri,
                               connection_pool_min_size,
                               connection_pool_max_size,
                               connection_timeout,
                               request_timeout FROM oraremote ORDER BY id""")

      log.msg("database created.")


   def scratchDatabase(self):
      """
      Scratch all data from database, other than instance key / license.
      """
      log.msg("scratching database at %s .." % self.dbfile)
      db = sqlite3.connect(self.dbfile)

      cur = db.cursor()
      cur.execute("DELETE FROM config WHERE key NOT IN ('database-created', 'admin-password', 'instance-pub-key', 'instance-priv-key', 'instance-id')")
      cur.execute("DELETE FROM appcredential")
      cur.execute("DELETE FROM ftpuser")
      cur.execute("DELETE FROM postrule")
      cur.execute("DELETE FROM clientperm")
      cur.execute("DELETE FROM extdirectremote")
      cur.execute("DELETE FROM restremote")
      cur.execute("DELETE FROM servicekey")
      cur.execute("DELETE FROM cookie")
      # cur.execute("DELETE FROM license") ## license table NOT deleted!
      cur.execute("DELETE FROM hanaconnect")
      cur.execute("DELETE FROM hanapushrule")
      cur.execute("DELETE FROM hanaremote")
      cur.execute("DELETE FROM pgconnect")
      cur.execute("DELETE FROM pgpushrule")
      cur.execute("DELETE FROM pgremote")
      cur.execute("DELETE FROM oraconnect")
      cur.execute("DELETE FROM orapushrule")
      cur.execute("DELETE FROM oraremote")
      db.commit()
      self.initDatabase(scratchMode = True)
      log.msg("database scratched to factory state")


   def initDatabase(self, scratchMode = False):
      """
      Data initialization of application database.
      """
      log.msg("initializing database ..")

      db = sqlite3.connect(self.dbfile)
      cur = db.cursor()

      created = utcnow()

      ## instance RSA key
      ##
      if not scratchMode:
         log.msg("generating new instance key pair ..")
         (privkey, pubkey, fingerprint) = generate_rsa_key(2048)
         cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", ['instance-pub-key', json_dumps(pubkey)])
         cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", ['instance-priv-key', json_dumps(privkey)])
         cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", ['instance-id', json_dumps(fingerprint)])
         db.commit()
         log.msg("new instance key pair generated and stored (fingerprint %s)" % fingerprint)

      ## Default configuration (initial database contents)
      ##
      CONFIG = {
          "database-version": Database.DBVERSION,

          ## authentication related options
          ##
          "auth-cookie-lifetime": 60 * 60 * 12,

          ## client permissions related options
          ##
          "client-auth-timeout": 0,
          "client-auth-allow-anonymous": True,

          ## postrules related options
          ##
          "postrule-default-action": "ALLOW",
          "post-body-limit": 4096,
          "sig-timestamp-delta-limit": 300,

          ## SSH Service (fixed, OS provided)
          ##
          "ssh-port": 22,

          ## Admin Web service
          ##
          "admin-web-port": 9090,
          "admin-web-tls": False,
          "admin-web-tlskey": None,

          ## Admin WS service
          ##
          "admin-websocket-port": 9000,
          "admin-websocket-tls": False,
          "admin-websocket-tlskey": None,

          ## App WS service
          ##
          "hub-websocket-port": 8080,
          "hub-websocket-tls": False,
          "hub-websocket-tlskey": None,

          ## REST/Push service
          ##
          "hub-web-port": 8090,
          "hub-web-tls": False,
          "hub-web-tlskey": None,

          ## Echo WS service
          ##
          "echo-websocket-port": 7000,
          "echo-websocket-tls": False,
          "echo-websocket-tlskey": None,

          ## Flash Policy File service
          ##
          "flash-policy-port": 843,

          ## FTP service
          ##
          "ftp-port": 21,
          "ftp-passive-port-start": 10000,
          "ftp-passive-port-end": 10100,
          "ftp-passive-public-ip": None,

          ## FTP related options
          "ftp-dir": os.path.join(self.cbdata, "ftp"),

          ## Logging related options
          ##
          "log-dir": os.path.join(self.cbdata, "log"),
          "log-retention-time": 24*3,
          "log-write-interval": 60,

          ## export/import directories
          ##
          "export-dir": os.path.join(self.cbdata, "export"),
          "export-url": "export",
          "import-dir": os.path.join(self.cbdata, "import"),
          "import-url": "import",

          ## Web serving directory
          ##
          "web-dir": os.path.join(self.cbdata, "web"), # if ws-enable-webserver == True, we serve file via embedded Web server from here

          ## WebSocket options
          ##
          "ws-allow-version-0": True, # Hixie-76
          "ws-allow-version-8": True,  # Hybi-Draft-10
          "ws-allow-version-13": True, # RFC6455
          "ws-max-connections": 0,
          "ws-max-frame-size": 0,
          "ws-max-message-size": 0,
          "ws-auto-fragment-size": 0,
          "ws-fail-by-drop": False,
          "ws-echo-close-codereason": False,
          "ws-open-handshake-timeout": 0,
          "ws-close-handshake-timeout": 0,
          "ws-tcp-nodelay": True,
          "ws-mask-server-frames": False,
          "ws-require-masked-client-frames": True,
          "ws-apply-mask": True,
          "ws-validate-utf8": True,
          "ws-enable-webstatus": True,
          "ws-accept-queue-size": 5000, # forwarded to backlog parameter on listenTCP/listenSSL
          "ws-enable-webserver": True, # if True, run WebSocket under Twisted Web Site and provide static file Web serving
          "ws-websocket-path": "ws", # if "ws-enable-webserver" == True, path under which WebSocket is mapped with Twisted Web Site

          "ws-enable-permessage-deflate": True,
          "ws-permessage-deflate-window-size": 0,
          "ws-permessage-deflate-require-window-size": False,

          ## CGI
          ##
          "appweb-cgi-enable": False,
          "appweb-cgi-path": "cgi",
          "appweb-cgi-processor": "",

          ## Update options
          ##
          "update-url": Database.CROSSBAR_UPDATE_URL,
          "update-check-interval": 600,

          "eula-accepted": None,

          ## admin API and UI
          "service-enable-adminui": True,
 
          ## main application WebSocket/Web network service
          "service-enable-appws": True,
          "service-enable-appweb": True,
 
          ## auxiliary network services
          "service-enable-flashpolicy": False,
          "service-enable-echows": False,
          "service-enable-ftp": False,
 
          ## system monitoring services
          "service-enable-netstat": True,
          "service-enable-vmstat": True,
 
          ## integration services
          "service-enable-restpusher": True,
          "service-enable-restremoter": True,
          "service-enable-pgpusher": True,
          "service-enable-pgremoter": True,
          "service-enable-orapusher": True,
          "service-enable-oraremoter": True,
          "service-enable-hanapusher": False,
          "service-enable-hanaremoter": False,
          "service-enable-extdirectremoter": False,
          }

      if not scratchMode:
         CONFIG.update({"database-created": created,
                        "admin-password": "secret"})

      ## default global configuration
      ##
      for k in CONFIG:
         cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", [k, json_dumps(CONFIG[k])])
      db.commit()

      ## default client permission: allow everything for anynonymous
      cur.execute("INSERT INTO clientperm (id, created, topic_uri, match_by_prefix, allow_publish, allow_subscribe) VALUES (?, ?, ?, ?, ?, ?)",
                  [newid(), utcnow(), "http://", 1, 1, 1])
      db.commit()

      if self.checkForOracleXE():
         log.msg("Inserting initial configuration for 'Tavendo WebMQ with Oracle XE'")
         oraConnectId = newid()
         now = utcnow()
         cur.execute("INSERT INTO oraconnect (id, created, label, host, port, sid, user, password, demo_user, demo_password, connection_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     [oraConnectId, now, "WebMQ", "127.0.0.1", 1521, "XE", "WEBMQ", "webmq", "WEBMQDEMO", "webmqdemo", 5])
         cur.execute("INSERT INTO orapushrule (id, created, oraconnect_id, topic_uri, match_by_prefix) VALUES (?, ?, ?, ?, ?)",
                     [newid(), now, oraConnectId, "http://", 1])
         cur.execute("INSERT INTO oraremote (id, created, oraconnect_id, schema_list, rpc_base_uri, connection_pool_min_size, connection_pool_max_size, connection_timeout, request_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     [newid(), now, oraConnectId, "", "http://", 3, 10, 5, 2])
         db.commit()

      log.msg("database initialized.")


   def checkForOracleXE(self):
      log.msg("Trying to detect locally running Oracle XE ..")
      try:
         import cx_Oracle
         dsn = cx_Oracle.makedsn("127.0.0.1", 1521, "XE")
         conn = cx_Oracle.connect("WEBMQ", "webmq", dsn)
         cur = conn.cursor()
         cur.execute("SELECT SYSTIMESTAMP AT TIME ZONE 'utc' FROM dual")
         res = cur.fetchone()
         log.msg("Oracle XE with WebMQ repository seems to be running on localhost [%s]." % res[0])
         return True
      except:
         log.msg("No Oracle XE is running on localhost or no WebMQ repository installed.")
         return False


   def getDatabaseInfo(self):
      """
      Get information about service database.
      """
      if os.path.isfile(self.dbfile):
         statinfo = os.stat(self.dbfile)
         size = statinfo.st_size
         modified = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(statinfo.st_mtime))
         db = sqlite3.connect(self.dbfile)
         cur = db.cursor()
         cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
         tables = []
         for r in cur.fetchall():
            tables.append(str(r[0]))
         info = {"file-path": self.dbfile,
                 "file-size": size,
                 "file-modified": modified,
                 "database-tables": tables}
         if "config" in tables:
            for a in ['database-version', 'database-created', 'instance-id']:
               cur.execute("SELECT value FROM config WHERE key = ?", [a])
               res = cur.fetchone()
               if res:
                  info[a] = json_loads(res[0])
               else:
                  return None
            info['host-id'] = "FIXME" # self.hostid
            return info
         else:
            return None
      else:
         return None


   def getConfig(self, key = None, includeTls = False, conn = None):
      """
      Get config from application database.
      """
      if not conn:
         conn = sqlite3.connect(self.dbfile)
      cur = conn.cursor()
      if key is None:
         cur.execute("SELECT key, value FROM config ORDER BY key")
         res = {}
         for r in cur.fetchall():
            res[r[0]] = json_loads(r[1])
         if includeTls:
            for t in Database.NETPORTS_TLS_PREFIXES:
               if res[t + "-tls"]:
                  cur.execute("SELECT key_priv, cert FROM servicekey WHERE id = ?", [res[t + "-tlskey"]])
                  res2 = cur.fetchone()
                  if res2:
                     res[t + "-tlskey-pem"] = res2[0]
                     res[t + "-tlscert-pem"] = res2[1]
         return res
      else:
         if type(key) in [str, unicode]:
            cur.execute("SELECT value FROM config WHERE key = ?", [key,])
            rs = cur.fetchone()
            if rs:
               return json_loads(rs[0])
            else:
               return None
         elif type(key) == list:
            cur.execute("SELECT key, value FROM config ORDER BY key")
            res = {}
            for r in cur.fetchall():
               if r[0] in key:
                  res[r[0]] = json_loads(r[1])
            return res
         else:
            return None


   def getWebAdminPort(self):
      """
      Get admin UI web port.
      """
      try:
         res = self.getConfig(["admin-web-port", "admin-web-tls"])
         return (res["admin-web-port"], res["admin-web-tls"])
      except:
         return (ADMIN_WEB_PORT_DEFAULT, False)


   def getWebAdminURL(self):
      adminport = self.getWebAdminPort()
      import socket
      hostname = socket.gethostname()
      return "http%s://%s:%s" % ('s' if adminport[1] else '', hostname, adminport[0])


   def getLicenseOptions(self):
      if self.licenseOptions is None:

         edition = 'oracle'
         #edition = 'appserver'

         opts = {'edition': edition,
                 ##
                 'tls': True,
                 'connections': 200000,
                 ##
                 'rest': True,
                 'extdirect': True,
                 'hana': True,
                 'oracle': True,
                 'postgresql': True}
         self.licenseOptions = opts
      return self.licenseOptions


   def getInstalledOptions(self):
      if self.installedOptions is None:

         opts = {}

         try:
            import pyodbc
            opts['hana'] = True
         except:
            opts['hana'] = False

         try:
            import cx_Oracle
            opts['oracle'] = True
         except:
            opts['oracle'] = False

         try:
            import psycopg2
            opts['postgresql'] = True
         except:
            opts['postgresql'] = False

         self.installedOptions = opts

      return self.installedOptions
