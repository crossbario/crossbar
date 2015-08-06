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

from autobahn.wamp.types import PublishOptions

from crossbar._logging import make_logger
from crossbar.adapter.postgres.common import PostgreSQLAdapter

__all__ = ('PostgreSQLPublisher',)


class PostgreSQLPublisher(PostgreSQLAdapter):

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

    PG_CHANNEL = "crossbar_publish"
    """
    The PostgreSQL NOTIFY channel used for Crossbar.io PubSub events
    sent from within the database.
    """

    def on_notify(self, notify):
        """
        Process PostgreSQL notifications sent via `NOTIFY` on channel `self.PG_CHANNEL`.
        """

        # sanity check that we are processing the correct channel
        #
        if notify.channel == self.PG_CHANNEL:
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
    runner.run(PostgreSQLPublisher)
