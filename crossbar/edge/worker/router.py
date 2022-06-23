##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import six
from typing import Dict

from txaio import make_logger

from twisted.internet import reactor

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions

from crossbar._util import hl, hltype

from crossbar.worker.router import RouterController
from crossbar.worker.types import RouterRealm
from crossbar.router.router import RouterFactory, Router

from crossbar.edge.worker.tracing import FabricRouterTrace

__all__ = ('ExtRouterController', )


class RouterRealmInterface(object):
    def __init__(self, id, config):
        self.id = id
        self.config = config


class RouterInterface(object):
    def __init__(self, router, uri):
        self.router = router
        self.uri = uri


class ExtRouter(Router):
    """
    Router extended with crossbar features.
    """
    def __init__(self, factory, realm, options=None, store=None):
        Router.__init__(self, factory, realm, options, store)
        self._interfaces = {}

    def has_interface(self, uri):
        return uri in self._interfaces

    def add_interface(self, interface):
        overwritten = interface.uri in self._interfaces
        self._interfaces[interface.uri] = interface
        return overwritten

    def drop_interface(self, interface):
        if interface.uri in self._interfaces:
            del self._interfaces[interface.uri]
            return True
        return False


class ExtRouterFactory(RouterFactory):
    """
    Router factory extended with crossbar features.
    """
    router = ExtRouter  # type: ignore

    def __init__(self, node_id, worker, options=None):
        RouterFactory.__init__(self, node_id, worker, options=options)
        self._routers: Dict[str, ExtRouter] = {}

    def add_interface(self, realm, interface):
        assert (type(realm) == six.text_type)
        assert (realm in self._routers)

        router_ = self._routers[realm]
        router_.add_interface(RouterInterface(router_, interface['uri']))

    def drop_interface(self, realm, interface_id):
        assert (type(realm) == six.text_type)
        assert (type(interface_id) == six.text_type)

        if realm not in self._routers:
            raise Exception('no router started for realm "{}"'.format(realm))

        router = self._routers[realm]

        if interface_id not in router._interfaces:
            raise Exception('no interface "{}" started on router for realm "{}"'.format(interface_id, realm))

        interface_id = router._interfaces[interface_id]
        router.drop_interface(interface_id)


class ExtRouterRealm(RouterRealm):
    """
    Router realm run-time representation, extended with crossbar features:

    1. router links
    2. interfaces
    """
    def __init__(self, controller, realm_id, config, router=None, session=None):
        """

        :param controller:

        :param realm_id: The realm ID within the router.
        :type realm_id: str

        :param config: The realm configuration.
        :type config: dict

        :param router: The router (within the router worker) serving the realm.
        :type router: :class:`crossbar.edge.worker.router.ExtRouter`

        :param session: The realm service session.
        :type session: :class:`crossbar.router.service.RouterServiceAgent`
        """
        RouterRealm.__init__(self, controller, realm_id, config, router=router, session=session)

        # FIXME
        self.interfaces = {}

    def marshal(self):
        marshalled = RouterRealm.marshal(self)

        # FIXME
        marshalled['interfaces'] = self.interfaces

        return marshalled


