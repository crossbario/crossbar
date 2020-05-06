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

import os
import binascii

import txaio

from txaio import make_logger

from autobahn import util

from autobahn import wamp
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.protocol import BaseSession, ApplicationSession
from autobahn.wamp.exception import SessionNotReady
from autobahn.wamp.types import SessionDetails
from autobahn.wamp.interfaces import ITransportHandler

from crossbar.common.twisted.endpoint import extract_peer_certificate
from crossbar.router.auth import PendingAuthWampCra, PendingAuthTicket, PendingAuthScram
from crossbar.router.auth import AUTHMETHODS, AUTHMETHOD_MAP
from crossbar.router.router import Router, RouterFactory
from crossbar.router import NotAttached
from crossbar._util import hl, hlid, hltype

from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure

try:
    from crossbar.router.auth import PendingAuthCryptosign, PendingAuthCryptosignProxy
except ImportError:
    PendingAuthCryptosign = None
    PendingAuthCryptosignProxy = None


__all__ = ('RouterSessionFactory',)


class RouterApplicationSession(object):
    """
    Wraps an application session to run directly attached to a WAMP router (broker+dealer).
    """

    log = make_logger()

    def __init__(self, session, router, authid=None, authrole=None, authextra=None, store=None):
        """
        Wrap an application session and add it to the given broker and dealer.

        :param session: Application session to wrap.
        :type session: An instance that implements :class:`autobahn.wamp.interfaces.ISession`

        :param router: The router this session is embedded within.
        :type router: instance of :class:`crossbar.router.router.Router`

        :param authid: The fixed/trusted authentication ID under which the session will run.
        :type authid: str

        :param authrole: The fixed/trusted authentication role under which the session will run.
        :type authrole: str
        """
        assert isinstance(session, ApplicationSession), 'session must be of class ApplicationSession, not {}'.format(session.__class__.__name__ if session else type(session))
        assert isinstance(router, Router), 'router must be of class Router, not {}'.format(router.__class__.__name__ if router else type(router))
        assert(authid is None or isinstance(authid, str))
        assert(authrole is None or isinstance(authrole, str))
        assert(authextra is None or type(authextra) == dict)

        self.log.debug('{func}(session={session}, router={router}, authid="{authid}", authrole="{authrole}", authextra={authextra}, store={store})',
                       func=hltype(RouterApplicationSession.__init__), session=session, router=router,
                       authid=hlid(authid), authrole=hlid(authrole), authextra=authextra, store=store)

        # remember router we are wrapping the app session for
        #
        self._router = router

        # remember wrapped app session
        #
        self._session = session

        # remember "trusted" authentication information
        #
        self._trusted_authid = authid
        self._trusted_authrole = authrole
        self._trusted_authextra = authextra

        # FIXME: do we need / should we do this?
        self._realm = router._realm
        self._authid = authid
        self._authrole = authrole

        # FIXME: assemble synthetic session info for the router-embedded application session
        self._session_details = None

        # if a realm store was configured for this session, remember a reference
        self._store = store
        if self._store:
            self._store.event_store.store_session_joined(self._session, self._session_details)

        # set fake transport on session ("pass-through transport")
        #
        self._session._transport = self

        self.log.debug('{func} firing {session}.onConnect() ..', session=self._session,
                       func=hltype(RouterApplicationSession.__init__))

        # now start firing "connect" observers on the session ..
        self._session.fire('connect', self._session, self)

        # .. as well as the old-school "onConnect" callback the session.
        self._session.onConnect()

    def _swallow_error(self, fail, msg):
        try:
            if self._session:
                self._session.onUserError(fail, msg)
        except:
            pass
        return None

    def _log_error(self, fail, msg):
        self.log.failure(msg, failure=fail)
        return None

    def isOpen(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.isOpen`
        """

    @property
    def is_closed(self):
        return txaio.create_future(result=self)

    def close(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.close`
        """
        self.log.info('{klass}.close(session={session})',
                      klass=self.__class__.__name__,
                      session=self._session)
        if self._router:
            if self._router.is_attached(self._session):
                # See also #578; this is to prevent the set() of observers
                # shrinking while itering in broker.py:329 since the
                # send() call happens synchronously because this class is
                # acting as ITransport and the send() can result in an
                # immediate disconnect which winds up right here...so we
                # take at trip through the reactor loop.
                from twisted.internet import reactor

                def detach(sess):
                    try:
                        self._router.detach(sess)
                    except NotAttached:
                        self.log.warn('cannot detach session "{}": session not currently attached'.format(self._session._session_id))
                    except Exception:
                        self.log.failure()
                reactor.callLater(0, detach, self._session)
            else:
                self.log.warn('{klass}.close: router embedded session "{session_id}" not attached to router realm "{realm}" (skipping detaching of session)',
                              klass=self.__class__.__name__,
                              session_id=self._session._session_id,
                              realm=self._router._realm.id)
        else:
            self.log.warn('{klass}.close: router already none (skipping)',
                          klass=self.__class__.__name__,)

        if self._store:
            # FIXME
            close_details = None
            self._store.event_store.store_session_left(self._session, self._session_details, close_details)

    def abort(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.abort`
        """

    def send(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.send`
        """
        if isinstance(msg, message.Hello):

            # fake session ID assignment (normally done in WAMP opening handshake)
            self._session._session_id = util.id()

            # set fixed/trusted authentication information
            self._session._authid = self._trusted_authid
            self._session._authrole = self._trusted_authrole
            self._session._authmethod = None
            # FIXME: the following does blow up
            # self._session._authmethod = 'trusted'
            self._session._authprovider = None
            self._session._authextra = self._trusted_authextra

            # add app session to router
            self._router.attach(self._session)

            self.log.debug('{func} attached {session} to realm={realm} with credentials session_id={session_id}, authid={authid}, authrole={authrole} using authmethod={authmethod}',
                           session=self._session, session_id=self._session._session_id, realm=self._session._realm,
                           authid=hlid(self._session._authid), authrole=hlid(self._session._authrole),
                           authmethod=hl(self._session._authmethod), func=hltype(RouterApplicationSession.send))

            # fake app session open
            details = SessionDetails(self._session._realm,
                                     self._session._session_id,
                                     self._session._authid,
                                     self._session._authrole,
                                     self._session._authmethod,
                                     self._session._authprovider,
                                     self._session._authextra)

            # have to fire the 'join' notification ourselves, as we're
            # faking out what the protocol usually does.
            d = self._session.fire('join', self._session, details)
            d.addErrback(lambda fail: self._log_error(fail, "While notifying 'join'"))
            # now fire onJoin (since _log_error returns None, we'll be
            # back in the callback chain even on errors from 'join'
            d.addCallback(lambda _: txaio.as_future(self._session.onJoin, details))
            d.addErrback(lambda fail: self._swallow_error(fail, "While firing onJoin"))

            d.addCallback(lambda _: self._session.fire('ready', self._session))
            d.addErrback(lambda fail: self._log_error(fail, "While notifying 'ready'"))

            d.addCallback(lambda _: self.log.debug('{func} fired {session} "join" and "ready" events with details={details})',
                                                   session=self._session, details=details,
                                                   func=hltype(RouterApplicationSession.send)))

        # app-to-router
        #
        elif isinstance(msg, (message.Publish,
                              message.Subscribe,
                              message.Unsubscribe,
                              message.Call,
                              message.Yield,
                              message.Register,
                              message.Unregister,
                              message.Cancel)) or (isinstance(msg, message.Error) and msg.request_type == message.Invocation.MESSAGE_TYPE):

            # deliver message to router
            #
            self._router.process(self._session, msg)

        # router-to-app
        #
        elif isinstance(msg, (message.Event,
                              message.Invocation,
                              message.Result,
                              message.Published,
                              message.Subscribed,
                              message.Unsubscribed,
                              message.Registered,
                              message.Unregistered)) or \
            (isinstance(msg, message.Error) and (msg.request_type in {
                message.Call.MESSAGE_TYPE,
                message.Cancel.MESSAGE_TYPE,
                message.Register.MESSAGE_TYPE,
                message.Unregister.MESSAGE_TYPE,
                message.Publish.MESSAGE_TYPE,
                message.Subscribe.MESSAGE_TYPE,
                message.Unsubscribe.MESSAGE_TYPE})):

            # deliver message to app session
            #
            self._session.onMessage(msg)

        # ignore messages
        #
        elif isinstance(msg, message.Goodbye):
            details = types.CloseDetails(msg.reason, msg.message)
            session = self._session

            @inlineCallbacks
            def do_goodbye():
                try:
                    yield session.onLeave(details)
                except Exception:
                    self._log_error(Failure(), "While firing onLeave")

                # FIXME: I _think_ this is no longer needed / desirable, as it
                # seems to lead to a duplicate call into close()
                # if session._transport:
                #     session._transport.close()

                try:
                    yield session.fire('leave', session, details)
                except Exception:
                    self._log_error(Failure(), "While notifying 'leave'")

                try:
                    yield session.fire('disconnect', session)
                except Exception:
                    self._log_error(Failure(), "While notifying 'disconnect'")

                if self._router._realm.session:
                    yield self._router._realm.session.publish(
                        'wamp.session.on_leave',
                        session._session_id,
                    )
            d = do_goodbye()
            d.addErrback(lambda fail: self._log_error(fail, "Internal error"))

        else:
            # should not arrive here
            #
            raise Exception("RouterApplicationSession.send: unhandled message {0}".format(msg))


class RouterSession(BaseSession):
    """
    WAMP router session. This class implements :class:`autobahn.wamp.interfaces.ITransportHandler`.
    """

    log = make_logger()

    def __init__(self, router_factory):
        """

        :param router_factory: The router factory this session is created from. This is different from
            the :class:`crossbar.router.session.RouterSessionFactory` stored in ``self.factory``.
        :type router_factory: Instance of :class:`crossbar.router.router.RouterFactory`.
        """
        super(RouterSession, self).__init__()
        self._transport = None

        # self._router_factory._node_id
        # self._router_factory._worker
        # self._router_factory._options # :class:`crossbar.router.RouterOptions`
        # self._router_factory._router[realm]._config
        self._router_factory = router_factory

        self._router = None
        self._realm = None
        self._testaments = {"destroyed": [], "detached": []}

        self._goodbye_sent = False
        self._transport_is_closing = False
        self._session_details = None
        self._service_session = None

    def onOpen(self, transport):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onOpen`
        """
        # this is a WAMP transport instance
        self._transport = transport

        # WampLongPollResourceSession instance has no attribute '_transport_info'
        if not hasattr(self._transport, '_transport_info') or self._transport._transport_info is None:
            self._transport._transport_info = {}

        # transport configuration
        if hasattr(self._transport, 'factory') and hasattr(self._transport.factory, '_config'):
            self._transport_config = self._transport.factory._config
        else:
            self._transport_config = {}

        # a dict with x509 TLS client certificate information (if the client provided a cert)
        # constructed from information from the Twisted stream transport underlying the WAMP transport
        client_cert = None
        # eg LongPoll transports lack underlying Twisted stream transport, since LongPoll is
        # implemented at the Twisted Web layer. But we should nevertheless be able to
        # extract the HTTP client cert! <= FIXME
        if hasattr(self._transport, 'transport'):
            client_cert = extract_peer_certificate(self._transport.transport)
        if client_cert:
            self._transport._transport_info['client_cert'] = client_cert
            self.log.debug("Client connecting with TLS certificate {client_cert}", client_cert=client_cert)

        # forward the transport channel ID (if any) on transport details
        channel_id = None
        if hasattr(self._transport, 'get_channel_id'):
            # channel ID isn't implemented for LongPolL!
            channel_id = self._transport.get_channel_id()
        if channel_id:
            self._transport._transport_info['channel_id'] = binascii.b2a_hex(channel_id).decode('ascii')

        self.log.debug("Client session connected - transport: {transport_info}", transport_info=self._transport._transport_info)

        # basic session information
        self._pending_session_id = None
        self._realm = None
        self._session_id = None
        self._session_roles = None
        self._session_details = None

        # session authentication information
        self._pending_auth = None
        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None
        self._authextra = None

        # the service session to be used eg for WAMP metaevents
        self._service_session = None

    def onMessage(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onMessage`
        """
        if self._session_id is None:

            if not self._pending_session_id:
                self._pending_session_id = util.id()

            def welcome(realm, authid=None, authrole=None, authmethod=None, authprovider=None, authextra=None, custom=None):
                self._realm = realm
                self._session_id = self._pending_session_id
                self._pending_session_id = None
                self._goodbye_sent = False

                self._router = self._router_factory.get(realm)
                if not self._router:
                    # should not arrive here
                    raise Exception("logic error (no realm at a stage were we should have one)")

                self._authid = authid
                self._authrole = authrole
                self._authmethod = authmethod
                self._authprovider = authprovider
                self._authextra = authextra or {}

                self._authextra['x_cb_node'] = custom.get('x_cb_node', None)
                self._authextra['x_cb_worker'] = custom.get('x_cb_worker', None)
                self._authextra['x_cb_peer'] = custom.get('x_cb_peer', None)
                self._authextra['x_cb_pid'] = custom.get('x_cb_pid', None)

                roles = self._router.attach(self)

                msg = message.Welcome(self._session_id,
                                      roles,
                                      realm=realm,
                                      authid=authid,
                                      authrole=authrole,
                                      authmethod=authmethod,
                                      authprovider=authprovider,
                                      authextra=self._authextra,
                                      custom=custom)
                self._transport.send(msg)

                self.onJoin(SessionDetails(self._realm, self._session_id, self._authid, self._authrole, self._authmethod, self._authprovider, self._authextra))

            # the first message MUST be HELLO
            if isinstance(msg, message.Hello):

                self._session_roles = msg.roles

                details = types.HelloDetails(realm=msg.realm,
                                             authmethods=msg.authmethods,
                                             authid=msg.authid,
                                             authrole=msg.authrole,
                                             authextra=msg.authextra,
                                             session_roles=msg.roles,
                                             pending_session=self._pending_session_id)

                d = txaio.as_future(self.onHello, msg.realm, details)

                def onHello_success(res):
                    self.log.debug('{func}::_on_success(res={res})', func=hltype(self.onMessage), res=res)
                    msg = None
                    # it is possible this session has disconnected
                    # while onHello was taking place
                    if self._transport is None:
                        self.log.info(
                            "Client session disconnected during authentication",
                        )
                        return

                    if isinstance(res, types.Accept):
                        custom = {
                            'x_cb_node': self._router_factory._node_id,
                            'x_cb_worker': self._router_factory._worker_id,
                            'x_cb_peer': str(self._transport.peer),
                            'x_cb_pid': os.getpid(),
                        }
                        welcome(res.realm, res.authid, res.authrole, res.authmethod, res.authprovider, res.authextra, custom)

                    elif isinstance(res, types.Challenge):
                        msg = message.Challenge(res.method, res.extra)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                def onHello_error(err):
                    self.log.warn('{func}.onMessage(..)::onHello(realm="{realm}", details={details}) failed with {err}',
                                  func=hltype(self.onMessage), realm=msg.realm, details=details, err=err)
                    return self._swallow_error_and_abort(err)

                txaio.add_callbacks(d, onHello_success, onHello_error)

            elif isinstance(msg, message.Authenticate):

                d = txaio.as_future(self.onAuthenticate, msg.signature, {})

                def onAuthenticate_success(res):
                    msg = None
                    # it is possible this session has disconnected
                    # while authentication was taking place
                    if self._transport is None:
                        self.log.info(
                            "Client session disconnected during authentication",
                        )
                        return

                    if isinstance(res, types.Accept):
                        custom = {
                            'x_cb_node': self._router_factory._node_id,
                            'x_cb_worker': self._router_factory._worker_id,
                            'x_cb_peer': str(self._transport.peer),
                            'x_cb_pid': os.getpid(),
                        }
                        welcome(res.realm, res.authid, res.authrole, res.authmethod, res.authprovider, res.authextra, custom)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                def onAuthenticate_error(err):
                    self.log.warn('{func}.onMessage(..)::onAuthenticate(..) failed with {err}',
                                  func=hltype(self.onMessage), err=err)
                    self.log.failure(err)
                    return self._swallow_error_and_abort(err)

                txaio.add_callbacks(d, onAuthenticate_success, onAuthenticate_error)

            elif isinstance(msg, message.Abort):

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                self._session_id = None
                self._pending_session_id = None

                # self._transport.close()

            else:
                msg = "{} message received while session is not yet joined".format(str(msg.__class__.__name__).upper())
                self.log.warn('{func} {msg}', func=hltype(self.onMessage), msg=msg)
                # raise ProtocolError(msg)

        else:

            if isinstance(msg, message.Hello):
                msg = "HELLO message received while session {} is already joined".format(self._session_id)
                self.log.warn('{func} {msg}', func=hltype(self.onMessage), msg=msg)
                # raise ProtocolError(msg)

            elif isinstance(msg, message.Goodbye):
                if not self._goodbye_sent:
                    # The peer wants to close: answer with GOODBYE reply.
                    # Note: We MUST NOT send any WAMP message _after_ GOODBYE
                    reply = message.Goodbye()
                    self._transport.send(reply)
                    self._goodbye_sent = True
                else:
                    # This is the peer's GOODBYE reply to our own earlier GOODBYE
                    pass

                # We need to first detach the session from the router before
                # erasing the session ID below ..
                try:
                    self._router.detach(self)
                except Exception:
                    self.log.failure("Internal error")

                # In order to send wamp.session.on_leave properly
                # (i.e. *with* the proper session_id) we save it
                previous_session_id = self._session_id

                # At this point, we've either sent GOODBYE already earlier,
                # or we have just responded with GOODBYE. In any case, we MUST NOT
                # send any WAMP message from now on:
                # clear out session ID, so that anything that might be triggered
                # in the onLeave below is prohibited from sending WAMP stuff.
                # E.g. the client might have been subscribed to meta events like
                # wamp.session.on_leave - and we must not send that client's own
                # leave to itself!
                self._session_id = None
                self._pending_session_id = None

                # publish event, *after* self._session_id is None so
                # that we don't publish to ourselves as well (if this
                # session happens to be subscribed to wamp.session.on_leave)
                if self._service_session:
                    self._service_session.publish(
                        'wamp.session.on_leave',
                        previous_session_id,
                    )

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                # don't close the transport, as WAMP allows to reattach a session
                # to the same or a different realm without closing the transport
                # self._transport.close()

            else:
                # let the actual wamp router handle all other wamp messages ..
                self._router.process(self, msg)

    # noinspection PyUnusedLocal
    def onClose(self, wasClean):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onClose`
        """
        self.log.debug('{klass}.onClose(was_clean={was_clean})',
                       klass=self.__class__.__name__, was_clean=wasClean)

        # publish final serializer stats for WAMP client connection being closed
        if self._service_session:
            session_info_short = {
                'session': self._session_id,
                'realm': self._realm,
                'authid': self._authid,
                'authrole': self._authrole,
            }

            session_stats = self._transport._serializer.stats()
            session_stats['first'] = False
            session_stats['last'] = True

            self._service_session.publish('wamp.session.on_stats', session_info_short, session_stats)

        # set transport to None: the session won't be usable anymore from here ..
        self._transport = None

        # fire callback and close the transport
        if self._session_id:
            try:
                self.onLeave(types.CloseDetails())
            except Exception:
                self.log.failure("Exception raised in onLeave callback")

            try:
                self._router.detach(self)
            except Exception as e:
                self.log.error(
                    "Failed to detach session '{}': {}".format(self._session_id, e)
                )
                self.log.debug("{tb}".format(tb=Failure().getTraceback()))

            self._session_id = None

        self._pending_session_id = None

        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None

    def leave(self, reason=None, message=None):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.leave`
        """
        if not self._goodbye_sent:
            if reason:
                msg = wamp.message.Goodbye(reason, message)
            else:
                msg = wamp.message.Goodbye(message=message)

            self._transport.send(msg)
            self._goodbye_sent = True
        else:
            raise SessionNotReady("Already requested to close the session")

    def _swallow_error_and_abort(self, fail):
        """
        Internal method that logs an error that would otherwise be
        unhandled and also *cancels it*. This will also completely
        abort the session, sending Abort to the other side.

        DO NOT attach to Deferreds that are returned to calling code.
        """
        self.log.failure("Internal error (5): {log_failure.value}", failure=fail)

        # tell other side we're done
        reply = message.Abort("wamp.error.authorization_failed", "Internal server error")
        self._transport.send(reply)

        # cleanup
        if self._router:
            try:
                self._router.detach(self)
            except Exception:
                pass
        self._session_id = None
        self._pending_session_id = None
        return None  # we've handled the error; don't propagate

    def onHello(self, realm, details):

        try:
            # allow "Personality" classes to add authmethods
            extra_auth_methods = dict()
            if self._router_factory._worker:
                personality = self._router_factory._worker.personality
                extra_auth_methods = personality.EXTRA_AUTH_METHODS

            # default authentication method is "WAMP-Anonymous" if client doesn't specify otherwise
            authmethods = details.authmethods or ['anonymous']
            authextra = details.authextra

            self.log.debug('{func} processing authmethods={authmethods}, authextra={authextra}',
                           func=hltype(self.onHello), authextra=authextra, authmethods=authmethods)

            # if the client had a reassigned realm during authentication, restore it from the cookie
            if hasattr(self._transport, '_authrealm') and self._transport._authrealm:
                if 'cookie' in authmethods:
                    realm = self._transport._authrealm
                    authextra = self._transport._authextra
                elif self._transport._authprovider == 'cookie':
                    # revoke authentication and invalidate cookie (will be revalidated if following auth is successful)
                    self._transport._authmethod = None
                    self._transport._authrealm = None
                    self._transport._authid = None
                    if hasattr(self._transport, '_cbtid'):
                        self._transport.factory._cookiestore.setAuth(self._transport._cbtid, None, None, None, None, None)
                else:
                    pass  # TLS authentication is not revoked here

            # perform authentication
            if self._transport._authid is not None and (self._transport._authmethod == 'trusted' or self._transport._authprovider in authmethods):

                # already authenticated .. e.g. via HTTP Cookie or TLS client-certificate

                # check if role still exists on realm
                allow = self._router_factory[realm].has_role(self._transport._authrole)

                if allow:
                    return types.Accept(realm=realm,
                                        authid=self._transport._authid,
                                        authrole=self._transport._authrole,
                                        authmethod=self._transport._authmethod,
                                        authprovider=self._transport._authprovider,
                                        authextra=authextra)
                else:
                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="session was previously authenticated (via transport), but role '{}' no longer exists on realm '{}'".format(self._transport._authrole, realm))

            else:
                auth_config = self._transport_config.get('auth', None)

                if not auth_config:
                    # if authentication is _not_ configured, allow anyone to join as "anonymous"!

                    # .. but don't if the client isn't ready/willing to go on "anonymous"
                    if 'anonymous' not in authmethods:
                        return types.Deny(ApplicationError.NO_AUTH_METHOD, message='cannot authenticate using any of the offered authmethods {}'.format(authmethods))

                    authmethod = 'anonymous'

                    if not realm:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message='no realm requested')

                    if realm not in self._router_factory:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message='no realm "{}" exists on this router'.format(realm))

                    # we ignore any details.authid the client might have announced, and use
                    # a cookie value or a random value
                    if hasattr(self._transport, "_cbtid") and self._transport._cbtid:
                        # if cookie tracking is enabled, set authid to cookie value
                        authid = self._transport._cbtid
                    else:
                        # if no cookie tracking, generate a random value for authid
                        authid = util.generate_serial_number()

                    try:
                        PendingAuthKlass = AUTHMETHOD_MAP[authmethod]
                    except KeyError:
                        PendingAuthKlass = extra_auth_methods[authmethod]

                    self._pending_auth = PendingAuthKlass(
                        self._pending_session_id,
                        self._transport._transport_info,
                        self._router_factory._worker,
                        {'type': 'static', 'authrole': 'anonymous', 'authid': authid}
                    )
                    return self._pending_auth.hello(realm, details)

                else:
                    # iterate over authentication methods announced by client ..
                    for authmethod in authmethods:

                        # invalid authmethod
                        if authmethod not in AUTHMETHODS and authmethod not in extra_auth_methods:
                            self.log.debug("Unknown authmethod: {}".format(authmethod))
                            return types.Deny(message='invalid authmethod "{}"'.format(authmethod))

                        # authmethod not configured
                        if authmethod not in auth_config:
                            self.log.debug("client requested valid, but unconfigured authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # authmethod not available
                        if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                            self.log.debug("client requested valid, but unavailable authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # WAMP-Anonymous, WAMP-Ticket, WAMP-CRA, WAMP-TLS, WAMP-Cryptosign
                        # WAMP-SCRAM
                        pending_auth_methods = [
                            'anonymous', 'anonymous-proxy', 'ticket', 'wampcra', 'tls',
                            'cryptosign', 'cryptosign-proxy', 'scram',
                        ] + list(extra_auth_methods.keys())
                        if authmethod in pending_auth_methods:
                            try:
                                PendingAuthKlass = AUTHMETHOD_MAP[authmethod]
                            except KeyError:
                                PendingAuthKlass = extra_auth_methods[authmethod]

                            self._pending_auth = PendingAuthKlass(
                                self._pending_session_id,
                                self._transport._transport_info,
                                self._router_factory._worker,
                                auth_config[authmethod],
                            )
                            return self._pending_auth.hello(realm, details)

                        # WAMP-Cookie authentication
                        elif authmethod == 'cookie':
                            # the client requested cookie authentication, but there is 1) no cookie set,
                            # or 2) a cookie set, but that cookie wasn't authenticated before using
                            # a different auth method (if it had been, we would never have entered here, since then
                            # auth info would already have been extracted from the transport)
                            # consequently, we skip this auth method and move on to next auth method.
                            continue

                        else:
                            # should not arrive here
                            raise Exception("logic error")

                    # no suitable authmethod found!
                    return types.Deny(ApplicationError.NO_AUTH_METHOD, message='cannot authenticate using any of the offered authmethods {}'.format(authmethods))

        except Exception as e:
            self.log.failure()
            self.log.failure('internal error: {log_failure.value}')
            self.log.critical("internal error: {msg}", msg=str(e))
            return types.Deny(message='internal error: {}'.format(e))

    def onAuthenticate(self, signature, extra):
        """
        Callback fired when a client responds to an authentication CHALLENGE.
        """
        self.log.debug("onAuthenticate: {signature} {extra}", signature=signature, extra=extra)

        try:
            # if there is a pending auth, check the challenge response. The specifics
            # of how to check depend on the authentication method
            if self._pending_auth:

                # WAMP-Ticket, WAMP-CRA, WAMP-Cryptosign
                if isinstance(self._pending_auth, PendingAuthTicket) or \
                   isinstance(self._pending_auth, PendingAuthWampCra) or \
                   isinstance(self._pending_auth, PendingAuthCryptosign) or \
                   isinstance(self._pending_auth, PendingAuthCryptosignProxy) or \
                   isinstance(self._pending_auth, PendingAuthScram):
                    return self._pending_auth.authenticate(signature)

                # should not arrive here: logic error
                else:
                    self.log.warn('unexpected pending authentication {pending_auth}', pending_auth=self._pending_auth)
                    return types.Deny(message='internal error: unexpected pending authentication')

            # should not arrive here: client misbehaving!
            else:
                return types.Deny(message='no pending authentication')
        except Exception as e:
            self.log.failure()
            return types.Deny(message='internal error: {}'.format(e))

    def onJoin(self, details):

        if hasattr(self._transport, '_cbtid') and self._transport._cbtid:
            if details.authmethod != 'cookie':
                self._transport.factory._cookiestore.setAuth(self._transport._cbtid, details.authid, details.authrole, details.authmethod, details.authextra, self._realm)

        # Router/Realm service session
        #
        self._service_session = self._router._realm.session
        # self._router:                  crossbar.router.session.CrossbarRouter
        # self._router_factory:          crossbar.router.session.CrossbarRouterFactory
        # self._router._realm:           crossbar.worker.router.RouterRealm
        # self._router._realm.session:   crossbar.router.session.CrossbarRouterServiceSession

        self._session_details = details
        self._router._session_joined(self, details)

        # dispatch session metaevent from WAMP AP
        #
        if self._service_session:
            session_info_long = {
                'session': details.session,
                'authid': details.authid,
                'authrole': details.authrole,
                'authmethod': details.authmethod,
                'authextra': details.authextra,
                'authprovider': details.authprovider,
                'transport': self._transport._transport_info
            }
            self._service_session.publish('wamp.session.on_join', session_info_long)

            realm_config = self._router_factory._routers[self._realm]._realm.config
            if 'stats' in realm_config:
                rated_message_size = realm_config['stats'].get('rated_message_size', 512)
                trigger_after_rated_messages = realm_config['stats'].get('trigger_after_rated_messages', 0)
                trigger_after_duration = realm_config['stats'].get('trigger_after_duration', 0)
                trigger_on_join = realm_config['stats'].get('trigger_on_join', False)
                trigger_on_leave = realm_config['stats'].get('trigger_on_leave', True)

                assert type(rated_message_size) == int and rated_message_size > 0 and rated_message_size % 2 == 0
                assert type(trigger_after_rated_messages) == int
                assert type(trigger_after_duration) == int
                assert trigger_after_rated_messages or trigger_after_duration
                assert type(trigger_on_join) == bool
                assert type(trigger_on_leave) == bool

                # setup serializer stats event publishing
                session_info_short = {
                    'realm': self._realm,
                    'session': details.session,
                    'authid': details.authid,
                    'authrole': details.authrole,
                }
                self._stats_trigger_on_leave = trigger_on_leave

                # if enabled, publish first stats event immediately when session is joined.
                if trigger_on_join:
                    session_stats = self._transport._serializer.stats()
                    session_stats['first'] = True
                    session_stats['last'] = False
                    self._service_session.publish('wamp.session.on_stats', session_info_short, session_stats)
                    self._stats_has_triggered_first = True
                else:
                    self._stats_has_triggered_first = False

                # publish stats events automatically ..
                def on_stats(stats):
                    if self._stats_has_triggered_first:
                        stats['first'] = False
                    else:
                        stats['first'] = True
                        self._stats_has_triggered_first = True
                    stats['last'] = False
                    self._service_session.publish('wamp.session.on_stats', session_info_short, stats)

                self._transport._serializer.RATED_MESSAGE_SIZE = rated_message_size
                self._transport._serializer.set_stats_autoreset(trigger_after_rated_messages,
                                                                trigger_after_duration,
                                                                on_stats)

                self._stats_enabled = True

                self.log.info('WAMP session statistics {mode} (rated_message_size={rated_message_size}, trigger_after_rated_messages={trigger_after_rated_messages}, trigger_after_duration={trigger_after_duration}, trigger_on_join={trigger_on_join}, trigger_on_leave={trigger_on_leave})',
                              trigger_after_rated_messages=trigger_after_rated_messages,
                              trigger_after_duration=trigger_after_duration,
                              trigger_on_join=trigger_on_join,
                              trigger_on_leave=trigger_on_leave,
                              rated_message_size=rated_message_size,
                              mode=hl('ENABLED'))

            else:
                self._stats_enabled = False
                self.log.debug('WAMP session statistics {mode}', mode=hl('DISABLED'))

    def onWelcome(self, msg):
        # this is a hook for authentication methods to deny the
        # session after the Welcome message -- do we need to do
        # anything in this impl?
        pass

    def onLeave(self, details):

        # _router can be None when, e.g., authentication fails hard
        # (e.g. the client aborts the connection during auth challenge
        # because they hit a syntax error)
        if self._router is not None:
            # todo: move me into detatch when session resumption happens
            for msg in self._testaments["detached"]:
                self._router.process(self, msg)

            for msg in self._testaments["destroyed"]:
                self._router.process(self, msg)

            self._router._session_left(self, self._session_details, details)

        # dispatch session metaevent from WAMP AP
        #
        if self._service_session and self._session_id:
            # if we got a proper Goodbye, we already sent out the
            # on_leave and our self._session_id is already None; if
            # the transport vanished our _session_id will still be
            # valid.
            self._service_session.publish('wamp.session.on_leave', self._session_id)

            if self._stats_enabled and self._stats_trigger_on_leave:
                if self._transport:
                    # publish final serializer stats for WAMP client connection being closed
                    session_info_short = {
                        'session': self._session_id,
                        'realm': self._realm,
                        'authid': self._authid,
                        'authrole': self._authrole,
                    }
                    session_stats = self._transport._serializer.stats()

                    # the stats might both be the first _and_ the last we'll publish for this session
                    if self._stats_has_triggered_first:
                        session_stats['first'] = False
                    else:
                        session_stats['first'] = True
                        self._stats_has_triggered_first = True
                    session_stats['last'] = True
                    self._service_session.publish('wamp.session.on_stats', session_info_short, session_stats)
                else:
                    self.log.warn('{klass}.onLeave() - could not retrieve last statistics for closing session {session_id}',
                                  klass=self.__class__.__name__, session_id=self._session_id)

        self._session_details = None

        # if asked to explicitly close the session ..
        if details.reason == "wamp.close.logout":

            # if cookie was set on transport ..
            if self._transport._cbtid and self._transport.factory._cookiestore:
                cs = self._transport.factory._cookiestore

                # set cookie to "not authenticated"
                cs.setAuth(self._transport._cbtid, None, None, None, None, None)

                # kick all session for the same auth cookie
                for proto in cs.getProtos(self._transport._cbtid):
                    proto.sendClose()


ITransportHandler.register(RouterSession)


class RouterSessionFactory(object):
    """
    Factory creating the router side of Crossbar.io WAMP sessions.
    This is the session factory that will be given to router transports.
    """

    log = make_logger()

    session = RouterSession
    """
    WAMP router session class to be used in this factory.
    """

    def __init__(self, routerFactory):
        """

        :param routerFactory: The router factory this session factory is working for.
        :type routerFactory: Instance of :class:`autobahn.wamp.router.RouterFactory`.
        """
        assert isinstance(routerFactory, RouterFactory)

        self._routerFactory = routerFactory
        self._app_sessions = {}

    def add(self, session, router, authid=None, authrole=None, authextra=None):
        """
        Adds a WAMP application session to run directly in this router.

        :param: session: A WAMP application session.
        :type session: instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        """
        assert isinstance(session, ApplicationSession)
        assert isinstance(router, Router)
        assert authid is None or type(authid) == str
        assert authrole is None or type(authrole) == str
        assert authextra is None or type(authextra) == dict

        if session not in self._app_sessions:
            router_session = RouterApplicationSession(session, router, authid, authrole, authextra, store=router._store)

            self._app_sessions[session] = router_session

        else:
            self.log.warn('{klass}.add: session {session} already running embedded in router {router} (skipping addition of session)',
                          klass=self.__class__.__name__,
                          session=session,
                          router=router)
            router_session = self._app_sessions[session]
        return router_session

    def remove(self, session):
        """
        Removes a WAMP application session running directly in this router.

        :param: session: A WAMP application session currently embedded in a router created from this factory.
        :type session: instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        """
        assert isinstance(session, ApplicationSession)

        if session in self._app_sessions:
            self._app_sessions[session]._session.disconnect()

            del self._app_sessions[session]

        else:
            self.log.warn('{klass}.remove: session {session} not running embedded in any router of this router factory (skipping removal of session)',
                          klass=self.__class__.__name__,
                          session=session)

    def __call__(self):
        """
        Creates a new WAMP router session.

        :return: An instance of the WAMP router session class as given by `self.session`.
        """
        session = self.session(self._routerFactory)
        session.factory = self
        return session
