#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import re
import os
import pkg_resources

from twisted.internet.defer import inlineCallbacks, returnValue

from txpostgres import txpostgres

from autobahn.twisted.wamp import ApplicationSession

from crossbar._logging import make_logger


class PostgreSQLAdapter(ApplicationSession):
    """
    Abstract base class for PostgreSQL-WAMP integration.
    """

    log = make_logger()

    PG_LOCK_GROUP = 6000
    """
    This is the common, shared `key1` part of advisory locks acquired by Crossbar.io PostgreSQL adapter classes.
    """

    PG_LOCK_UPGRADE = 1
    """
    This lock will be held during database schema upgrades.
    """

    PG_CHANNEL = ''

    @inlineCallbacks
    def onJoin(self, details):
        self.log.debug("Joined realm '{realm}' on router", realm=details.realm)

        self._db_config = self.resolve_config(self.config.extra['database'])
        self._db_config['application_name'] = "Crossbar.io PostgreSQL Adapter (Publisher)"
        self._db_config['scripts'] = os.path.abspath(pkg_resources.resource_filename("crossbar", "adapter/postgres/ddl"))
        self._db_config['adapter_xlock'] = 100
        self._db_config['adapter_channel'] = self.PG_CHANNEL

        self.log.debug("Using database configuration {db_config}", db_config=self._db_config)
        self.log.debug("Using DDL script directory {ddl_scripts_dir}", ddl_scripts_dir=self._db_config['scripts'])

        try:
            yield self.connect_and_observe(self._db_config, self.PG_CHANNEL, self.on_notify)
        except Exception as e:
            self.log.error("Could not connect to database: {error}", error=e)
            self.leave()

        self.log.info("PostgreSQL database adapter (Publisher) ready")

    def onLeave(self, details):
        self.log.debug("Left realm - {}".format(details))
        self.disconnect()

    def onDisconnect(self):
        self.log.info("PostgreSQL database adapter (Publisher) stopped")

    def resolve_config(self, db_config):
        # check if the config contains environment variables instead of
        # straight strings (e.g. $DBNAME), and if so, try to fill in the actual
        # value from environment
        #
        pat = re.compile("^\$([A-Z0-9_]+)$")
        for k in ['host', 'port', 'database', 'user', 'password']:
            if k in db_config:
                if type(db_config[k]) in (str, unicode):
                    match = pat.match(db_config[k])
                    if match and match.groups():
                        envvar = match.groups()[0]
                        if envvar in os.environ:
                            db_config[k] = os.environ[envvar]
                            if k != 'password':
                                val = db_config[k]
                            else:
                                val = len(db_config[k]) * '*'
                            self.log.debug("Database configuration parameter '{}' set to '{}' from environment variable {}".format(k, val, envvar))
                        else:
                            self.log.warn("Database configuration parameter '{}' should have been read from enviroment variable {}, but the latter is not set".format(k, envvar))
        return db_config

    @inlineCallbacks
    def connect_and_observe(self, db_config, channel, fun):

        # connect to database
        #
        conn = txpostgres.Connection()

        db_conn_params = {
            'user': db_config['user'],
            'password': db_config['password'],
            'host': db_config['host'],
            'port': db_config['port'],
            'database': db_config['database'],
        }

        try:
            yield conn.connect(**db_conn_params)
        except Exception as e:
            raise Exception("database connection failed: {}".format(e))
        else:
            self.log.debug("Connected to database")

        # acquire exclusive run lock
        #
        res = yield conn.runQuery("SELECT pg_try_advisory_lock(%s, %s)", (self.PG_LOCK_GROUP, db_config['adapter_xlock']))
        if not res[0][0]:
            locker_pid, locker_user_id, locker_user_name, locker_app_name = None, None, None, None
            res = yield conn.runQuery("SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND classid = %s AND objid = %s", (self.PG_LOCK_GROUP, db_config['adapter_xlock']))
            if res:
                locker_pid = res[0][0]
            if locker_pid:
                res = yield conn.runQuery("SELECT usesysid, usename, application_name FROM pg_stat_activity WHERE pid = %s", (locker_pid,))
                if res:
                    locker_user_id, locker_user_name, locker_app_name = res[0]

            self.log.error('A database session already holds the run lock for us (pid={pid}, userid={userid}, username={username}, appname="{appname}")', pid=locker_pid, userid=locker_user_id, username=locker_user_name, appname=locker_app_name)
            raise Exception("Only one instance of this adapter can be connected to a given database")
        else:
            self.log.debug("Obtained exclusive run lock on ({key1}, {key2})", key1=self.PG_LOCK_GROUP, key2=db_config['adapter_xlock'])

        # upgrade database schema if needed
        #
        schema_version = yield self._check_and_upgrade_schema(db_config, conn)
        self.log.info("Running on schema version {schema_version}", schema_version=schema_version)

        # add channel listener
        #
        conn.addNotifyObserver(fun)
        try:
            yield conn.runOperation("LISTEN {0}".format(self._db_config['adapter_channel']))
        except Exception as e:
            self.log.error("Failed to listen on channel '{0}': {1}".format(self._db_config['adapter_channel'], e))
            self.leave()
        else:
            self.log.debug("Listening on PostgreSQL NOTIFY channel '{0}'' ...".format(self._db_config['adapter_channel']))

    @inlineCallbacks
    def _check_and_upgrade_schema(self, db_config, conn):
        # check that schema 'crossbar' exists and is owned by the connecting user
        #
        res = yield conn.runQuery("SELECT nspowner FROM pg_catalog.pg_namespace WHERE nspname = 'crossbar'")
        if len(res) < 1:
            raise Exception("No schema 'crossbar' exists in database")
        else:
            owner_oid = res[0][0]
            self.log.debug("Schema is owned by user with OID {owner_oid}", owner_oid=owner_oid)

        res = yield conn.runQuery("SELECT usename FROM pg_user WHERE usesysid = %s", (owner_oid,))
        if len(res) < 1 or res[0][0] != db_config['user']:
            raise Exception("Schema 'crossbar' exists, but is not owned by connecting user '{}'".format(db_config['user']))
        else:
            self.log.debug("Schema is owned by the user '{user}' we are connecting under", user=db_config['user'])

        # check if table 'crossbar.meta' exists (and is owned by the connecting user)
        #
        res = yield conn.runQuery("SELECT tableowner FROM pg_tables WHERE schemaname = 'crossbar' AND tablename = 'meta'")
        if len(res) < 1:
            # full install
            current_version = 0
        else:
            owner = res[0][0]
            if owner != db_config['user']:
                raise Exception("Table 'crossbar.meta' exists, but is not owned by connecting user '{}'".format(db_config['user']))

            # get the schema version
            #
            res = yield conn.runQuery("SELECT value FROM crossbar.meta WHERE key = 'schema_version'")
            if len(res) < 1:
                current_version = 0
            else:
                current_version = res[0][0]

        # get the latest schema version from DDL scripts as well as map of DDL upgrade scripts
        #
        latest_version, upgrade_scripts = self._get_latest_schema_version(db_config['scripts'])

        # upgrade schema version-wise, running each upgrade in it's own transaction
        #
        for from_version in range(current_version, latest_version):
            yield self._upgrade_schema(conn, db_config['scripts'], upgrade_scripts, from_version, from_version + 1)

        current_version = latest_version

        returnValue(current_version)

    def _get_latest_schema_version(self, scripts_dir):
        """
        Determine latest available database schema version available from DDL scripts,
        and build a map of (from_version, to_version) -> (part -> script)
        """
        latest_version = 0
        upgrade_scripts = {}
        pat = re.compile(r"^upgrade_(\d)_(\d)_(\d).sql$")
        for fn in os.listdir(scripts_dir):
            m = pat.match(fn)
            if m:
                from_version, to_version, part = m.groups()
                from_version = int(from_version)
                to_version = int(to_version)
                part = int(part)
                if (from_version, to_version) not in upgrade_scripts:
                    upgrade_scripts[(from_version, to_version)] = {}
                upgrade_scripts[(from_version, to_version)][part] = fn
                if to_version > latest_version:
                    latest_version = to_version
        return latest_version, upgrade_scripts

    def _upgrade_schema(self, conn, scripts_dir, upgrade_scripts, from_version, to_version):
        """
        Upgrade database schema in a transaction.
        """
        scripts = upgrade_scripts[(from_version, to_version)]

        @inlineCallbacks
        def upgrade(txn):
            for part in sorted(scripts.keys()):
                script = os.path.join(scripts_dir, scripts[part])

                self.log.debug("Running schema upgrade script {script}", script=script)
                with open(script) as f:
                    sql = f.read()
                    sql = str(sql)
                    try:
                        yield txn.execute(sql)
                    except Exception as e:
                        self.log.error("Error while running DDL script '{script}': {error}", script=script, error=e)

        return conn.runInteraction(upgrade)

    def on_notify(self, notify):
        """
        Process PostgreSQL notifications sent via `NOTIFY` on channel `self.CHANNEL_PUBSUB_EVENT`.
        """
