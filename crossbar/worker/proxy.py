#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

from copy import deepcopy

from twisted.internet.defer import Deferred, inlineCallbacks, succeed

import txaio

from autobahn import wamp
from autobahn.wamp import message
from autobahn.wamp import types
from autobahn.wamp import auth
from autobahn.wamp import role
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import Session

from crossbar.node import worker
from crossbar.worker.controller import WorkerController
from crossbar.worker.transport import RouterTransport
from crossbar.common.twisted.endpoint import create_connecting_endpoint_from_config
from crossbar.router.protocol import WampWebSocketClientFactory
from crossbar.router.session import RouterSession
from crossbar.router.session import RouterSessionFactory
from crossbar.router.auth.pending import PendingAuth

__all__ = (
    'ProxyWorkerProcess',
    'ProxyNativeWorkerSession',
)


class ProxyWorkerProcess(worker.NativeWorkerProcess):

    TYPE = 'proxy'
    LOGNAME = 'Proxy'


class PendingAuthProxy(PendingAuth):
    """
    This implements the 'server side' of a new authentication scheme
    called 'proxy'. This scheme always succeeds and has no challenge,
    but remembers the incoming authid, authrole, authmethod and
    authextra.

    This is used for components that will be fronted by a Proxy; the
    Proxy will (for example) do cryptosign auth and then tell the
    backend component which authid et al to use via this
    authentication method.

    So, components being fronted would configured themselves like so::

        "transports": [
            {
                "type": "websocket",
                "endpoint": {
                    "type": "tcp",
                    "port": 9999,
                    "interface": "localhost"
                },
                "auth": {
                    "proxy": {}
                }
            }
        ]
    """
    log = txaio.make_logger()
    name = u'proxy'

    def __init__(self, session, config):
        self._realm = session._realm
        self._authid = session._authid
        self._authrole = session._authrole
        self._authmethod = session._authmethod
        self._authextra = session._authextra
        self._authprovider = 'proxy'

    def hello(self, realm, details):
        self.log.info(
            "PendingAuthProxy: hello {realm} {details}",
            realm=realm,
            details=details,
        )
        self._realm = realm
        self._authid = details.authid
        self._authrole = details.authrole
        self._authextra = details.authextra
        return self._accept()


class AuthProxy(PendingAuth):
    name = u'proxy'

    def __init__(self, **kw):
        self._realm = kw.get('authrealm', None)
        self._authid = kw.get('authid', 'anonymous')
        self._authrole = kw.get('authrole', None)
        self._args = kw

    @property
    def authextra(self):
        return self._args.get(u'authextra', dict())

    def on_challenge(self, session, challenge):
        raise RuntimeError("on_challenge called on proxy authentication")

    def on_welcome(self, msg, authextra):
        self.log.info(
            "AuthProxy.on_welcome: {message} {extra}",
            message=msg,
            extra=authextra,
        )
        return {
            "authextra": {
                "authid": self._authid,
                "realm": self._realm,
            }
        }


auth.IAuthenticator.register(AuthProxy)


class ProxyServerSession(RouterSession):
    """
    The autobahn.wamp.interfaces.ITransportHandler for Proxies. This
    forwards every incoming message to the other side's transport
    (with no further processing) with the *exception* of the messages
    in .do_not_forward
    """
    _backend = None
    log = txaio.make_logger()

    # types of messages we do not forward but pass up to the parent
    # class for normal-style Router processing
    do_not_forward = (
        message.Hello,
        message.Welcome,
        message.Authenticate,
    )

    def set_backend(self, other_session):
        self._backend = other_session

    def onMessage(self, msg):
        if isinstance(msg, self.do_not_forward):
            return super(ProxyServerSession, self).onMessage(msg)
        # TODO: should always destroy 'the other side' if one side
        # (including the backend) goes away (e.g. message IDs would
        # get out of sync if we just auto re-connected to the backend)
        if not self._backend or not self._backend._transport:
            raise RuntimeError("No backend, or backend transport gone")
        self._backend._transport.send(msg)


class ProxyRealm(object):
    """
    Faking out some things so we can provide a valid _realm object for
    ProxyRouter
    """

    def __init__(self, realm_id, session):
        self._realm_id = realm_id
        self.session = session  # the authenticator (among others?) will call on this session