class ExtRouterController(RouterController):
    """
    Controller session for crossbar router workers.
    """

    log = make_logger()

    def __init__(self, config=None, reactor=None, personality=None):
        RouterController.__init__(self, config=config, reactor=reactor, personality=personality)

        # router factory / realm classes to be used
        self.router_factory_class = ExtRouterFactory
        self.router_realm_class = ExtRouterRealm

        # map: trace ID -> RouterTrace
        self._traces = {}

        # when users don't provide a trace_id, draw from this enumerator
        self._next_trace = 1

    @wamp.register(None)
    def start_router_realm(self, realm_id, realm_config, details=None):
        self.log.info('Starting router realm "{realm_id}" {method}',
                      realm_id=realm_id,
                      method=hltype(ExtRouterController.start_router_realm))

        # activate this to test:
        if False and realm_config['name'] == 'realm1':
            self.log.info(hl('Auto-renaming realm1 to realm001', color='green', bold=True))
            realm_config['name'] = 'realm001'

        return RouterController.start_router_realm(self, realm_id, realm_config, details)

    def _next_trace_id(self):
        while True:
            trace_id = u'trace{}'.format(self._next_trace)
            self._next_trace += 1
            if trace_id not in self._traces:
                return trace_id

    def _maybe_trace_rx_msg(self, session, msg):
        if self._traces:
            for trace in self._traces.values():
                trace.maybe_trace_rx_msg(session, msg)

    def _maybe_trace_tx_msg(self, session, msg):
        if self._traces:
            for trace in self._traces.values():
                trace.maybe_trace_tx_msg(session, msg)

    @wamp.register(None)
    def get_traces(self, include_stopped=False, details=None):
        self.log.debug('get_traces(inclue_stopped="{include_stopped}")', include_stopped=include_stopped)

        return sorted(self._traces.keys())

    @wamp.register(None)
    def get_trace(self, trace_id, details=None):
        self.log.debug('get_trace(trace_id="{trace_id}")', trace_id=trace_id)

        if trace_id not in self._traces:
            raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))

        return self._traces[trace_id].marshal()

    @wamp.register(None)
    def start_trace(self, trace_id=None, trace_options=None, details=None):
        self.log.info('start_trace(trace_id="{trace_id}", trace_options="{trace_options}")',
                      trace_id=trace_id,
                      trace_options=trace_options)

        assert (trace_id is None or type(trace_id) == six.text_type)
        assert (trace_options is None or type(trace_options) == dict)

        trace_id = trace_id or self._next_trace_id()
        trace_options = trace_options or {}

        # tracing level: u'message' (default) or u'action'
        trace_level = trace_options.get(u'trace_level', u'message')
        if trace_level not in [u'message', u'action']:
            emsg = 'invalid tracing options: trace_level must be one of ["message", "action"], but was "{}"'.format(
                trace_level)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # flag to control tracing of app _payload_
        trace_app_payload = trace_options.get(u'trace_app_payload', False)
        if type(trace_app_payload) != bool:
            emsg = 'invalid tracing options: trace_app_payload must be of type bool, was {}'.format(
                type(trace_app_payload))
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # tracing app payload only makes sense for trace_level == u'message'
        if trace_app_payload and trace_level != u'message':
            emsg = 'invalid tracing options: when trace_app_payload is set, trace_level must be "message", but was "{}"'.format(
                trace_level)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # parameter to control batching of trace records (in ms)
        batching_period = trace_options.get(u'batching_period', 200)
        if type(batching_period) not in six.integer_types or batching_period < 10 or batching_period > 10000:
            emsg = 'invalid tracing options: batching_period must be an integer [10, 10000], was "{}"'.format(
                type(batching_period))
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # flag to control tracing persistence
        persist = trace_options.get(u'persist', False)
        if type(persist) != bool:
            emsg = 'invalid tracing options: persist must be of type bool, was {}'.format(type(persist))
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # parameter to control trace duration (in secs): if given, automatically stop the trace
        # after the given period of time. if not given, the trace runs until stopped explicitly
        duration = trace_options.get(u'duration', None)
        if duration is not None and (type(duration) not in six.integer_types or duration < 1 or duration > 86400):
            emsg = 'invalid tracing options: duration must be an integer [1, 86400], was "{}"'.format(type(duration))
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # check user provided trace_id
        if trace_id in self._traces:
            emsg = 'could not start trace: a trace with ID "{}" is already running (or starting)'.format(trace_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        def on_trace_period_finished(trace_id, period, trace_batch):
            if trace_level == u'message':
                trace_data = [trace_record.marshal(self._trace_app_payload) for trace_record in trace_batch]
            elif trace_level == u'action':
                trace_data = [traced_action.marshal() for traced_action in trace_batch]
            else:
                raise Exception('logic error')

            self.publish(u'{}.on_trace_data'.format(self._uri_prefix), trace_id, period, trace_data)

        trace = FabricRouterTrace(self,
                                  trace_id,
                                  on_trace_period_finished=on_trace_period_finished,
                                  trace_level=trace_level,
                                  trace_app_payload=trace_app_payload,
                                  batching_period=batching_period,
                                  persist=persist,
                                  duration=duration)
        trace.start()
        self._traces[trace_id] = trace

        if duration:

            def maybe_stop():
                if trace_id in self._traces and self._traces[trace_id]._status == u'running':
                    self.stop_trace(trace_id, details=details)

            reactor.callLater(float(duration), maybe_stop)

        trace_started = trace.marshal()

        self.publish(u'{}.on_trace_started'.format(self._uri_prefix), trace_id, trace_started)

        return trace_started

    @wamp.register(None)
    def stop_trace(self, trace_id, details=None):
        self.log.info('stop_trace(trace_id="{trace_id}")', trace_id=trace_id)

        if trace_id not in self._traces:
            raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))

        trace = self._traces[trace_id]
        trace.stop()

        del self._traces[trace_id]

        trace_stopped = trace.marshal()

        self.publish(u'{}.on_trace_stopped'.format(self._uri_prefix), trace_id, trace_stopped)

        return trace_stopped

    @wamp.register(None)
    def get_trace_data(self, trace_id, from_seq, to_seq=None, limit=None, details=None):
        self.log.debug(
            'get_trace_data(trace_id="{trace_id}", from_seq="{from_seq})", to_seq="{to_seq}", limit="{limit}")',
            trace_id=trace_id,
            from_seq=from_seq,
            to_seq=to_seq,
            limit=limit)

        if trace_id not in self._traces:
            raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))

        limit = limit or 100
        if limit > 10000:
            raise Exception('limit too large')

        return self._traces[trace_id].get_data(from_seq, to_seq, limit)

    @wamp.register(None)
    def start_router_realm_interface(self, realm_id, interface_id, interface_config, details=None):
        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if interface_id in self.realms[realm_id].interfaces:
            raise ApplicationError(
                u"crossbar.error.already_exists",
                "An interface with ID '{}' already exists in realm with ID '{}'".format(interface_id, realm_id))

        self.realms[realm_id].interfaces[interface_id] = RouterRealmInterface(interface_id, interface_config)

        realm = self.realms[realm_id].config['name']
        self._router_factory.add_interface(realm, interface_config)

        topic = u'{}.on_router_realm_interface_started'.format(self._uri_prefix)
        event = {u'id': interface_id}
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

    @wamp.register(None)
    def stop_router_realm_interface(self, realm_id, interface_id, details=None):
        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if interface_id not in self.realms[realm_id].interfaces:
            raise ApplicationError(u"crossbar.error.no_such_object",
                                   "No interface with ID '{}' in realm with ID '{}'".format(interface_id, realm_id))

        del self.realms[realm_id].interfaces[interface_id]

    @wamp.register(None)
    def get_router_realm_interface(self, realm_id, details=None):
        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))
        return self.realms[realm_id].interfaces.values()
