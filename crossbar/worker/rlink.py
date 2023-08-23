#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import copy
import pprint

from collections.abc import Mapping, Sequence
from typing import Dict

from twisted.internet.defer import Deferred, inlineCallbacks

from autobahn import util
from autobahn.wamp.types import SessionIdent
from autobahn.util import hl, hlid, hltype, hluserid, hlval

from crossbar.common.checkconfig import check_dict_args, check_realm_name, check_connecting_transport
from crossbar.common.twisted.endpoint import create_connecting_endpoint_from_config

from autobahn.wamp.types import SubscribeOptions, PublishOptions, RegisterOptions, CallOptions, ComponentConfig
from autobahn.wamp.message import Event, Invocation, Unregistered
from autobahn.wamp.exception import ApplicationError, TransportLost
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

from txaio import make_logger, time_ns

__all__ = (
    'RLink',
    'RLinkConfig',
    'RLinkManager',
)


class BridgeLink:
    # this class is a wrapper for sub/registration details + link to chained registration/subscription
    # Storing a reference to dealer/broker owned object should save memory instead of having to duplicate
    # for every BrideSession.  Memory becomes an issue with full mesh configs O(n^2)
    def __init__(self, details, chained=None):
        self.details = details
        self.chained = chained


class URIExclusions:
    def __init__(self, uri_excludes):
        self.exact = uri_excludes.get('exact', []) if uri_excludes is not None else []
        self.prefix = uri_excludes.get('prefix', []) if uri_excludes is not None else []
        self.wildcard = uri_excludes.get('wildcard', []) if uri_excludes is not None else []

