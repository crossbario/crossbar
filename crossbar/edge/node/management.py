##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import pprint

import numpy as np

from twisted.internet.defer import inlineCallbacks, succeed
from twisted.internet.task import LoopingCall

from autobahn.wamp.types import SubscribeOptions, PublishOptions
from autobahn.wamp.exception import ApplicationError, TransportLost
from autobahn.twisted.wamp import ApplicationSession

from crossbar._util import hlid, hl, hltype

import txaio
from txaio import make_logger, time_ns

__all__ = ('NodeManagementSession', 'NodeManagementBridgeSession')


class NodeManagementSession(ApplicationSession):
    """
    This session is used for the uplink connection to
    Crossbar.io Master.
    """

    log = make_logger()

    def onUserError(self, fail, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onUserError`
        """
        if isinstance(fail.value, ApplicationError):
            self.log.debug('{klass}.onUserError(): "{msg}"',
                           klass=self.__class__.__name__,
                           msg=fail.value.error_message())
        else:
            self.log.error(
                '{klass}.onUserError(): "{msg}"\n{traceback}',
                klass=self.__class__.__name__,
                msg=msg,
                traceback=txaio.failure_format_traceback(fail),
            )

    def __init__(self, runner, config=None):
        ApplicationSession.__init__(self, config)
        self._runner = runner

    def onConnect(self):
        self.log.debug('{klass}.onConnect()', klass=self.__class__.__name__)

        # we're connected, now authenticate using wamp-cryptosign ..

        extra = {
            # forward the client pubkey: this allows us to omit authid as
            # the router can identify us with the pubkey already
            'pubkey': self.config.extra['node_key'].public_key(),

            # not yet implemented. a public key the router should provide
            # a trustchain for it's public key. the trustroot can eg be
            # hard-coded in the client, or come from a command line option.
            'trustroot': None,

            # not yet implemented. for authenticating the router, this
            # challenge will need to be signed by the router and send back
            # in AUTHENTICATE for client to verify. A string with a hex
            # encoded 32 bytes random value.
            'challenge': None,

            # https://tools.ietf.org/html/rfc5929
            'channel_binding': 'tls-unique'
        }

        # now request to join. the authrole==node is mandatory. the actual realm
        # we're joined to is decided by Crossbar.io Master, and hence we
        # must not provide that. Same holds for authid (also auto-assigned).
        # the authid assigned will (also) be used as the node_id
        self.join(realm=None, authrole='node', authmethods=['cryptosign'], authextra=extra)

    def onChallenge(self, challenge):
        self.log.debug('{klass}.onChallenge(challenge={challenge})',
                       klass=self.__class__.__name__,
                       challenge=challenge)

        if challenge.method == 'cryptosign':
            # alright, we've got a challenge from the router.

            # not yet implemented. check the trustchain the router provided against
            # our trustroot, and check the signature provided by the
            # router for our previous challenge. if both are ok, everything
            # is fine - the router is authentic wrt our trustroot.

            # sign the challenge with our private key.
            signed_challenge = self.config.extra['node_key'].sign_challenge(self, challenge)

            # send back the signed challenge for verification
            return signed_challenge

        else:
            raise Exception(
                'internal error: we asked to authenticate using wamp-cryptosign, but now received a challenge for {}'.
                format(challenge.method))

    def onJoin(self, details):
        self.log.info('{func}(details={details})', func=hltype(self.onJoin), details=details)

        # be paranoid .. sanity checks
        if self.config.extra and 'on_ready' in self.config.extra:
            if not self.config.extra['on_ready'].called:

                self.config.extra['on_ready'].callback((
                    self,
                    details.realm,  # the management realm we've got auto-assigned to
                    details.session,  # WAMP session ID
                    details.authid,  # the authid (==node_id) we've got auto-assigned
                    details.authextra))
            else:
                raise Exception('internal error: on_ready callback already called when we expected it was not')
        else:
            raise Exception('internal error: no on_ready callback provided')

    def onLeave(self, details):
        self.log.debug('{klass}.onLeave(details={details})', klass=self.__class__.__name__, details=details)

        if details.reason in ['fabric.auth-failed.node-unpaired', 'fabric.auth-failed.node-already-connected']:
            # no reason to auto-reconnect: user needs to get active and pair the node first.
            self._runner.stop()

        if self.config.extra and 'on_ready' in self.config.extra:
            if not self.config.extra['on_ready'].called:
                self.config.extra['on_ready'].errback(ApplicationError(details.reason, details.message))

        if self.config.extra and 'on_exit' in self.config.extra:
            if not self.config.extra['on_exit'].called:
                self.config.extra['on_exit'].callback(details.reason)
            else:
                raise Exception('internal error: on_exit callback already called when we expected it was not')
        else:
            raise Exception('internal error: no on_exit callback provided')

        self.disconnect()

    def onDisconnect(self):
        self.log.debug('{klass}.onDisconnect()', klass=self.__class__.__name__)

        node = self.config.extra['node']

        # FIXME: the node shutdown behavior should be more sophisticated than this!
        shutdown_on_cfc_lost = False

        if shutdown_on_cfc_lost:
            if node._controller:
                node._controller.shutdown()


class NodeManagementBridgeSession(ApplicationSession):
    """
    The management bridge is a WAMP session that lives on the local management router,
    but has access to a 2nd WAMP session that lives on the uplink CFC router.

    The bridge is responsible for forwarding calls from CFC into the local node,
    and for forwarding events from the local node to CFC.
    """

    log = make_logger()

    def __init__(self, config):
        ApplicationSession.__init__(self, config)
        self._manager = None
        self._management_realm = None
        self._node_id = None
        self._regs = {}
        self._authrole = 'trusted'
        self._authmethod = 'trusted'
        self._sub_on_mgmt = None
        self._sub_on_reg_create = None
        self._sub_on_reg_delete = None
        self._heartbeat_time_ns = None
        self._heartbeat = 0
        self._heartbeat_call = None

    def onJoin(self, details):
        self.log.debug('{klass}.onJoin(details={details})', klass=self.__class__.__name__, details=details)

    @inlineCallbacks
    def attach_manager(self, manager, management_realm, node_id):
        """
        Attach management uplink session when the latter has been fully established
        and is ready to be used.

        :param manager: uplink session.
        :type manager: instance of `autobahn.wamp.protocol.ApplicationSession`

        :param management_realm: The management realm that was assigned by CFC to this node.
        :type management_realm: unicode

        :param node_id: The node ID that was assigned by CFC to this node.
        :type node_id: unicode
        """
        if self._manager:
            raise Exception('{}.attach_manager: interal error: manager already attached!'.format(
                self.__class__.__name__))

        self._manager = manager
        self._management_realm = management_realm
        self._node_id = node_id
        self._node_key = self.config.extra['node_key']
        self._controller_config = self.config.extra['controller_config']

        fabric = self._controller_config.get('fabric', {})
        heartbeat = fabric.get('heartbeat', {})
        self._heartbeat_startup_delay = heartbeat.get('startup_delay', 5)
        self._heartbeat_heartbeat_period = heartbeat.get('heartbeat_period', 10)
        self._heartbeat_include_system_stats = heartbeat.get('include_system_stats', True)
        self._heartbeat_send_workers_heartbeats = heartbeat.get('send_workers_heartbeats', True)
        self._heartbeat_aggregate_workers_heartbeats = heartbeat.get('aggregate_workers_heartbeats', True)

        yield self._start_call_forwarding()
        yield self._start_event_forwarding()

        # start heartbeating a bit later (we currently run into workers not fully being up otherwise)
        from twisted.internet import reactor
        reactor.callLater(self._heartbeat_startup_delay, self._start_cfc_heartbeat)

        self.log.info(
            '{klass}.attach_manager: manager attached as node "{node_id}" on management realm "{management_realm}") with public key "{public_key}"',
            klass=self.__class__.__name__,
            node_id=self._node_id,
            management_realm=self._management_realm,
            public_key=self._node_key.public_key())
        self.log.info('Controller configuration: {controller_config}', controller_config=self._controller_config)

    @inlineCallbacks
    def detach_manager(self):
        """
        Detach management uplink session (eg when that session has been lost).
        """
        if not self._manager:
            self.log.debug('{klass}.detach_manager: no manager manager currently attached',
                           klass=self.__class__.__name__)
            return

        try:
            self._stop_cfc_heartbeat()
        except:  # noqa
            self.log.failure()

        try:
            yield self._stop_event_forwarding()
        except:  # noqa
            self.log.failure()

        try:
            yield self._stop_call_forwarding()
        except:  # noqa
            self.log.failure()

        self._manager = None
        self._management_realm = None
        self._node_id = None

        self.log.info(
            '{klass}.detach_manager: manager detached for node "{node_id}" on management realm "{management_realm}")',
            klass=self.__class__.__name__,
            node_id=self._node_id,
            management_realm=self._management_realm)

    def _translate_uri(self, uri):
        """
        Translate a local URI (one that is used on the local node management router)
        to a remote URI (one used on the uplink management session at the CFC router
        for the management realm).

        Example:

            crossbar.worker.worker-001.start_manhole
                ->
            crossbarfabriccenter.node.<node_id>.worker.<worker_id>.start_manhole
        """

        # the local URI prefix under which the management API is registered
        _PREFIX = 'crossbar.'

        # the remote (==CFC) URI prefix under which the management API is registered
        _TARGET_PREFIX = 'crossbarfabriccenter.node'

        if uri.startswith(_PREFIX):
            suffix = uri[len(_PREFIX):]
            mapped_uri = '.'.join([_TARGET_PREFIX, self._node_id, suffix])
            self.log.debug("mapped URI {uri} to {mapped_uri} [suffix={suffix}]",
                           uri=uri,
                           mapped_uri=mapped_uri,
                           suffix=suffix)
            return mapped_uri

        raise Exception("don't know how to translate URI {}".format(uri))

    @inlineCallbacks
    def _send_heartbeat(self):
        def _drop_attr(status):
            for k in ['ts', 'timestamp', 'user', 'name', 'cmdline', 'created']:
                if k in status:
                    del status[k]

        if self._manager and self._manager.is_attached():
            node_pubkey = str(self._node_key.public_key())

            # get basic status
            status = yield self.call('crossbar.get_status')
            obj = {
                'timestamp': self._heartbeat_time_ns,
                'period': self._heartbeat_heartbeat_period,
                'pubkey': node_pubkey,
                'mrealm_id': self._management_realm,
                'seq': self._heartbeat,
                'workers': status.get('workers_by_type', {}),
            }

            controller_status = None
            try:
                controller_status = yield self.call('crossbar.get_process_monitor')
            except ApplicationError as e:
                if e.error == 'wamp.error.no_such_procedure':
                    self.log.info(
                        'Failed to retrieve controller process statistics for period {period} - controller procedure unavailable',
                        period=self._heartbeat)
                else:
                    raise e
            else:
                _drop_attr(controller_status)
                controller_status['timestamp'] = self._heartbeat_time_ns
                controller_status['period'] = self._heartbeat_heartbeat_period
                controller_status['mrealm_id'] = self._management_realm
                controller_status['seq'] = self._heartbeat
                controller_status['type'] = 'controller'

                # MWorkerState: "online and fully operational" == 1
                controller_status['state'] = 1

            obj['workers']['controller'] = 1

            if self._heartbeat_include_system_stats:
                obj['system'] = yield self.call('crossbar.get_system_stats')

            # MNodeState: "online and fully operational" == 1
            obj['state'] = 1

            try:
                if self._manager:
                    yield self._manager.publish('crossbarfabriccenter.node.on_heartbeat',
                                                self._node_id,
                                                obj,
                                                options=PublishOptions(acknowledge=True))
                    self.log.debug('Node heartbeat sent [node_id="{node_id}", timestamp="{timestamp}", seq={seq}]',
                                   timestamp=np.datetime64(obj['timestamp'], 'ns'),
                                   seq=obj['seq'],
                                   node_id=self._node_id,
                                   obj=obj)
                    self.log.debug('{heartbeat}', heartbeat=pprint.pformat(obj))
                else:
                    self.log.warn(
                        'Skipped sending management link node heartbeat for period {period} - no management uplink',
                        period=self._heartbeat)
            except:  # noqa
                self.log.warn('Failed to send management link node heartbeat for period {period}:',
                              period=self._heartbeat)
                self.log.failure()

            if self._heartbeat_send_workers_heartbeats:
                workers = {}
                native_worker_types = ['router', 'container', 'proxy', 'xbrmm', 'hostmonitor']
                worker_ids = yield self.call('crossbar.get_workers', filter_types=native_worker_types)
                for worker_id in worker_ids:
                    worker_status = {}
                    try:
                        worker_status['process'] = yield self.call(
                            'crossbar.worker.{}.get_process_monitor'.format(worker_id))
                        self.log.debug('Native worker status: {status}', status=worker_status)
                    except ApplicationError as e:
                        if e.error == 'wamp.error.no_such_procedure':
                            self.log.warn(
                                'Failed to retrieve worker process statistics for worker "{worker_id}" in period {period} ("worker procedure unavailable")',
                                worker_id=worker_id,
                                period=self._heartbeat)
                        else:
                            raise e
                    else:
                        _drop_attr(worker_status)
                        worker_status['timestamp'] = self._heartbeat_time_ns
                        worker_status['period'] = self._heartbeat_heartbeat_period
                        worker_status['pubkey'] = node_pubkey
                        worker_status['mrealm_id'] = self._management_realm
                        worker_status['seq'] = self._heartbeat
                        worker_status['type'] = worker_status['process']['type']

                        # MWorkerState: "online and fully operational" == 1
                        worker_status['state'] = 1

                        del worker_status['process']['type']
                        workers[worker_id] = worker_status

                workers['controller'] = controller_status

                for worker_id, worker_status in workers.items():

                    # if worker is of type "router", expand with router statistics
                    if worker_status['type'] == 'router':
                        try:
                            router_stats = yield self.call(
                                'crossbar.worker.{}.get_router_realm_stats'.format(worker_id))
                            self.log.debug('Router worker status: {router_stats}', router_stats=router_stats)
                        except ApplicationError as e:
                            if e.error == 'wamp.error.no_such_procedure':
                                self.log.warn(
                                    'Failed to retrieve router statistics for period {period} - worker procedure unavailable',
                                    period=self._heartbeat)
                            else:
                                raise e
                        else:
                            if self._heartbeat_aggregate_workers_heartbeats:
                                mstats = {}
                                stats_sessions = 0
                                stats_roles = 0
                                for realm in router_stats:
                                    stats_sessions += router_stats[realm]['sessions']
                                    stats_roles += router_stats[realm]['roles']
                                    for direction in router_stats[realm]['messages']:
                                        for k in router_stats[realm]['messages'][direction]:
                                            if k not in mstats:
                                                mstats[k] = 0
                                            mstats[k] += router_stats[realm]['messages'][direction][k]
                                worker_status['router'] = {
                                    'messages': mstats,
                                    'sessions': stats_sessions,
                                    'roles': stats_roles,
                                }
                            else:
                                worker_status['router'] = router_stats

                    # now publish the node heartbeat management event
                    try:
                        if self._manager:
                            yield self._manager.publish('crossbarfabriccenter.node.on_worker_heartbeat',
                                                        self._node_id,
                                                        str(worker_id),
                                                        worker_status,
                                                        options=PublishOptions(acknowledge=True))
                            self.log.debug(
                                'Worker heartbeat sent [node_id="{node_id}", worker_id="{worker_id}", timestamp="{timestamp}", seq={seq}]',
                                node_id=self._node_id,
                                worker_id=worker_id,
                                timestamp=np.datetime64(worker_status['timestamp'], 'ns'),
                                seq=worker_status['seq'])
                            self.log.debug('{heartbeat}', heartbeat=pprint.pformat(worker_status))
                        else:
                            self.log.warn(
                                'Skipped sending management link node heartbeat for period {period} - no management uplink',
                                period=self._heartbeat)
                    except TransportLost:
                        self.log.info(
                            'Failed to send management link worker heartbeat for period {period} - transport lost',
                            period=self._heartbeat)

        else:
            self.log.info('Skipped sending management link heartbeat for period {period} (not connected)',
                          period=self._heartbeat)
            return succeed(None)

    def _start_cfc_heartbeat(self):
        self.log.info('Starting management heartbeat .. [period={period} seconds]',
                      period=hlid(self._heartbeat_heartbeat_period))

        self._heartbeat_time_ns = None
        self._heartbeat = 0

        @inlineCallbacks
        def publish():
            self._heartbeat_time_ns = time_ns()
            self._heartbeat += 1
            try:
                yield self._send_heartbeat()
            except Exception:
                self.log.failure()

        self._heartbeat_call = LoopingCall(publish)
        self._heartbeat_call.start(self._heartbeat_heartbeat_period)

    def _stop_cfc_heartbeat(self):
        if self._heartbeat_call:
            self._heartbeat_call.stop()
            self._heartbeat_call = None
            self._heartbeat_time_ns = None
            self._heartbeat = 0

    @inlineCallbacks
    def _start_event_forwarding(self):

        # setup event forwarding (events originating locally are forwarded uplink)
        #
        @inlineCallbacks
        def on_management_event(*args, **kwargs):
            if not (self._manager and self._manager.is_attached()):
                self.log.warn("Can't foward management event: CFC session not attached")
                return

            details = kwargs.pop('details')

            # a node local event such as 'crossbar.node.on_ready' is mogrified to 'local.crossbar.node.on_ready'
            # (one reason is that URIs such as 'wamp.*' and 'crossbar.*' are restricted to trusted sessions, and
            # the management bridge is connecting over network to the uplink CFC and hence can't be trusted)
            #
            topic = self._translate_uri(details.topic)

            try:
                yield self._manager.publish(topic, *args, options=PublishOptions(acknowledge=True), **kwargs)
            except Exception:
                self.log.failure(
                    "Failed to forward event on topic '{topic}': {log_failure.value}",
                    topic=topic,
                )
            else:
                if topic.endswith('.on_log'):
                    log = self.log.debug
                else:
                    log = self.log.debug

                log('Forwarded management {forward_type} to CFC [local_uri={local_topic}, remote_uri={remote_topic}]',
                    forward_type=hl('EVENT'),
                    local_topic=hlid(details.topic),
                    remote_topic=hlid(topic))

        try:
            sub = self._sub_on_mgmt = yield self.subscribe(on_management_event,
                                                           u"crossbar.",
                                                           options=SubscribeOptions(match=u"prefix",
                                                                                    details_arg="details"))
            self.log.debug("Setup prefix subscription to forward node management events: {sub}", sub=sub)
        except:
            self.log.failure()

    @inlineCallbacks
    def _stop_event_forwarding(self):
        if self._sub_on_mgmt:
            yield self._sub_on_mgmt.unsubscribe()
            self._sub_on_mgmt = None

    @inlineCallbacks
    def _start_call_forwarding(self):

        # forward future new registrations
        #
        @inlineCallbacks
        def on_registration_create(session_id, registration):
            # we use the WAMP meta API implemented by CB to get notified whenever a procedure is
            # registered/unregister on the node management router, setup a forwarding procedure
            # and register that on the uplink CFC router

            if not (self._manager and self._manager.is_attached()):
                self.log.warn("Can't create forward management registration: CFC session not attached")
                return

            local_uri = registration['uri']
            remote_uri = self._translate_uri(local_uri)

            self.log.debug('Setup management API forwarding: {remote_uri} -> {local_uri}',
                           remote_uri=remote_uri,
                           local_uri=local_uri)

            def forward_call(*args, **kwargs):
                kwargs.pop('details', None)
                self.log.debug(
                    'Forwarding management {forward_type} from CFC .. [remote_uri={remote_uri}, local_uri={local_uri}]',
                    forward_type=hl('CALL'),
                    local_uri=hlid(local_uri),
                    remote_uri=hlid(remote_uri))
                return self.call(local_uri, *args, **kwargs)

            try:
                reg = yield self._manager.register(forward_call, remote_uri)
            except Exception:
                self.log.failure(
                    "Failed to register management procedure '{remote_uri}': {log_failure.value}",
                    remote_uri=remote_uri,
                )
            else:
                self._regs[registration['id']] = reg
                self.log.debug("Management procedure registered: '{remote_uri}'", remote_uri=reg.procedure)

        self._sub_on_reg_create = yield self.subscribe(on_registration_create, 'wamp.registration.on_create')

        # stop forwarding future registrations
        #
        @inlineCallbacks
        def on_registration_delete(session_id, registration_id):
            if not (self._manager and self._manager.is_attached()):
                self.log.debug("Can't delete forward management registration: CFC session not attached")
                return

            reg = self._regs.pop(registration_id, None)

            if reg:
                yield reg.unregister()
                self.log.debug("Management procedure unregistered: '{remote_uri}'", remote_uri=reg.procedure)
            else:
                self.log.warn("Could not remove forwarding for unmapped registration_id {reg_id}",
                              reg_id=registration_id)

        self._sub_on_reg_delete = yield self.subscribe(on_registration_delete, 'wamp.registration.on_delete')

        # start forwarding current registrations
        #
        res = yield self.call('wamp.registration.list')
        for match_type, reg_ids in res.items():
            for reg_id in reg_ids:
                registration = yield self.call('wamp.registration.get', reg_id)
                if registration['uri'].startswith('crossbar.'):
                    yield on_registration_create(None, registration)
                else:
                    # eg skip WAMP meta API procs like "wamp.session.list"
                    self.log.debug('skipped {uri}', uri=registration['uri'])

    @inlineCallbacks
    def _stop_call_forwarding(self):
        if self._sub_on_reg_create:
            yield self._sub_on_reg_create.unsubscribe()
            self._sub_on_reg_create = None

        if self._sub_on_reg_delete:
            yield self._sub_on_reg_delete.unsubscribe()
            self._sub_on_reg_delete = None