class ProxyRouter(object):
    """
    Provide enough Router functionality so that crossbar's base
    RouterSession class can call various methods on us..
    """
    log = txaio.make_logger()

    def __init__(self, realm, worker, transport_config):
        self._realm = ProxyRealm(realm, worker)
        self._worker = worker
        self._front_to_back = dict()  # session_id -> ProxySession backend
        self._backend_transport_config = transport_config

    def has_role(self, role):
        """
        we just forward any role at all onto the 'real' backend

        XXX TODO: is this true? or should we config which roles are
        okay? or is that up to 'the real backend' itself?
        """
        return True

    def _make_backend_connection(self, realm, authid, authrole):
        backend_connected_d = Deferred()

        self.log.info(
            "backend connection to: {config}",
            config=self._backend_transport_config,
        )
        ep = create_connecting_endpoint_from_config(
            self._backend_transport_config['endpoint'],
            self._worker._cbdir,
            self._worker._reactor,
            self.log,
        )

        def create_session():
            self.log.info("ProxyRouter connected, creating session", )
            # backend_cfg = list(self._worker._backend_configs.values())[0]
            s = Session(types.ComponentConfig(realm=realm))
            s.add_authenticator(AuthProxy(
                authrealm=realm,
                authid=authid,
                authrole=authrole,
            ))

            def _join(*args):
                self.log.info("ProxyRouter joined to backend session", )
                backend_connected_d.callback(s)

            s.on('join', _join)
            return s

        # XXX FIXME TODO look at transport-type etc
        factory = WampWebSocketClientFactory(create_session, url="ws://localhost:9000/ws")
        conn_d = ep.connect(factory)
        conn_d.addErrback(backend_connected_d.errback)
        return backend_connected_d

    def _session_joined(self, session, details):
        self.log.info(
            "ProxyRouter _session_joined {details}",
            details=details,
        )
        frontend = session
        # connect to the backend
        authid = session._authid
        authrole = session._authrole
        realm = session._realm
        d = self._make_backend_connection(realm, authid, authrole)

        def got_backend(backend):
            self._front_to_back[details['session']] = backend

            def backend_connected(_, details):
                assert backend._session_id is not None

                # always just forward to frontend
                backend.onMessage = frontend._transport.send
                frontend.set_backend(backend)
                return

            backend.on('join', backend_connected)
            return backend

        d.addCallback(got_backend)
        return d

    def _session_left(self, session, details):
        self.log.info(
            "ProxyRouter _session_left {session}",
            session=session._session_id,
        )
        del self._front_to_back[session._session_id]

    def attach(self, session):
        return {
            u'broker':
            role.RoleBrokerFeatures(
                publisher_identification=True,
                pattern_based_subscription=True,
                session_meta_api=True,
                subscription_meta_api=True,
                subscriber_blackwhite_listing=True,
                publisher_exclusion=True,
                subscription_revocation=True,
                event_retention=True,
                payload_transparency=True,
                payload_encryption_cryptobox=True,
            ),
            u'dealer':
            role.RoleDealerFeatures(
                caller_identification=True,
                pattern_based_registration=True,
                session_meta_api=True,
                registration_meta_api=True,
                shared_registration=True,
                progressive_call_results=True,
                registration_revocation=True,
                payload_transparency=True,
                testament_meta_api=True,
                payload_encryption_cryptobox=True,
                call_canceling=True,
            ),
        }

    def detach(self, session):
        # XXX TODO do we need to do anything here?
        self.log.info(
            "ProxyRouter detach {session}",
            session=session._session_id,
        )


# @implementer(IRouterFactory)
class ProxyRouterFactory(object):
    """
    Given to a 'real' RouterSessionFactory so it can create IRouter
    instances
    """

    def __init__(self, worker):
        self._worker = worker
        self._node_id = "proxy"  # XXX FIXME TODO
        self._routers = dict()

    def auto_add_role(self, realm, role):
        self.log.error(
            "not auto_add: {role} to {realm}",
            role=role,
            realm=realm,
        )

    def get(self, realm):
        """
        all realms are valid.

        XXX TODO: is that true? or do we want to config valid realms?
        """
        try:
            p = self._routers[realm]
        except KeyError:
            p = self._routers[realm] = ProxyRouter(
                realm,
                self._worker,
                list(self._worker._backend_configs.values())[0]['transport'],
            )
        return p

    def __getitem__(self, realm_id):
        return self.get(realm_id)

    def __contains__(self, realm):
        return realm in self._routers