class BridgeSession(ApplicationSession):
    log = make_logger()

    def __init__(self, config):
        ApplicationSession.__init__(self, config)

        self._subs = {}
        # registration-id's of remote registrations from an rlink
        self._regs = {}

        self._exclude_authid = config.extra['exclude_authid']
        self._exclude_authrole = config.extra['exclude_authrole']
        self._exclude_uri = config.extra['exclude_uri']

        self._active = False
        self._rlink_id = config.extra['rlink_id']

        self.other = None

    def _on_unregistered(self, msg):
        if msg.request == 0:
            # this is a forced un-register either from a call
            # to the wamp.* meta-api or the force_reregister
            # option
            # forward to other
            self.log.debug(
                "Received UNREGISTERED : {me} {reg_id}",
                me=self,
                reg_id=msg.registration
            )

            reg_id = msg.registration

            if not self._active:
                return

            link = self._regs.get(reg_id, None)
            if not link:
                self.log.debug("Attempting to force-delete registration {reg_id} from {me} that is not tracked",
                               reg_id=reg_id,
                               me=self)
                return

            reg_details = link.details

            remote_registration = link.chained
            if remote_registration is None:
                # see above; we might have un-registered here before
                # we got an answer from the other router
                self.log.debug(
                    "Attempting to delete registration {reg_id} from {me} that is has no remote registration id",
                    reg_id=reg_id,
                    me=self)
            else:
                pass

            del self._regs[reg_id]


    def onMessage(self, msg):
        if msg._router_internal is not None:
            if isinstance(msg, Event):
                msg.publisher, msg.publisher_authid, msg.publisher_authrole = msg._router_internal
            elif isinstance(msg, Invocation):
                msg.caller, msg.caller_authid, msg.caller_authrole = msg._router_internal
        if isinstance(msg, Unregistered):
            self._on_unregistered(msg)
        return super(BridgeSession, self).onMessage(msg)

    def is_uri_excluded(self, uri):

        # local to router component subscriptions/registrations that shouldn't be forwarded can be defined in config
        # i.e. #prefix: ['local.', 'wamp.']
        if uri.startswith("local."):
            return True

        if self._exclude_uri is None:
            return False

        if uri in self._exclude_uri.exact:
            return True

        # check if uri has a prefix match in the list of excluded by prefix
        for prefix in self._exclude_uri.prefix:
            if uri.startswith(prefix):
                return True

        # TODO: handle wildcards

        return False


    def _common_setup(self, other):
        self.other = other

    @inlineCallbacks
    def _setup_event_forwarding(self, other):

        self.log.debug(
            "setup event forwarding between {me} and {other} (exclude_authid={exclude_authid}, exclude_authrole={exclude_authrole}, exclude_uri={exclude_uri})",
            exclude_authid=self._exclude_authid,
            exclude_authrole=self._exclude_authrole,
            exclude_uri=self._exclude_uri,
            me=self,
            other=other)

        @inlineCallbacks
        def on_subscription_create(sub_session, sub_details, details=None):
            """
            Event handler fired when a new subscription was created on this router.

            The handler will then also subscribe on the other router, and when receiving
            events, re-publish those on this router.

            :param sub_session:
            :param sub_details:
            :param details:
            :return:
            """

            if not self._active:
                return

            uri = sub_details['uri']
            if uri.startswith("wamp."):
                return

            sub_id = sub_details["id"]

            if self.is_uri_excluded(uri):
                return

            if sub_id in self._subs:
                bridge_link = self._subs[sub_id]
                if bridge_link.chained:
                    # This will happen if, partway through the registration process, the RLink disconnects
                    self.log.error('on_subscription_create: sub ID {sub_id} already in map {method}',
                                   sub_id=sub_id,
                                   method=hltype(BridgeSession._setup_event_forwarding))
                    return
                else:
                    self.log.warn(
                        'on_subscription_create: sub ID {sub_id} already in map but has no remote subscription',
                        sub_id=sub_id)
            else:
                bridge_link = BridgeLink(sub_details)
                self._subs[sub_id] = bridge_link

            ERR_MSG = [None]

            @inlineCallbacks
            def on_event(*args, **kwargs):
                assert 'details' in kwargs
                event_details = kwargs.pop('details')
                options = kwargs.pop('options', None)

                self.log.debug(
                    'Received event on uri={uri}, options={options} (publisher={publisher}, publisher_authid={publisher_authid}, publisher_authrole={publisher_authrole}, forward_for={forward_for})',
                    uri=uri,
                    options=options,
                    publisher=event_details.publisher,
                    publisher_authid=event_details.publisher_authid,
                    publisher_authrole=event_details.publisher_authrole,
                    forward_for=event_details.forward_for)

                assert event_details.publisher is not None
                this_forward = {
                    'session': event_details.publisher,
                    'authid': event_details.publisher_authid,
                    'authrole': event_details.publisher_authrole,
                }

                if event_details.forward_for:
                    # the event comes already forwarded from a router node
                    if len(event_details.forward_for) >= 0:
                        self.log.debug('SKIP! already forwarded')
                        return

                    forward_for = copy.deepcopy(event_details.forward_for)
                    forward_for.append(this_forward)
                else:
                    forward_for = [this_forward]

                options = PublishOptions(acknowledge=True,
                                         exclude_me=True,
                                         exclude_authid=self._exclude_authid,
                                         exclude_authrole=self._exclude_authrole,
                                         forward_for=forward_for)

                try:
                    # pass original procedure uri to support whildcard events #1959
                    yield self.publish(event_details.topic or uri, *args, options=options, **kwargs)
                except TransportLost:
                    return
                except ApplicationError as e:
                    if e.error not in ['wamp.close.normal']:
                        self.log.warn('FAILED TO PUBLISH 1: {} {}'.format(type(e), str(e)))
                    return
                except Exception as e:
                    if not ERR_MSG[0]:
                        self.log.warn('FAILED TO PUBLISH 2: {} {}'.format(type(e), str(e)))
                        ERR_MSG[0] = True
                    return

                self.log.debug(
                    "RLink forward-published event {dir} (options={options})",
                    dir=self.DIR,
                    options=options,
                )

            try:

                # support wildcard registrations and subscription #1959 by passing match type to other
                sub = yield other.subscribe(on_event,
                                            uri,
                                            options=SubscribeOptions(details=True,
                                                                     match=sub_details['match']))
            except TransportLost:
                self.log.debug(
                    "on_subscription_create: could not forward-subscription {uri} as RLink is not connected", uri=uri)
                return

            if sub_id not in self._subs:
                self.log.info("subscription already gone: {uri}", uri=uri)
                yield sub.unsubscribe()
            else:
                bridge_link.chained = sub

            self.log.debug(
                "created forwarding subscription or {uri}: me={me} other={other} sub_id={sub_id} sub_details={sub_details} details={details} sub_session={sub_session} sub={sub}",
                me=self,
                uri=uri,
                other=other,
                sub_id=sub_id,
                sub_details=sub_details,
                details=details,
                sub_session=sub_session,
                sub=sub)

        # listen to when a subscription is removed from the router
        #
        @inlineCallbacks
        def on_subscription_delete(session_id, sub_id, details=None):
            self.log.debug(
                "on_subscription_delete: {me} {session} {sub_id} {details}",
                me=self,
                session=session_id,
                sub_id=sub_id,
                details=details,
            )

            if not self._active:
                return

            bridge_link = self._subs.get(sub_id, None)

            if not bridge_link:
                self.log.debug("Attempting to delete subscription {sub_id} from {me} that is not tracked",
                               sub_id=sub_id,
                               me=self)
                return

            sub_details = bridge_link.details

            uri = sub_details['uri']

            sub = bridge_link.chained
            if sub is None:
                # see above; we might have un-subscribed here before
                # we got an answer from the other router
                self.log.debug("Attempting to delete subscription {sub_id} from {me} that has no chained subscription",
                               sub_id=sub_id,
                               me=self)
            else:
                yield sub.unsubscribe()

            del self._subs[sub_id]

            self.log.debug("{me} unsubscribed from {uri} on {other}", me=self, other=other, uri=uri)

        @inlineCallbacks
        def forward_current_subs():
            # get current subscriptions on the router
            self.log.debug("Forwarding all current subcriptions from {me}", me=self)

            subs = yield self.call("wamp.subscription.list")

            # support for all match types exact, prefix, wildcard #1959
            for sub_list in subs.values():
                for sub_id in sub_list:
                    sub = yield self.call("wamp.subscription.get", sub_id)
                    assert sub["id"] == sub_id, "Logic error, subscription IDs don't match"

                    # note that details are not passed to on_subscription_create
                    yield on_subscription_create(self._session_id, sub)

        @inlineCallbacks
        def on_remote_join(_session, _details):
            # Remoted joined, start/resume forwarding events
            self._active = True
            yield forward_current_subs()

        @inlineCallbacks
        def on_remote_leave(_session, _details):
            # The remote session has ended, clear subscription records.
            # Clearing this dictionary helps avoid the case where
            # local procedures are not subscribed on the remote leg
            # on reestablishment of remote session.
            # See: https://github.com/crossbario/crossbar/issues/1909
            self._subs = {}

            # also suspend forwarding events to remote leg until it re-joins
            self._active = False

        if self.IS_REMOTE_LEG:
            yield forward_current_subs()
        else:
            # from the local leg, don't try to forward events on the
            # remote leg unless the remote session is established.
            other.on('join', on_remote_join)
            other.on('leave', on_remote_leave)

        # listen to when new subscriptions are created on the local router
        yield self.subscribe(on_subscription_create,
                             "wamp.subscription.on_create",
                             options=SubscribeOptions(details_arg="details"))

        yield self.subscribe(on_subscription_delete,
                             "wamp.subscription.on_delete",
                             options=SubscribeOptions(details_arg="details"))

        self.log.debug("{me}: event forwarding setup done", me=self)

    @inlineCallbacks
    def _setup_invocation_forwarding(self, other: ApplicationSession):

        self.log.info(
            "setup invocation forwarding between {me} and {other} (exclude_authid={exclude_authid}, exclude_authrole={exclude_authrole})",
            exclude_authid=self._exclude_authid,
            exclude_authrole=self._exclude_authrole,
            me=self,
            other=other)

        # called when a registration is created on the local router
        @inlineCallbacks
        def on_registration_create(reg_session, reg_details, details=None):
            """
            Event handler fired when a new registration was created on this router.

            The handler will then also register on the other router, and when receiving
            calls, re-issue those on this router.

            :param reg_session:
            :param reg_details:
            :param details:
            :return:
            """

            if not self._active:
                return

            uri = reg_details['uri']

            # this is a useless check and can probably be removed
            # RLinkLocalSession is no longer `trusted` but `rlink`, so wamp.registration.list doesn't return wamp.*
            if uri.startswith("wamp."):
                return

            if self.is_uri_excluded(uri):
                return

            reg_id = reg_details["id"]

            if reg_id in self._regs:
                bridge_link = self._regs[reg_id]
                if bridge_link.chained:
                    # [From Skully17] This will happen if, partway through the registration process, the RLink disconnects
                    self.log.error('on_registration_create: reg ID {reg_id} already in map {method}',
                                   reg_id=reg_id,
                                   method=hltype(BridgeSession._setup_invocation_forwarding))
                    return
                else:
                    self.log.warn(
                        'on_registration_create: reg ID {reg_id} already in map but has no remote registration',
                        reg_id=reg_id)
            else:
                bridge_link = BridgeLink(reg_details)
                self._regs[reg_id] = bridge_link

            ERR_MSG = [None]

            @inlineCallbacks
            def on_call(*args, **kwargs):

                assert 'details' in kwargs

                details = kwargs.pop('details')
                options = kwargs.pop('options', None)

                if details.caller is None or details.caller_authrole is None or details.caller_authid is None:
                    raise RuntimeError("Internal error attempting rlink forwarding")

                self.log.info(
                    'Received invocation on uri={uri}, options={options} (caller={caller}, caller_authid={caller_authid}, caller_authrole={caller_authrole}, forward_for={forward_for})',
                    uri=uri,
                    options=options,
                    caller=details.caller,
                    caller_authid=details.caller_authid,
                    caller_authrole=details.caller_authrole,
                    forward_for=details.forward_for)

                this_forward = {
                    'session': details.caller,
                    'authid': details.caller_authrole,
                    'authrole': details.caller_authrole,
                }

                if details.forward_for:
                    # the call comes already forwarded from a router node ..
                    if len(details.forward_for) >= 0:
                        self.log.debug('SKIP! already forwarded')
                        return

                    forward_for = copy.deepcopy(details.forward_for)
                    forward_for.append(this_forward)
                else:
                    forward_for = [this_forward]

                options = CallOptions(forward_for=forward_for)

                try:
                    result = yield self.call(details.procedure or uri, *args, options=options, **kwargs)
                except TransportLost:
                    return
                except ApplicationError as e:
                    if e.error not in ['wamp.close.normal']:
                        self.log.warn('FAILED TO CALL 1: {} {}'.format(type(e), str(e)))
                    return
                except Exception as e:
                    if not ERR_MSG[0]:
                        self.log.warn('FAILED TO CALL 2: {} {}'.format(type(e), str(e)))
                        ERR_MSG[0] = True
                    return

                self.log.info(
                    "RLink forward-invoked call {dir} (options={options})",
                    dir=self.DIR,
                    options=options,
                )
                return result

            if not self._active:
                return

            try:
                reg = yield other.register(on_call,
                                           uri,
                                           options=RegisterOptions(
                                               details_arg='details',
                                               match=reg_details.get('match', None),
                                               invoke=reg_details.get('invoke', None),
                                               force_reregister=reg_details.get('forced_reregister', None),
                                           ))
            except TransportLost:
                self.log.debug("on_registration_create: could not forward-register '{uri}' as RLink is not connected",
                               uri=uri)
                return
            except Exception as e:
                # FIXME: partially fixes https://github.com/crossbario/crossbar/issues/1894,
                #  however we need to make sure this situation never happens.
                if isinstance(e, ApplicationError) and e.error == 'wamp.error.procedure_already_exists':
                    other_leg = 'local' if self.IS_REMOTE_LEG else 'remote'
                    self.log.debug(
                        "on_registration_create: tried to register procedure {uri} on {other_leg} session but it's already registered. session={me}",
                        uri=uri,
                        other_leg=other_leg,
                        me=self)
                    return
                raise Exception("fatal: could not forward-register '{}'".format(uri))

            # so ... if, during that "yield" above while we register
            # on the "other" router, *this* router may have already
            # un-registered. If that happened, our registration will
            # be gone, so we immediately un-register on the other side
            if reg_id not in self._regs:
                self.log.info("registration already gone: {uri}", uri=reg_details['uri'])
                yield reg.unregister()
            else:
                bridge_link.chained = reg
                # only log successful creation when we actually registered in local map
                self.log.debug(
                    "created forwarding registration: me={me} other={other} reg_id={reg_id} reg_details={reg_details} details={details} reg_session={reg_session} reg={reg}",
                    me=self,
                    other=other._session_id,
                    reg_id=reg_id,
                    reg_details=reg_details,
                    details=details,
                    reg_session=reg_session,
                    reg=reg)

        # called when a registration is removed from the local router
        @inlineCallbacks
        def on_registration_delete(session_id, reg_id, details=None):
            self.log.debug(
                "on_registration_delete: {me} {session} {reg_id} {details}",
                me=self,
                session=session_id,
                reg_id=reg_id,
                details=details,
            )

            if not self._active:
                return

            link = self._regs.get(reg_id, None)
            if not link:
                self.log.debug("Attempting to delete registration {reg_id} from {me} that is not tracked",
                               reg_id=reg_id,
                               me=self)
                return

            reg_details = link.details
            uri = reg_details['uri']

            remote_registration = link.chained
            if remote_registration is None:
                # see above; we might have un-registered here before
                # we got an answer from the other router
                self.log.debug(
                    "Attempting to delete registration {reg_id} from {me} that is has no remote registration id",
                    reg_id=reg_id,
                    me=self)
            else:
                yield remote_registration.unregister()

            del self._regs[reg_id]

            self.log.debug("deleted forwarding registration of {uri} on {me}", uri=uri, me=self)

        @inlineCallbacks
        def register_current():
            self.log.debug("Registering all current registrations from {me}", me=self)
            # get current registrations on the router
            # Since live registrations are filtered by dealer, the expectation here is that other rlink registrations
            # would be filtered out from the list, otherwise it ends up creating a snowball of registrations

            regs = yield self.call("wamp.registration.list")

            # support for all match types exact, prefix, wildcard #1959
            for reg_list in regs.values():
                for reg_id in reg_list:
                    reg = yield self.call("wamp.registration.get", reg_id)
                    assert reg['id'] == reg_id, "Logic error, registration IDs don't match"
                    yield on_registration_create(self._session_id, reg)

        @inlineCallbacks
        def on_remote_join(_session, _details):
            yield register_current()
            self._active = True

        def on_remote_leave(_session, _details):
            # The remote session has ended, clear registration records.
            # Clearing this dictionary helps avoid the case where
            # local procedures are not registered on the remote leg
            # on reestablishment of remote session.
            # See: https://github.com/crossbario/crossbar/issues/1909
            self._active = False
            self._regs = {}

        if self.IS_REMOTE_LEG:
            yield register_current()
        else:
            # from the local leg, don't try to register procedures on the
            # remote leg unless the remote session is established.
            # This avoids issues where in-router components register procedures
            # on startup and when the rlink is setup, the local leg tries to
            # register procedures on the remote leg, even though the connection
            # hasn't established.
            # See: https://github.com/crossbario/crossbar/issues/1895
            other.on('join', on_remote_join)
            other.on('leave', on_remote_leave)

        # listen to when new registrations are created on the local router
        yield self.subscribe(on_registration_create,
                             "wamp.registration.on_create",
                             options=SubscribeOptions(details_arg="details"))

        # listen to when a registration is removed from the local router
        yield self.subscribe(on_registration_delete,
                             "wamp.registration.on_delete",
                             options=SubscribeOptions(details_arg="details"))

        self.log.info("{me}: call forwarding setup done", me=self)

    def __str__(self):
        return "{klass}({rlink} {attr})".format(klass=type(self).__name__,
                                                rlink=self._rlink_id,
                                                attr=pprint.pformat(self.marshal(), width=100))

    def marshal(self):
        obj = {'authid': self.authid, 'authrole': self.authrole, 'sessionid': self.session_id, 'active': self._active}
        return obj


