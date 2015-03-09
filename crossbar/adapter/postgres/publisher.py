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

import json
import six
import re
import os
from txpostgres import txpostgres

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession


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

    SELECT pg_notify('crossbar_pubsub_event',
       json_build_object(
          'type', 'direct',
          'topic', 'com.example.topic1',
          'args', json_build_array(23, 7, 'hello world!'),
          'kwargs', json_build_object('foo', 'bar', 'baz', 42)
       )::text
    );

    Above is bypassing the wrapper API that comes with Crossbar.io, which could
    be used to do the same as above like this:

    SELECT cb_publish(
       'com.example.topic1',
       json_build_array(23, 7, 'hello world!'),
       json_build_object('foo', 'bar', 'baz', 42))
    );

    See also:

       * http://www.postgresql.org/docs/devel/static/functions-json.html
    """

    CHANNEL_PUBSUB_EVENT = "crossbar_pubsub_event"
    """
   The PostgreSQL NOTIFY channel used for Crossbar.io PubSub events
   sent from within the database.
   """

    @inlineCallbacks
    def onJoin(self, details):

        print("PostgreSQL database adapter [publisher role] connected to router")

        dbconfig = self.config.extra['database']

        # check if the config contains environment variables instead of
        # straight strings (e.g. $DBNAME), and if so, try to fill in the actual
        # value from environment
        #
        pat = re.compile("^\$([A-Z0-9_]+)$")
        for k in ['host', 'port', 'database', 'user', 'password']:
            if k in dbconfig:
                if type(dbconfig[k]) in (str, unicode):
                    match = pat.match(dbconfig[k])
                    if match and match.groups():
                        envvar = match.groups()[0]
                        if envvar in os.environ:
                            dbconfig[k] = os.environ[envvar]
                            if k != 'password':
                                val = dbconfig[k]
                            else:
                                val = len(dbconfig[k]) * '*'
                            print("database configuration parameter '{}' set to '{}' from environment variable {}".format(k, val, envvar))
                        else:
                            print("warning: database configuration parameter '{}' should have been read from enviroment variable {}, but the latter is not set".format(k, envvar))

        conn = txpostgres.Connection()

        try:
            yield conn.connect(**dbconfig)
        except Exception as e:
            print("could not connect to database: {0}".format(e))
            self.leave()
            return
        else:
            print("PostgreSQL database adapter [publisher role] connected to database")

        conn.addNotifyObserver(self._on_notify)
        try:
            yield conn.runOperation("LISTEN {0}".format(self.CHANNEL_PUBSUB_EVENT))
        except Exception as e:
            print("failed to listen on channel '{0}': {1}".format(self.CHANNEL_PUBSUB_EVENT, e))
            self.leave()
        else:
            print("ok, pusher is listening on PostgreSQL NOTIFY channel '{0}'' ...".format(self.CHANNEL_PUBSUB_EVENT))

    def onLeave(self, details):
        print("session closed")
        self.disconnect()

    def onDisconnect(self):
        print("disconnected")

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
                if obj['type'] not in ['direct', 'table']:
                    raise Exception("notification payload 'type' must be one of ['direct', 'table'], was '{0}'".format(obj['type']))

                if obj['type'] == 'direct':

                    # check allowed attributes
                    #
                    for k in obj:
                        if k not in ['type', 'topic', 'args', 'kwargs', 'exclude', 'eligible']:
                            raise Exception("invalid attribute '{0}'' in notification of type 'direct'".format(k))

                    # check for mandatory 'topic' attribute
                    #
                    if 'topic' not in obj:
                        raise Exception("notification payload of type 'direct' must have a 'topic' attribute")
                    topic = obj['topic']
                    if not isinstance(topic, six.text_type):
                        raise Exception("notification payload of type 'direct' must have a 'topic' attribute of type string - was {0}".format(type(obj['topic'])))

                    # check for optional 'args' attribute
                    #
                    args = None
                    if 'args' in obj:
                        if not isinstance(obj['args'], list):
                            raise Exception("notification payload of type 'direct' with wrong type for 'args' attribute: must be list, was {0}".format(obj['args']))
                        else:
                            args = obj['args']

                    # check for optional 'args' attribute
                    #
                    kwargs = None
                    if 'kwargs' in obj:
                        if not isinstance(obj['kwargs'], dict):
                            raise Exception("notification payload of type 'direct' with wrong type for 'kwargs' attribute: must be dict, was {0}".format(obj['kwargs']))
                        else:
                            kwargs = obj['kwargs']

                    # now actually publish the WAMP event
                    #
                    if kwargs:
                        self.publish(topic, *args, **kwargs)
                    elif args:
                        self.publish(topic, *args)
                    else:
                        self.publish(topic)

                    print("event published to topic {0}".format(topic))

                elif obj['type'] == 'table':
                    raise Exception("notification payload type 'table' not implemented")
                else:
                    raise Exception("logic error")

            except Exception as e:
                print e
        else:
            print "unknown channel"


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
