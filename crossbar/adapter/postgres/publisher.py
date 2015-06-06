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

from __future__ import absolute_import, print_function

import json
import six
import re
import os
import pkg_resources
from txpostgres import txpostgres

from twisted.internet.defer import inlineCallbacks, returnValue

from autobahn.wamp.types import PublishOptions
from autobahn.twisted.wamp import ApplicationSession

from crossbar._logging import make_logger


class PostgreSQLDatabasePublisher(ApplicationSession):

    """
    PostgreSQL database adapter that allows publishing of WAMP real-time
    events from within the database, e.g. from SQL or PL/pgSQL.

    WAMP Publish & Subscribe events can be issued from SQL or PL/pgSQL (or
    any other PostgreSQL procedural language) and is dispatched in real-time
    by Crossbar.io to all subscribers authorized and eligible to receiving
    the event.

    Effectively, this adapter implements a WAMP Publisher Role for PostgreSQL.

    A WAMP Publish & Subcribe event can be issued from a PostgreSQL database
    session like this:

    ```sql
    SELECT crossbar.publish(
       'com.example.topic1',
       json_build_array(23, 7, 'hello world!')::jsonb
    );

    See also:

       * http://www.postgresql.org/docs/devel/static/functions-json.html
    """

    log = make_logger()

    CHANNEL_PUBSUB_EVENT = "crossbar_publish"
    """
    The PostgreSQL NOTIFY channel used for Crossbar.io PubSub events
    sent from within the database.
    """

    DDL_SCRIPTS_DIR = os.path.abspath(pkg_resources.resource_filename("crossbar", "adapter/postgres/ddl"))

    @inlineCallbacks
    def onJoin(self, details):

        self.log.debug("Joined realm '{realm}' on router", realm=details.realm)
        self.log.debug("Using DDL script directory {ddl_scripts_dir}", ddl_scripts_dir=self.DDL_SCRIPTS_DIR)

        self._db_config = self.config.extra['database']

        # check if the config contains environment variables instead of
        # straight strings (e.g. $DBNAME), and if so, try to fill in the actual
        # value from environment
        #
        pat = re.compile("^\$([A-Z0-9_]+)$")
        for k in ['host', 'port', 'database', 'user', 'password']:
            if k in self._db_config:
                if type(self._db_config[k]) in (str, unicode):
                    match = pat.match(self._db_config[k])
                    if match and match.groups():
                        envvar = match.groups()[0]
                        if envvar in os.environ:
                            self._db_config[k] = os.environ[envvar]
                            if k != 'password':
                                val = self._db_config[k]
                            else:
                                val = len(self._db_config[k]) * '*'
                            self.log.debug("Database configuration parameter '{}' set to '{}' from environment variable {}".format(k, val, envvar))
                        else:
                            self.log.warn("Database configuration parameter '{}' should have been read from enviroment variable {}, but the latter is not set".format(k, envvar))

        self.log.debug("Using database configuration {db_config}", db_config=self._db_config)

        # connect to database
        #
        conn = txpostgres.Connection()

        try:
            yield conn.connect(**self._db_config)
        except Exception as e:
            self.log.error("Could not connect to database: {0}".format(e))
            self.leave()
            return
        else:
            self.log.debug("Connected to database")

        # upgrade database schema if needed
        #
        schema_version = yield self._check_and_upgrade_schema(conn)
        self.log.info("Running on schema version {schema_version}", schema_version=schema_version)

        # add channel listener
        #
        conn.addNotifyObserver(self._on_notify)
        try:
            yield conn.runOperation("LISTEN {0}".format(self.CHANNEL_PUBSUB_EVENT))
        except Exception as e:
            self.log.error("Failed to listen on channel '{0}': {1}".format(self.CHANNEL_PUBSUB_EVENT, e))
            self.leave()
        else:
            self.log.debug("Listening on PostgreSQL NOTIFY channel '{0}'' ...".format(self.CHANNEL_PUBSUB_EVENT))

        self.log.info("PostgreSQL database adapter (Publisher) ready")

    @inlineCallbacks
    def _check_and_upgrade_schema(self, conn):
        # check that schema 'crossbar' exists and is owned by the connecting user
        #
        res = yield conn.runQuery("SELECT nspowner FROM pg_catalog.pg_namespace WHERE nspname = 'crossbar'")
        if len(res) < 1:
            raise Exception("No schema 'crossbar' exists in database")
        else:
            owner_oid = res[0][0]
            self.log.debug("Schema is owned by user with OID {owner_oid}", owner_oid=owner_oid)

        res = yield conn.runQuery("SELECT usename FROM pg_user WHERE usesysid = %s", (owner_oid,))
        if len(res) < 1 or res[0][0] != self._db_config['user']:
            raise Exception("Schema 'crossbar' exists, but is not owned by connecting user '{}'".format(self._db_config['user']))
        else:
            self.log.debug("Schema is owned by the user '{user}' we are connecting under", user=self._db_config['user'])

        # check if table 'crossbar.meta' exists (and is owned by the connecting user)
        #
        res = yield conn.runQuery("SELECT tableowner FROM pg_tables WHERE schemaname = 'crossbar' AND tablename = 'meta'")
        if len(res) < 1:
            # full install
            current_version = 0
        else:
            owner = res[0][0]
            if owner != self._db_config['user']:
                raise Exception("Table 'crossbar.meta' exists, but is not owned by connecting user '{}'".format(self._db_config['user']))

            # get the schema version
            #
            res = yield conn.runQuery("SELECT value FROM crossbar.meta WHERE key = 'schema_version'")
            if len(res) < 1:
                current_version = 0
            else:
                current_version = res[0][0]

        latest_version, upgrade_scripts = self._get_latest_schema_version()
        for from_version in range(current_version, latest_version):
            yield self._upgrade_schema(conn, upgrade_scripts, from_version, from_version + 1)

        current_version = latest_version

        returnValue(current_version)

    def _get_latest_schema_version(self):
        latest_version = 0
        upgrade_scripts = {}
        pat = re.compile(r"^upgrade_(\d)_(\d)_(\d).sql$")
        for fn in os.listdir(self.DDL_SCRIPTS_DIR):
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

    def _upgrade_schema(self, conn, upgrade_scripts, from_version, to_version):
        scripts = upgrade_scripts[(from_version, to_version)]

        @inlineCallbacks
        def upgrade(txn):
            for part in sorted(scripts.keys()):
                script = os.path.join(self.DDL_SCRIPTS_DIR, scripts[part])

                self.log.debug("Running schema upgrade script {script}", script=script)
                with open(script) as f:
                    sql = f.read()
                    try:
                        yield txn.execute(sql)
                    except Exception as e:
                        self.log.error("Error while running DDL script '{script}': {error}", script=script, error=e)

        return conn.runInteraction(upgrade)

    def onLeave(self, details):
        self.log.debug("Left realm - {}".format(details))
        self.disconnect()

    def onDisconnect(self):
        self.log.info("PostgreSQL database adapter (Publisher) stopped")

    def _on_notify(self, notify):
        # process PostgreSQL notifications sent via NOTIFY
        #

        # PID of the PostgreSQL backend that issued the NOTIFY
        #
        # pid = notify.pid

        # sanity check that we are processing the correct channel
        #
        if notify.channel == self.CHANNEL_PUBSUB_EVENT:
            try:
                obj = json.loads(notify.payload)

                if not isinstance(obj, dict):
                    raise Exception("notification payload must be a dictionary, was type {0}".format(type(obj)))

                # check for mandatory 'type' attribute
                #
                if 'type' not in obj:
                    raise Exception("notification payload must have a 'type' attribute")
                if obj['type'] not in ['inline', 'buffered']:
                    raise Exception("notification payload 'type' must be one of ['inline', 'buffered'], was '{0}'".format(obj['type']))

                if obj['type'] == 'inline':

                    # check allowed attributes
                    #
                    for k in obj:
                        if k not in ['type', 'topic', 'args', 'kwargs', 'options', 'details']:
                            raise Exception("invalid attribute '{0}'' in notification of type 'inline'".format(k))

                    # check for mandatory 'topic' attribute
                    #
                    if 'topic' not in obj:
                        raise Exception("notification payload of type 'inline' must have a 'topic' attribute")
                    topic = obj['topic']
                    if not isinstance(topic, six.text_type):
                        raise Exception("notification payload of type 'inline' must have a 'topic' attribute of type string - was {0}".format(type(obj['topic'])))

                    # check for optional 'args' attribute
                    #
                    args = None
                    if 'args' in obj and obj['args']:
                        if not isinstance(obj['args'], list):
                            raise Exception("notification payload of type 'inline' with wrong type for 'args' attribute: must be list, was {0}".format(obj['args']))
                        else:
                            args = obj['args']

                    # check for optional 'kwargs' attribute
                    #
                    kwargs = None
                    if 'kwargs' in obj and obj['kwargs']:
                        if not isinstance(obj['kwargs'], dict):
                            raise Exception("notification payload of type 'inline' with wrong type for 'kwargs' attribute: must be dict, was {0}".format(obj['kwargs']))
                        else:
                            kwargs = obj['kwargs']

                    # check for optional 'options' attribute
                    #
                    options = None
                    if 'options' in obj and obj['options']:
                        if not isinstance(obj['options'], dict):
                            raise Exception("notification payload of type 'inline' with wrong type for 'options' attribute: must be dict, was {0}".format(obj['options']))
                        else:
                            try:
                                options = PublishOptions(**(obj['options']))
                            except Exception as e:
                                raise Exception("notification payload of type 'inline' with invalid attribute in 'options': {0}".format(e))

                    # check for optional 'details' attribute
                    #
                    details = None
                    if 'details' in obj and obj['details']:
                        if not isinstance(obj['details'], dict):
                            raise Exception("notification payload of type 'inline' with wrong type for 'details' attribute: must be dict, was {0}".format(obj['details']))
                        else:
                            details = obj['details']

                    # now actually publish the WAMP event
                    #
                    if options:
                        if kwargs:
                            args = args or []
                            self.publish(topic, *args, options=options, **kwargs)
                        elif args:
                            self.publish(topic, *args, options=options)
                        else:
                            self.publish(topic, options=options)
                    else:
                        if kwargs:
                            args = args or []
                            self.publish(topic, *args, **kwargs)
                        elif args:
                            self.publish(topic, *args)
                        else:
                            self.publish(topic)

                    # self.log.debug('Event forwarded on topic "{topic}" with options {options} and details {details}: args={args}, kwargs={kwargs}', topic=topic, options=options, details=details, args=args, kwargs=kwargs)
                    self.log.debug('Event forwarded to topic "{topic}" (options={options}) with args={args} and kwargs={kwargs}', topic=topic, options=options, details=details, args=args, kwargs=kwargs)

                elif obj['type'] == 'buffered':
                    raise Exception("notification payload type 'buffered' not implemented")

                else:
                    raise Exception("logic error")

            except Exception as e:
                self.log.error(e)

        else:
            self.log.error("Received NOTIFY on unknown channel {channel}", channel=notify.channel)


if __name__ == '__main__':
    from autobahn.twisted.choosereactor import install_reactor
    from autobahn.twisted.wamp import ApplicationRunner

    import sys
    if sys.platform == 'win32':
        # IOCPReactor does did not implement addWriter: use select reactor
        install_reactor('select')
    else:
        install_reactor()

    config = {
        'database': {
            'host': u'127.0.0.1',
            'port': 5432,
            'port': u'$DBPORT',
            'database': u'test',
            #         'user': u'$DBUSER',
            'user': u'testuser',
            'password': u'$DBPASSWORD'
            #         'password': u'testuser'
        }
    }

    runner = ApplicationRunner(url="ws://127.0.0.1:8080/ws",
                               realm="realm1", extra=config)
    runner.run(PostgreSQLDatabasePublisher)