class RLinkLocalSession(BridgeSession):
    """
    This session is the local leg of the router-to-router link and runs embedded inside the local router.
    """

    log = make_logger()

    IS_REMOTE_LEG = False

    # direction in which events are flowing (published) via this session
    DIR = hl('from remote to local', color='yellow', bold=True)

    def onConnect(self):
        self.log.info('{klass}.onConnect()', klass=self.__class__.__name__)
        # _BridgeSession.onConnect(self)
        authextra = {'rlink': self.config.extra['rlink']}
        self.join(self.config.realm, authid=self.config.extra['rlink'], authextra=authextra)
        self._tracker = self.config.extra['tracker']

    @inlineCallbacks
    def onJoin(self, details):
        assert self.config.extra and 'on_ready' in self.config.extra
        assert self.config.extra and 'other' in self.config.extra

        remote = self.config.extra['other']
        assert isinstance(remote, RLinkRemoteSession)

        # Make sure this session is registered in router lookups for authroles
        self.transport._router._session_joined(self, session_details=details)

        self._exclude_authid = self.config.extra.get('exclude_authid', None)
        self._exclude_authrole = self.config.extra.get('exclude_authrole', None)
        self._exclude_uri = self.config.extra.get('exclude_uri', None)

        self._common_setup(remote)

        # setup local->remote event forwarding
        forward_events = self.config.extra.get('forward_events', False)
        if forward_events:
            yield self._setup_event_forwarding(remote)

        # setup local->remote invocation forwarding
        forward_invocations = self.config.extra.get('forward_invocations', False)
        if forward_invocations:
            yield self._setup_invocation_forwarding(remote)

        self.log.debug(
            'Router link local session ready (forward_events={forward_events}, forward_invocations={forward_invocations}, realm={realm}, authid={authid}, authrole={authrole}, session={session}) {method}',
            method=hltype(RLinkLocalSession.onJoin),
            forward_events=hluserid(forward_events),
            forward_invocations=hluserid(forward_invocations),
            realm=hluserid(details.realm),
            authid=hluserid(details.authid),
            authrole=hluserid(details.authrole),
            session=hlid(details.session))

        on_ready = self.config.extra.get('on_ready', None)
        if on_ready and not on_ready.called:
            self.config.extra['on_ready'].callback(self)

    def onLeave(self, details):
        self.other = None
        self.log.warn(
            'Router link local session down! (realm={realm}, authid={authid}, authrole={authrole}, session={session}, details={details}) {method}',
            method=hltype(RLinkLocalSession.onLeave),
            realm=hluserid(self.config.realm),
            authid=hluserid(self._authid),
            authrole=hluserid(self._authrole),
            details=details,
            session=hlid(self._session_id))

        BridgeSession.onLeave(self, details)


