##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import datetime
from collections.abc import Mapping, Sequence

import six
import txaio
from twisted.internet.defer import inlineCallbacks, returnValue

from autobahn.util import utcstr
from autobahn.wamp.exception import ApplicationError
from crossbar.common import checkconfig
from crossbar.common.checkconfig import get_config_value

try:
    from txpostgres import txpostgres
    _HAS_POSTGRESQL = True
except ImportError:
    _HAS_POSTGRESQL = False

__all__ = ('PostgresConnectionPool', )

if _HAS_POSTGRESQL:

    class PostgreSQLConnection(object):
        """
        A PostgreSQL database connection pool.
        """

        log = txaio.make_logger()

        def __init__(self, id, config):
            """

            :param id: The ID of the connection item.
            :type id: unicode
            :param config: The connection item configuration.
            :type config: dict
            """
            self.id = id
            self.config = config
            self.started = None
            self.stopped = None

            params = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 5432),
                'database': config['database'],
                'user': config['user'],
                'password': get_config_value(config, 'password'),
            }
            self.pool = txpostgres.ConnectionPool(None, min=5, **params)

        def start(self):
            self.started = datetime.utcnow()
            return self.pool.start()

        def stop(self):
            self.stopped = datetime.utcnow()
            return self.pool.close()

        def marshal(self):
            return {
                u'id': self.id,
                u'started': utcstr(self.started),
                u'stopped': utcstr(self.stopped) if self.stopped else None,
                u'config': self.config,
            }


class PostgresConnectionPool(object):

    log = txaio.make_logger()

    def __init__(self, personality, session):
        self._personality = personality
        self._session = session
        self._connections = {}

    @staticmethod
    def check_connection(personality, connection, ignore=[]):
        """
        Check a connection item (such as a PostgreSQL or Oracle database connection pool).
        """
        if 'id' in connection:
            checkconfig.check_id(connection['id'])

        if 'type' not in connection:
            raise checkconfig.InvalidConfigException("missing mandatory attribute 'type' in connection configuration")

        valid_types = ['postgres']
        if connection['type'] not in valid_types:
            raise checkconfig.InvalidConfigException(
                "invalid type '{}' for connection type - must be one of {}".format(connection['type'], valid_types))

        if connection['type'] == 'postgres':
            checkconfig.check_dict_args(
                {
                    'id': (False, [six.text_type]),
                    'type': (True, [six.text_type]),
                    'host': (False, [six.text_type]),
                    'port': (False, six.integer_types),
                    'database': (True, [six.text_type]),
                    'user': (True, [six.text_type]),
                    'password': (False, [six.text_type]),
                    'options': (False, [Mapping]),
                }, connection, "PostgreSQL connection configuration")

            if 'port' in connection:
                checkconfig.check_endpoint_port(connection['port'])

            if 'options' in connection:
                checkconfig.check_dict_args(
                    {
                        'min_connections': (False, six.integer_types),
                        'max_connections': (False, six.integer_types),
                    }, connection['options'], "PostgreSQL connection options")

        else:
            raise checkconfig.InvalidConfigException('logic error')

    @staticmethod
    def check_connections(personality, connections):
        """
        Connections can be present in controller, router and container processes.
        """
        if not isinstance(connections, Sequence):
            raise checkconfig.InvalidConfigException("'connections' items must be lists ({} encountered)".format(
                type(connections)))

        for i, connection in enumerate(connections):
            personality.check_connection(personality, connection)

    @inlineCallbacks
    def start_connection(self, id, config, details=None):
        """
        Starts a connection in this process.

        :param id: The ID for the started connection.
        :type id: unicode

        :param config: Connection configuration.
        :type config: dict

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: The connection.
        """
        self.log.debug("start_connection: id={id}, config={config}", id=id, config=config)

        # prohibit starting a component twice
        #
        if id in self._connections:
            emsg = "cannot start connection: a connection with id={} is already started".format(id)
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # check configuration
        #
        try:
            self._personality.check_connection(self._personality, config)
        except Exception as e:
            emsg = "invalid connection configuration ({})".format(e)
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
        else:
            self.log.info("Starting {ptype} in process.", ptype=config['type'])

        if config['type'] == u'postgresql.connection':
            if _HAS_POSTGRESQL:
                connection = PostgreSQLConnection(id, config)
            else:
                emsg = "unable to start connection - required PostgreSQL driver package not installed"
                self.log.warn(emsg)
                raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)
        else:
            # should not arrive here
            raise Exception("logic error")

        self._connections[id] = connection

        try:
            yield connection.start()
            self.log.info("Connection {connection_type} started '{connection_id}'",
                          connection_id=id,
                          connection_type=config['type'])
        except:
            del self._connections[id]
            raise

        state = connection.marshal()

        self._session.publish(u'crossbar.node.process.on_connection_start', state)

        returnValue(state)

    @inlineCallbacks
    def stop_connection(self, id, details=None):
        """
        Stop a connection currently running within this process.

        :param id: The ID of the connection to stop.
        :type id: unicode

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: A dict with component start information.
        """
        self.log.debug("stop_connection: id={id}", id=id)

        if id not in self._connections:
            raise ApplicationError(u'crossbar.error.no_such_object',
                                   'no connection with ID {} running in this process'.format(id))

        connection = self._connections[id]

        try:
            yield connection.stop()
        except Exception as e:
            self.log.warn('could not stop connection {id}: {error}', error=e)
            raise

        del self._connections[id]

        state = connection.marshal()

        self._session.publish(u'crossbar.node.process.on_connection_stop', state)

        returnValue(state)

    def get_connections(self, details=None):
        """
        Get connections currently running within this processs.

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: List of connections.
        """
        self.log.debug("get_connections")

        res = []
        for c in self._connections.values():
            res.append(c.marshal())
        return res