class ProxyNativeWorkerSession(WorkerController):
    WORKER_TYPE = u'proxy'
    WORKER_TITLE = u'WAMP proxy'

    def __init__(self, config=None, reactor=None, personality=None):
        super(ProxyNativeWorkerSession, self).__init__(
            config=config, reactor=reactor, personality=personality)

        self._cbdir = config.extra.cbdir
        self._reactor = reactor
        self._transports = dict()
        self._backend_configs = dict()
        self._proxy_router_factory = ProxyRouterFactory(self)
        self._proxy_session_factory = RouterSessionFactory(self._proxy_router_factory)
        self._proxy_session_factory.session = ProxyServerSession

    @property
    def router_session_factory(self):
        """
        Our custom RouterTransport subclass uses this to pass to the
        protocol Factory so it can create new sessions.
        """
        return self._proxy_session_factory

    @property
    def transports(self):
        return self._transports

    def call(self, method, *args, **kw):
        # XXX FIXME hack-tacular, pretending to be a session -- should
        # do call over a real session, probably..
        assert method == u"crossbarfx.cryptosign_auth"

        authrealm, authid, more = args
        assert more.get(u"authmethod", None) == u"cryptosign"
        authextra = more.get(u"authextra", {})
        # XXX here we can await the backend connection being
        # successful (and fail if it failed already)
        return succeed({
            u"role": more.get(u"authrole", u"anonymous"),
            u"realm": authrealm,
            u"pubkey": authextra.get(u"pubkey", None),
        })

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info(
            'Proxy worker "{worker_id}" session {session_id} initializing ..',
            worker_id=self._worker_id,
            session_id=details.session,
        )

        yield WorkerController.onJoin(self, details, publish_ready=False)

        yield self.publish_ready()

    @wamp.register(u"crossbarfx.cryptosign_auth")
    def cryptosign_auth(self, *args, **kw):
        self.log.error("cryptosign_auth called, what do we do?")

    @wamp.register(None)
    def start_proxy_transport(self, transport_id, config, details=None):
        self.log.info(
            u"start_proxy_transport: transport_id={transport_id}, config={config}",
            transport_id=transport_id,
            config=config,
        )

        if transport_id in self._transports:
            emsg = "Could not start transport: a transport with ID '{}' is already running (or starting)".format(
                transport_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # we allow two extra 'auth' methods: proxy-cryptosign and
        # proxy-ticket but these are invalid to "plain" crossbar
        transport_config = deepcopy(config)
        cryptosign_config = transport_config['auth'].pop('proxy-cryptosign', None)
        transport_config['auth'].pop('proxy-ticket', None)

        if cryptosign_config is not None:
            transport_config['auth']['cryptosign'] = {
                "type": "dynamic",
                "authenticator": "crossbarfx.cryptosign_auth",
            }

        proxy_transport = RouterTransport(self, transport_id, transport_config)

        self.log.info(
            'Proxy transport: {transport}',
            transport=proxy_transport,
        )

        # start listening ..
        d = proxy_transport.start()

        def ok(_):
            # XXX should we just make connections to all backend
            # components here (and fail now if they fail?) -- this
            # would be nice for the user (maybe) but also we want to
            # re-connect if the backend bounces right? (which implies
            # we should "always" be running, but only deal with
            # backend failures when sessions try to connect.?)
            self.transports[transport_id] = proxy_transport
            self.log.info('Proxy transport "{transport_id}" started and listening', transport_id=transport_id)
            return

        def fail(err):
            _emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(_emsg, log_failure=err)
            raise ApplicationError(u"crossbar.error.cannot_listen", _emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    @inlineCallbacks
    def stop_proxy_transport(self, name, details=None):
        if name not in self._transports:
            raise ApplicationError(
                u"crossbar.error.worker_not_running",
                u"No such worker '{}'".format(name),
            )
        yield self._transports[name].port.stopListening()
        del self._transports[name]

    @wamp.register(None)
    def start_proxy_backend(self, name, options, details=None):
        self.log.info(
            u"start_proxy_backend {name}: {options}",
            name=name,
            options=options,
        )
        if len(self._backend_configs) > 0:
            raise ApplicationError(
                u"crossbarfabric.error",
                u"Can only have a single backend currently",
            )

        # XXX FIXME checkconfig

        self._backend_configs[name] = options
        # XXX FIXME
        # ahhhh, okay so "start_proxy_backend" should *connect* to the
        # backend in the configuration -- the worker should be started
        # elsewhere.
        # if connection fails now, fail this call
        # if connection fails later, we re-connect
        # if we're not connected when a session comes in, fail the session
        # if we lose our connection, drop all proxied sessions

    # def _session_factory(self, config):
    #     self.log.info(
    #         "ProxyNativeWorker creating session {config}",
    #         config=config,
    #     )
    #     if not self._backend_configs:
    #         raise RuntimeError("No backends configured; can't proxy")
    #     return ProxyClientSession(
    #         self._reactor,
    #         self.config.extra.cbdir,
    #         self,
    #         list(self._backend_configs.values())[0]['transport'],
    #         config,
    #     )