class RLinkRemoteSession(BridgeSession):
    """
    This session is the remote leg of the router-to-router link.
    """

    log = make_logger()

    IS_REMOTE_LEG = True

    # directory in which events are flowing (published via this session
    DIR = hl('from local to remote', color='yellow', bold=True)

    def __init__(self, config):
        BridgeSession.__init__(self, config)

        # import here to resolve import dependency issues
        from crossbar.worker.router import RouterController

        self._rlink_manager: RLinkManager = self.config.extra['rlink_manager']
        self._router_controller: RouterController = self._rlink_manager.controller

    # FIXME: async? see below
    def onConnect(self):
        self.log.info('{func}() ...', func=hltype(self.onConnect))

        authid = self.config.extra.get('authid', None)
        authrole = self.config.extra.get('authrole', None)
        authextra = self.config.extra.get('authextra', {})

        # FIXME: use cryptosign-proxy
        authmethods = ['cryptosign']

        # use WorkerController.get_public_key to call node controller
        # FIXME: the following does _not_ work with onConnect (?!)
        # _public_key = await self._router_controller.get_public_key()

        def actually_join(_public_key):
            authextra.update({
                # forward the client pubkey: this allows us to omit authid as
                # the router can identify us with the pubkey already
                'pubkey': _public_key,

                # not yet implemented. a public key the router should provide
                # a trustchain for its public key. the trustroot can eg be
                # hard-coded in the client, or come from a command line option.
                'trustroot': None,

                # not yet implemented. for authenticating the router, this
                # challenge will need to be signed by the router and send back
                # in AUTHENTICATE for client to verify. A string with a hex
                # encoded 32 bytes random value.
                'challenge': None,

                # https://tools.ietf.org/html/rfc5929
                'channel_binding': 'tls-unique'
            })

            self.log.info(
                '{func} joining with realm="{realm}", authmethods={authmethods}, authid="{authid}", authrole="{authrole}", authextra={authextra}',
                func=hltype(self.onConnect),
                realm=hlval(self.config.realm),
                authmethods=hlval(authmethods),
                authid=hlval(authid),
                authrole=hlval(authrole),
                authextra=authextra)

            self.join(self.config.realm,
                      authmethods=authmethods,
                      authid=authid,
                      authrole=authrole,
                      authextra=authextra)

        res = self._rlink_manager._controller.get_public_key()
        res.addCallback(actually_join)
        self.log.info('{func}() done (res={res}).', func=hltype(self.onConnect), res=res)
        return res

    # FIXME: async? see below
    def onChallenge(self, challenge):
        self.log.debug('{func}(challenge={challenge})', func=hltype(self.onChallenge), challenge=challenge)

        if challenge.method == 'cryptosign':
            # alright, we've got a challenge from the router.

            # sign the challenge with our private key.
            channel_id_type = 'tls-unique'
            channel_id_map = self._router_controller._transport.transport_details.channel_id
            if channel_id_type in channel_id_map:
                channel_id = channel_id_map[channel_id_type]
            else:
                channel_id = None
                channel_id_type = None

            # use WorkerController.get_public_key to call node controller
            # FIXME: await?
            signed_challenge = self._router_controller.sign_challenge(challenge, channel_id, channel_id_type)

            # send back the signed challenge for verification
            return signed_challenge

        else:
            raise Exception(
                'internal error: we asked to authenticate using wamp-cryptosign, but now received a challenge for {}'.
                format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        self.log.debug('{klass}.onJoin(details={details})', klass=self.__class__.__name__, details=details)

        assert self.config.extra and 'on_ready' in self.config.extra
        assert self.config.extra and 'other' in self.config.extra

        local = self.config.extra['other']
        assert isinstance(local, RLinkLocalSession)
        local._tracker.connected = True
        self._active = True

        self._exclude_authid = self.config.extra.get('exclude_authid', None)
        self._exclude_authrole = self.config.extra.get('exclude_authrole', None)
        self._exclude_uri = self.config.extra.get('exclude_uri', None)

        self._common_setup(local)
        # setup remote->local event forwarding
        forward_events = self.config.extra.get('forward_events', False)
        if forward_events:
            yield self._setup_event_forwarding(local)

        # setup remote->local invocation forwarding
        forward_invocations = self.config.extra.get('forward_invocations', False)
        if forward_invocations:
            yield self._setup_invocation_forwarding(local)

        self.log.info(
            '{klass}.onJoin(): rlink remote session ready (forward_events={forward_events}, forward_invocations={forward_invocations}, realm={realm}, authid={authid}, authrole={authrole}, session={session}) {method}',
            klass=self.__class__.__name__,
            method=hltype(RLinkRemoteSession.onJoin),
            forward_events=hluserid(forward_events),
            forward_invocations=hluserid(forward_invocations),
            realm=hluserid(details.realm),
            authid=hluserid(details.authid),
            authrole=hluserid(details.authrole),
            session=hlid(details.session))

        # we are ready!
        on_ready = self.config.extra.get('on_ready', None)
        if on_ready and not on_ready.called:
            self.config.extra['on_ready'].callback(self)

    @inlineCallbacks
    def onLeave(self, details):
        # When the rlink is going down, make sure to unsubscribe to
        # all events that are subscribed on the local-leg.
        # This avoids duplicate events that would otherwise arrive
        # See: https://github.com/crossbario/crossbar/issues/1916
        for k, v in self._subs.items():
            if v.chained.active:
                yield v.chained.unsubscribe()

        self._subs = {}

        self._active = False

        self.config.extra['other']._tracker.connected = False
        self.log.warn(
            '{klass}.onLeave(): rlink remote session left! (realm={realm}, authid={authid}, authrole={authrole}, session={session}, details={details}) {method}',
            klass=self.__class__.__name__,
            method=hltype(RLinkLocalSession.onLeave),
            realm=hluserid(self.config.realm),
            authid=hluserid(self._authid),
            authrole=hluserid(self._authrole),
            session=hlid(self._session_id),
            details=details)

        self.other = None
        BridgeSession.onLeave(self, details)


class RLink(object):
    def __init__(self, id, config, started=None, started_by=None, local=None, remote=None):
        assert type(id) == str
        assert isinstance(config, RLinkConfig)
        assert started is None or type(started) == int
        assert started_by is None or isinstance(started_by, RLinkConfig)
        assert local is None or isinstance(local, RLinkLocalSession)
        assert remote is None or isinstance(remote, RLinkLocalSession)

        # link ID
        self.id = id

        # link config: RLinkConfig
        self.config = config

        # when was it started: epoch time in ns
        self.started = started

        # who started this link: SessionIdent
        self.started_by = started_by

        # local session: RLinkLocalSession
        self.local = local

        # remote session: RLinkRemoteSession
        self.remote = remote

        # updated by the session
        self.connected = False

    def __str__(self):
        return pprint.pformat(self.marshal())

    def marshal(self):
        obj = {
            'id': self.id,
            'config': self.config.marshal() if self.config else None,
            'started': self.started,
            'started_by': self.started_by.marshal() if self.started_by else None,
            'connected': self.connected,
        }
        return obj


class RLinkConfig(object):
    def __init__(self, realm, transport, authrole, authid, exclude_authid, exclude_authrole, exclude_uri,
                 forward_local_events,
                 forward_remote_events, forward_local_invocations, forward_remote_invocations):
        """

        :param realm: The remote router realm.
        :type realm: str

        :param transport: The transport for connecting to the remote router.
        :type transport:
        """
        self.realm = realm
        self.transport = transport
        self.authrole = authrole
        self.authid = authid
        self.exclude_authid = exclude_authid
        # Components are assigned UUID for authid, we need to rely on authroles
        self.exclude_authrole = exclude_authrole
        self.exclude_uri = exclude_uri
        self.forward_local_events = forward_local_events
        self.forward_remote_events = forward_remote_events
        self.forward_local_invocations = forward_local_invocations
        self.forward_remote_invocations = forward_remote_invocations

    def __str__(self):
        return pprint.pformat(self.marshal())

    def marshal(self):
        obj = {
            'realm': self.realm,
            'transport': self.transport,
            'authid': self.authid,
            'exclude_authid': self.exclude_authid,
            'exclude_authrole': self.exclude_authrole,
            'exclude_uri': self.exclude_uri,
            'forward_local_events': self.forward_local_events,
            'forward_remote_events': self.forward_remote_events,
            'forward_local_invocations': self.forward_local_invocations,
            'forward_remote_invocations': self.forward_remote_invocations,
        }
        return obj

    @staticmethod
    def parse(personality, obj, id=None):
        """
        Parses a generic object (eg a dict) into a typed
        object of this class.

        :param obj: The generic object to parse.
        :type obj: dict

        :returns: Router link configuration
        :rtype: :class:`crossbar.edge.worker.rlink.RLinkConfig`
        """
        # assert isinstance(personality, Personality)
        assert type(obj) == dict
        assert id is None or type(id) == str

        if id:
            obj['id'] = id

        check_dict_args(
            {
                'id': (False, [str]),
                'realm': (True, [str]),
                'transport': (True, [Mapping]),
                'authid': (False, [str]),
                'authrole': (False, [str]),
                'exclude_authid': (False, [Sequence]),
                'exclude_authrole': (False, [Sequence]),
                'exclude_uri': (False, [Mapping]),
                'forward_local_events': (False, [bool]),
                'forward_remote_events': (False, [bool]),
                'forward_local_invocations': (False, [bool]),
                'forward_remote_invocations': (False, [bool]),
            }, obj, 'router link configuration')

        realm = obj['realm']
        authrole = obj.get('authrole', None)
        authid = obj.get('authid', None)
        exclude_authid = obj.get('exclude_authid', [])
        for aid in exclude_authid:
            assert type(aid) == str
        exclude_authrole = obj.get('exclude_authrole', [])
        for rid in exclude_authrole:
            assert type(rid) == str

        exclude_uri = obj.get('exclude_uri', None)
        if exclude_uri:
            for k, v in exclude_uri.items():
                assert type(k) == str
                assert k in ['prefix', 'exact', 'wildcard']
                assert type(v) == list
                for i in v:
                    assert type(i) == str
        forward_local_events = obj.get('forward_local_events', True)
        forward_remote_events = obj.get('forward_remote_events', True)
        forward_local_invocations = obj.get('forward_local_invocations', True)
        forward_remote_invocations = obj.get('forward_remote_invocations', True)
        transport = obj['transport']

        check_realm_name(realm)
        check_connecting_transport(personality, transport)

        config = RLinkConfig(
            realm=realm,
            transport=transport,
            authrole=authrole,
            authid=authid,
            exclude_authid=exclude_authid,
            exclude_authrole=exclude_authrole,
            exclude_uri=exclude_uri,
            forward_local_events=forward_local_events,
            forward_remote_events=forward_remote_events,
            forward_local_invocations=forward_local_invocations,
            forward_remote_invocations=forward_remote_invocations,
        )

        return config


class RLinkManager(object):
    """
    Router-to-router links manager.
    """
    log = make_logger()

    def __init__(self, realm, controller):
        """

        :param realm: The (local) router realm this object is managing links for.
        :param controller: The router controller this rlink is running under.
        """
        # import here to resolve import dependency issues
        from crossbar.edge.worker.router import ExtRouterRealm
        from crossbar.worker.router import RouterController

        self._realm: ExtRouterRealm = realm
        self._controller: RouterController = controller

        # map: link_id -> RLink
        self._links: Dict[str, RLink] = {}

    @property
    def realm(self):
        return self._realm

    @property
    def controller(self):
        return self._controller

    def __getitem__(self, link_id):
        if link_id in self._links:
            return self._links[link_id]
        else:
            raise KeyError('no router link with ID "{}"'.format(link_id))

    def __contains__(self, link_id):
        return link_id in self._links

    def __len__(self):
        return len(self._links)

    def __setitem__(self, item, value):
        raise Exception('__setitem__ not supported on this class')

    def __delitem__(self, item):
        raise Exception('__delitem__ not supported on this class')

    def keys(self):
        return self._links.keys()

    @inlineCallbacks
    def start_link(self, link_id, link_config, caller):
        assert type(link_id) == str
        assert isinstance(link_config, RLinkConfig)
        assert isinstance(caller, SessionIdent)

        if link_id in self._links:
            raise ApplicationError('crossbar.error.already_running', 'router link {} already running'.format(link_id))

        # setup local session
        #
        local_extra = {
            'other': None,
            'on_ready': Deferred(),
            'rlink': link_id,
            'rlink_id': link_id,
            'exclude_authid': link_config.exclude_authid,
            'exclude_authrole': link_config.exclude_authrole,
            'exclude_uri': URIExclusions(link_config.exclude_uri),
            'forward_events': link_config.forward_local_events,
            'forward_invocations': link_config.forward_local_invocations,
        }
        local_realm = self._realm.config['name']

        local_authid = link_config.authid or util.generate_serial_number()
        # Having local authrole be 'trusted' allows this RLink to see other RLinks
        # This may need to be changed in order to distinguish between actual trusted sessions and
        # RLinks that can see other RLinks
        local_authrole = link_config.authrole or 'trusted'
        local_config = ComponentConfig(local_realm, local_extra)
        local_session = RLinkLocalSession(local_config)

        # setup remote session
        #
        remote_extra = {
            'rlink_manager': self,
            'other': None,
            'on_ready': Deferred(),
            'authid': link_config.authid,
            'rlink_id': link_id,
            'exclude_authid': link_config.exclude_authid,
            'exclude_authrole': link_config.exclude_authrole,
            'exclude_uri': URIExclusions(link_config.exclude_uri),
            'forward_events': link_config.forward_remote_events,
            'forward_invocations': link_config.forward_remote_invocations,
        }
        remote_realm = link_config.realm
        remote_config = ComponentConfig(remote_realm, remote_extra)
        remote_session = RLinkRemoteSession(remote_config)

        # cross-connect the two sessions
        #
        local_extra['other'] = remote_session
        remote_extra['other'] = local_session

        # the rlink
        #
        rlink = RLink(link_id, link_config)
        self._links[link_id] = rlink
        local_extra['tracker'] = rlink

        # create connecting client endpoint
        #
        connecting_endpoint = create_connecting_endpoint_from_config(link_config.transport['endpoint'],
                                                                     self._controller.cbdir, self._controller._reactor,
                                                                     self.log)
        try:
            # connect the local session
            #
            # Adding to the router session factory will NOT add session to role->session map
            self._realm.controller._router_session_factory.add(local_session,
                                                               self._realm.router,
                                                               authid=local_authid,
                                                               authrole=local_authrole,
                                                               authextra=local_extra)

            yield local_extra['on_ready']

            # connect the remote session
            #
            # remote connection parameters to ApplicationRunner:
            #
            # url: The WebSocket URL of the WAMP router to connect to (e.g. ws://somehost.com:8090/somepath)
            # realm: The WAMP realm to join the application session to.
            # extra: Optional extra configuration to forward to the application component.
            # serializers: List of :class:`autobahn.wamp.interfaces.ISerializer` (or None for default serializers).
            # ssl: None or :class:`twisted.internet.ssl.CertificateOptions`
            # proxy: Explicit proxy server to use; a dict with ``host`` and ``port`` keys
            # headers: Additional headers to send (only applies to WAMP-over-WebSocket).
            # max_retries: Maximum number of reconnection attempts. Unlimited if set to -1.
            # initial_retry_delay: Initial delay for reconnection attempt in seconds (Default: 1.0s).
            # max_retry_delay: Maximum delay for reconnection attempts in seconds (Default: 60s).
            # retry_delay_growth: The growth factor applied to the retry delay between reconnection attempts (Default 1.5).
            # retry_delay_jitter: A 0-argument callable that introduces nose into the delay. (Default random.random)
            #
            remote_runner = ApplicationRunner(url=link_config.transport['url'], realm=remote_realm, extra=remote_extra)

            yield remote_runner.run(remote_session,
                                    start_reactor=False,
                                    auto_reconnect=True,
                                    endpoint=connecting_endpoint,
                                    reactor=self._controller._reactor)

            yield remote_extra['on_ready']

        except:
            # make sure to remove the half-initialized link from our map ..
            del self._links[link_id]

            # .. and then re-raise
            raise

        # the router link is established: store final infos
        rlink.started = time_ns()
        rlink.started_by = caller
        rlink.local = local_session
        rlink.remote = remote_session

        return rlink

    @inlineCallbacks
    def stop_link(self, link_id, caller):
        raise NotImplementedError()
