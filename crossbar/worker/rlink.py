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
from autobahn.wamp.message import Event, Invocation
from autobahn.wamp.exception import ApplicationError, TransportLost
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.twisted.rawsocket import WampRawSocketClientProtocol

from txaio import make_logger, time_ns

__all__ = (
    'RLink',
    'RLinkConfig',
    'RLinkManager',
)


class BridgeSession(ApplicationSession):

    log = make_logger()

    def __init__(self, config):
        ApplicationSession.__init__(self, config)

        self._subs = {}
        # registration-id's of remote registrations from an rlink
        self._regs = {}

        self._exclude_authid = None
        self._exclude_authrole = None

    def onMessage(self, msg):
        if msg._router_internal is not None:
            if isinstance(msg, Event):
                msg.publisher, msg.publisher_authid, msg.publisher_authrole = msg._router_internal
            elif isinstance(msg, Invocation):
                msg.caller, msg.caller_authid, msg.caller_authrole = msg._router_internal
        return super(BridgeSession, self).onMessage(msg)

    @inlineCallbacks
    def _setup_event_forwarding(self, other):

        self.log.debug(
            "setup event forwarding between {me} and {other} (exclude_authid={exclude_authid}, exclude_authrole={exclude_authrole})",
            exclude_authid=self._exclude_authid,
            exclude_authrole=self._exclude_authrole,
            me=self._session_id,
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
            if sub_details["uri"].startswith("wamp."):
                return

            sub_id = sub_details["id"]

            if sub_id in self._subs and self._subs[sub_id]["sub"]:
                # This will happen if, partway through the subscription process, the RLink disconnects
                self.log.error('on_subscription_create: sub ID {sub_id} already in map {method}',
                               sub_id=sub_id,
                               method=hltype(BridgeSession._setup_event_forwarding))
                return

            sub_details_local = copy.deepcopy(sub_details)
            if sub_id not in self._subs:
                sub_details_local["sub"] = None
                self._subs[sub_id] = sub_details_local

            uri = sub_details['uri']
            ERR_MSG = [None]

            @inlineCallbacks
            def on_event(*args, **kwargs):
                assert 'details' in kwargs
                details = kwargs.pop('details')
                options = kwargs.pop('options', None)

                self.log.debug(
                    'Received event on uri={uri}, options={options} (publisher={publisher}, publisher_authid={publisher_authid}, publisher_authrole={publisher_authrole}, forward_for={forward_for})',
                    uri=uri,
                    options=options,
                    publisher=details.publisher,
                    publisher_authid=details.publisher_authid,
                    publisher_authrole=details.publisher_authrole,
                    forward_for=details.forward_for)

                assert details.publisher is not None

                rlink_id = self.config.extra.get('rlink')

                if details.forward_for:
                    # The event has already been forwarded - check if we're in the chain to prevent loops
                    # Copy the chain to avoid mutating the original message
                    forward_for = list(details.forward_for)

                    # Check if this rlink session or rlink id already appears in the forward chain
                    for hop in forward_for:
                        if hop.get('session') == self._session_id:
                            self.log.debug('SKIP! already forwarded through this rlink session (session={session})',
                                           session=self._session_id)
                            return
                        if rlink_id and hop.get('rlink') == rlink_id:
                            self.log.debug('SKIP! already forwarded through rlink {rlink}', rlink=rlink_id)
                            return

                    # Not in chain yet - append ourselves and continue forwarding for multi-hop
                    self.log.debug('Multi-hop forward: appending to existing chain (forward_for={ff})', ff=forward_for)
                else:
                    # First-time forward: create forward_for chain
                    forward_for = [{
                        'session': details.publisher,
                        'authid': details.publisher_authid,
                        'authrole': details.publisher_authrole,
                    }]

                forward_for.append({
                    'session': self._session_id,
                    'authid': self._authid,
                    'authrole': self._authrole,
                    'rlink': rlink_id,
                })

                options = PublishOptions(acknowledge=True,
                                         exclude_me=True,
                                         exclude_authid=self._exclude_authid,
                                         exclude_authrole=self._exclude_authrole,
                                         forward_for=forward_for)

                try:
                    yield self.publish(uri, *args, options=options, **kwargs)
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
                sub = yield other.subscribe(on_event, uri, options=SubscribeOptions(details=True))
            except TransportLost:
                self.log.debug(
                    "on_subscription_create: could not forward-subscription '{}' as RLink is not connected".format(
                        uri))
                return

            if sub_id not in self._subs:
                self.log.info("subscription already gone: {uri}", uri=sub_details['uri'])
                yield sub.unsubscribe()
            else:
                self._subs[sub_id]["sub"] = sub

            self.log.debug(
                "created forwarding subscription: me={me} other={other} sub_id={sub_id} sub_details={sub_details} details={details} sub_session={sub_session}",
                me=self._session_id,
                other=other,
                sub_id=sub_id,
                sub_details=sub_details,
                details=details,
                sub_session=sub_session,
            )

        # listen to when a subscription is removed from the router
        #
        @inlineCallbacks
        def on_subscription_delete(session_id, sub_id, details=None):
            self.log.debug(
                "Subscription deleted: {me} {session} {sub_id} {details}",
                me=self,
                session=session_id,
                sub_id=sub_id,
                details=details,
            )

            sub_details = self._subs.get(sub_id, None)
            if not sub_details:
                self.log.debug("subscription not tracked - huh??")
                return

            uri = sub_details['uri']

            sub = self._subs[sub_id]["sub"]
            if sub is None:
                # see above; we might have un-subscribed here before
                # we got an answer from the other router
                self.log.info("subscription has no 'sub'")
            else:
                yield sub.unsubscribe()

            del self._subs[sub_id]

            self.log.debug("{other} unsubscribed from {uri}".format(other=other, uri=uri))

        @inlineCallbacks
        def forward_current_subs():
            # get current subscriptions on the router
            subs = yield self.call("wamp.subscription.list")
            for sub_id in subs['exact']:
                sub = yield self.call("wamp.subscription.get", sub_id)
                assert sub["id"] == sub_id, "Logic error, subscription IDs don't match"
                yield on_subscription_create(self._session_id, sub)

        @inlineCallbacks
        def on_remote_join(_session, _details):
            yield forward_current_subs()

        def on_remote_leave(_session, _details):
            # The remote session has ended, clear subscription records.
            # Clearing this dictionary helps avoid the case where
            # local procedures are not subscribed on the remote leg
            # on reestablishment of remote session.
            # See: https://github.com/crossbario/crossbar/issues/1909
            self._subs = {}

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
            :param details: EventDetails including publisher info and forward_for chain
            :return:
            """
            if reg_details['uri'].startswith("wamp."):
                return

            # Skip forwarding registrations created by this rlink session itself
            # to prevent feedback loop (reg_session=None is allowed for initial sync)
            if reg_session is not None and reg_session == self._session_id:
                self.log.debug('on_registration_create: skipping registration from own session for {uri}',
                               uri=reg_details['uri'])
                return

            # Skip forwarding registrations created by the other leg of this rlink
            # to prevent circular forwarding between workers
            if other._session_id and reg_session == other._session_id:
                self.log.debug('on_registration_create: skipping registration from other rlink leg for {uri}',
                               uri=reg_details['uri'])
                return

            # Check forward_for chain from the registration details to prevent loops
            # Loop detection is based on router nodes (sessions), not edges (rlinks)
            rlink_id = self.config.extra.get('rlink')
            reg_forward_for = reg_details.get('forward_for', None)
            if reg_forward_for:
                # Check if this router node (session) is already in the forward chain
                for hop in reg_forward_for:
                    if hop.get('session') == self._session_id:
                        self.log.info(
                            'SKIP registration! Loop detected - already forwarded through this router node (session={session}, rlink={rlink}) for {uri}',
                            session=self._session_id,
                            rlink=rlink_id,
                            uri=reg_details['uri'])
                        return

            reg_id = reg_details["id"]

            if reg_id in self._regs and self._regs[reg_id]["reg"]:
                # This will happen if, partway through the registration process, the RLink disconnects
                self.log.error('on_registration_create: reg ID {reg_id} already in map {method}',
                               reg_id=reg_id,
                               method=hltype(BridgeSession._setup_invocation_forwarding))
                return

            reg_details_local = copy.deepcopy(reg_details)
            if reg_id not in self._regs:
                reg_details_local["reg"] = None
                self._regs[reg_id] = reg_details_local

            uri = reg_details['uri']
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

                rlink_id = self.config.extra.get('rlink')

                # Skip if this is being called by the other rlink leg (prevents direct ping-pong)
                if details.caller == other._session_id:
                    self.log.debug('SKIP! call from other rlink leg (caller={caller}, other={other})',
                                   caller=details.caller,
                                   other=other._session_id)
                    return

                if details.forward_for:
                    # The call has already been forwarded - check if we're in the chain to prevent loops
                    # Loop detection is based on router nodes (sessions), not edges (rlinks)
                    # Copy the chain to avoid mutating the original message
                    forward_for = list(details.forward_for)

                    # Check if this router node (session) already appears in the forward chain
                    for hop in forward_for:
                        if hop.get('session') == self._session_id:
                            self.log.info(
                                'SKIP invocation! Loop detected - already forwarded through this router node (session={session}, rlink={rlink})',
                                session=self._session_id,
                                rlink=rlink_id)
                            return
                            return

                    # Not in chain yet - append ourselves and continue forwarding for multi-hop
                    self.log.debug('Multi-hop forward: appending to existing chain (forward_for={ff})', ff=forward_for)
                else:
                    # First-time forward: create forward_for chain
                    forward_for = [{
                        'session': details.caller,
                        'authid': details.caller_authid,
                        'authrole': details.caller_authrole,
                    }]

                forward_for.append({
                    'session': self._session_id,
                    'authid': self._authid,
                    'authrole': self._authrole,
                    'rlink': rlink_id,
                })

                options = CallOptions(forward_for=forward_for)

                try:
                    # Forward the call to the OTHER leg of the rlink (not back to self)
                    # This handler runs on 'other' session, so call on 'self' to forward across rlink
                    result = yield self.call(uri, *args, options=options, **kwargs)
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

            # Preserve registration options from the original registration
            match = reg_details.get('match', None)
            invoke = reg_details.get('invoke', None)
            # Check if original registration used force_reregister
            # Note: This might not be in reg_details, so we'll use it as fallback on conflict
            original_force_reregister = reg_details.get('force_reregister', False)

            # Build forward_for chain for registration loop prevention across cluster
            forward_for = []
            reg_forward_for = reg_details.get('forward_for', None)
            if reg_forward_for:
                # Append to existing chain
                forward_for = list(reg_forward_for)

            # Append this rlink session to the chain
            forward_for.append({
                'session': self._session_id,
                'authid': self._authid,
                'authrole': self._authrole,
                'rlink': rlink_id,
            })

            self.log.debug('Forwarding registration for {uri} with forward_for chain: {ff}', uri=uri, ff=forward_for)

            # First try with original settings
            # IMPORTANT: Set details_arg='details' to receive invocation details including forward_for
            try:
                reg = yield other.register(on_call,
                                           uri,
                                           options=RegisterOptions(
                                               details_arg='details',
                                               invoke=invoke,
                                               match=match,
                                               force_reregister=original_force_reregister,
                                               forward_for=forward_for,
                                           ))
            except TransportLost:
                self.log.debug(
                    "on_registration_create: could not forward-register '{}' as RLink is not connected".format(uri))
                return
            except ApplicationError as e:
                if e.error == 'wamp.error.procedure_already_exists':
                    # If procedure already exists AND original didn't use force_reregister,
                    # retry with force_reregister=True to replace stale registration.
                    # This handles stale registrations from previous rlink connections.
                    if not original_force_reregister:
                        other_leg = 'local' if self.IS_REMOTE_LEG else 'remote'
                        self.log.debug(
                            f"on_registration_create: procedure {uri} already exists on {other_leg} session, "
                            f"retrying with force_reregister=True")
                        try:
                            reg = yield other.register(on_call,
                                                       uri,
                                                       options=RegisterOptions(
                                                           details_arg='details',
                                                           invoke=invoke,
                                                           match=match,
                                                           force_reregister=True,
                                                           forward_for=forward_for,
                                                       ))
                        except Exception as retry_e:
                            self.log.error(f"on_registration_create: failed to force-reregister {uri}: {retry_e}")
                            return
                    else:
                        # Original already used force_reregister, so this shouldn't happen
                        # unless there's a race condition or multiple rlinks
                        other_leg = 'local' if self.IS_REMOTE_LEG else 'remote'
                        self.log.error(
                            f"on_registration_create: procedure {uri} already exists on {other_leg} even though "
                            f"we used force_reregister=True. Race condition or multiple rlinks?")
                        return
                else:
                    raise Exception("fatal: could not forward-register '{}'".format(uri))
            except Exception as e:
                raise Exception("fatal: could not forward-register '{}': {}".format(uri, e))

            # so ... if, during that "yield" above while we register
            # on the "other" router, *this* router may have already
            # un-registered. If that happened, our registration will
            # be gone, so we immediately un-register on the other side
            if reg_id not in self._regs:
                self.log.info("registration already gone: {uri}", uri=reg_details['uri'])
                yield reg.unregister()
            else:
                self._regs[reg_id]['reg'] = reg

            self.log.debug(
                "created forwarding registration: me={me} other={other} reg_id={reg_id} reg_details={reg_details} details={details} reg_session={reg_session}",
                me=self._session_id,
                other=other._session_id,
                reg_id=reg_id,
                reg_details=reg_details,
                details=details,
                reg_session=reg_session,
            )

        # called when a registration is removed from the local router
        @inlineCallbacks
        def on_registration_delete(session_id, reg_id, details=None):
            self.log.debug(
                "Registration deleted: {me} {session} {reg_id} {details}",
                me=self,
                session=session_id,
                reg_id=reg_id,
                details=details,
            )

            reg_details = self._regs.get(reg_id, None)
            if not reg_details:
                self.log.debug("registration not tracked - huh??")
                return

            uri = reg_details['uri']

            reg = self._regs[reg_id]['reg']
            if reg is None:
                # see above; we might have un-registered here before
                # we got an answer from the other router
                self.log.debug("registration has no 'reg'")
            else:
                yield reg.unregister()

            del self._regs[reg_id]

            self.log.debug("{other} unregistered from {uri}".format(other=other, uri=uri))

        @inlineCallbacks
        def register_current():
            # Get current registrations on the router to forward to newly connected remote router
            # This is called when RLink Remote leg first connects
            # We need to forward existing LOCAL registrations, but NOT registrations that were
            # already forwarded from other RLinks (to avoid propagation loops)

            regs = yield self.call("wamp.registration.list")
            for reg_id in regs['exact']:
                reg = yield self.call("wamp.registration.get", reg_id)
                assert reg['id'] == reg_id, "Logic error, registration IDs don't match"

                # Check if this registration was created by an RLink session
                # by examining the callees (sessions registered for this procedure)
                try:
                    callee_ids = yield self.call("wamp.registration.list_callees", reg_id)

                    # Skip if any callee is an RLink session (authrole='rlink' or 'trusted')
                    # These are forwarded registrations, not local ones
                    is_rlink_registration = False
                    for callee_id in callee_ids:
                        try:
                            callee_info = yield self.call("wamp.session.get", callee_id)
                            callee_authrole = callee_info.get('authrole', '')
                            # RLink sessions use authrole 'trusted' or 'rlink'
                            if callee_authrole in ('trusted', 'rlink'):
                                is_rlink_registration = True
                                self.log.debug(
                                    'Skipping RLink-forwarded registration during initial sync: {uri} (callee authrole={authrole})',
                                    uri=reg['uri'],
                                    authrole=callee_authrole)
                                break
                        except Exception as e:
                            # Session might have disconnected, skip this check
                            self.log.debug('Could not get session info for callee {callee}: {err}',
                                           callee=callee_id,
                                           err=e)
                            continue

                    if is_rlink_registration:
                        continue  # Skip this registration

                except Exception as e:
                    # If we can't get callees, log and skip to be safe
                    self.log.warn('Could not check callees for registration {uri}: {err}',
                                  uri=reg.get('uri', '?'),
                                  err=e)
                    continue

                # This is a local registration - forward it
                # Pass None for reg_session since wamp.registration.get doesn't provide it
                yield on_registration_create(None, reg)

        @inlineCallbacks
        def on_remote_join(_session, _details):
            yield register_current()

        def on_remote_leave(_session, _details):
            # The remote session has ended, clear registration records.
            # Clearing this dictionary helps avoid the case where
            # local procedures are not registered on the remote leg
            # on reestablishment of remote session.
            # See: https://github.com/crossbario/crossbar/issues/1909
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
        # Subscribe to INTERNAL event which is always published (even for RLink sessions)
        # to enable cluster-wide registration propagation.
        #
        # IMPORTANT: Each RLink on a router subscribes independently to this event.
        # This ensures that registrations propagate through ALL RLinks in the mesh,
        # not just a single arbitrary one. Loop prevention is handled by:
        # 1. exclude_authid in event publishing (filters RLinks in forward_for chain)
        # 2. Session-based loop detection in on_registration_create handler
        # 3. Self/other-leg checks to prevent immediate feedback
        yield self.subscribe(on_registration_create,
                             "crossbar.registration.on_create_internal",
                             options=SubscribeOptions(details_arg="details"))

        # listen to when a registration is removed from the local router
        yield self.subscribe(on_registration_delete,
                             "wamp.registration.on_delete",
                             options=SubscribeOptions(details_arg="details"))

        self.log.info("{me}: call forwarding setup done", me=self._session_id)


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

        self._exclude_authid = self.config.extra.get('exclude_authid', None)
        self._exclude_authrole = self.config.extra.get('exclude_authrole', None)

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

        self._subs = {}
        self._rlink_manager: RLinkManager = self.config.extra['rlink_manager']
        self._router_controller: RouterController = self._rlink_manager.controller

    # FIXME: async? see below
    def onConnect(self):
        try:
            authid = self.config.extra.get('authid', None)
            authrole = self.config.extra.get('authrole', None)
            authextra = self.config.extra.get('authextra', {})

            # use cryptosign-proxy for rawsocket connections (cryptosign for websocket)
            # Note: transport info is on self._transport, not self.config.transport
            if isinstance(self._transport, WampRawSocketClientProtocol):
                authmethods = ['cryptosign-proxy']
            else:
                # Assume websocket or other transport uses cryptosign
                authmethods = ['cryptosign']

            # Use pre-fetched public key from config.extra (fetched in start_link before session creation)
            # onConnect() cannot return a Deferred - it must call join() synchronously
            _public_key = self.config.extra.get('pubkey', None)
            if not _public_key:
                self.log.error('{func} No public key provided in config.extra! Cannot authenticate.',
                               func=hltype(self.onConnect))
                return

            authextra.update({
                # forward the client pubkey: this allows us to omit authid as
                # the router can identify us with the pubkey already
                'pubkey': _public_key,

                # cryptosign-proxy requires proxy_authid, proxy_authrole, and proxy_realm to identify the connecting principal
                'proxy_authid': authid,
                'proxy_authrole': authrole if authrole else 'rlink',
                'proxy_realm': self.config.realm,

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
        except Exception as e:
            self.log.error('RLINK onConnect ERROR: Exception in onConnect: {err}', err=e)
            import traceback
            traceback.print_exc()
            raise

    # FIXME: async? see below
    def onChallenge(self, challenge):
        self.log.debug('{func}(challenge={challenge})', func=hltype(self.onChallenge), challenge=challenge)

        if challenge.method in ('cryptosign', 'cryptosign-proxy'):
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

        self._exclude_authid = self.config.extra.get('exclude_authid', None)
        self._exclude_authrole = self.config.extra.get('exclude_authrole', None)

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
            if v['sub'].active:
                yield v['sub'].unsubscribe()
        self._subs = {}

        for k, v, in self._regs.items():
            if v["reg"] and v["reg"].active:
                yield v["reg"].unregister()
        self._regs = {}

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

        BridgeSession.onLeave(self, details)


class RLink(object):
    def __init__(self, id, config, started=None, started_by=None, local=None, remote=None):
        assert isinstance(id, str)
        assert isinstance(config, RLinkConfig)
        assert started is None or isinstance(started, int)
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
    def __init__(self, realm, transport, authid, exclude_authid, forward_local_events, forward_remote_events,
                 forward_local_invocations, forward_remote_invocations):
        """

        :param realm: The remote router realm.
        :type realm: str

        :param transport: The transport for connecting to the remote router.
        :type transport:
        """
        self.realm = realm
        self.transport = transport
        self.authid = authid
        self.exclude_authid = exclude_authid
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
        assert isinstance(obj, dict)
        assert id is None or isinstance(id, str)

        if id:
            obj['id'] = id

        check_dict_args(
            {
                'id': (False, [str]),
                'realm': (True, [str]),
                'transport': (True, [Mapping]),
                'authid': (False, [str]),
                'exclude_authid': (False, [Sequence]),
                'forward_local_events': (False, [bool]),
                'forward_remote_events': (False, [bool]),
                'forward_local_invocations': (False, [bool]),
                'forward_remote_invocations': (False, [bool]),
            }, obj, 'router link configuration')

        realm = obj['realm']
        authid = obj.get('authid', None)
        exclude_authid = obj.get('exclude_authid', [])
        for aid in exclude_authid:
            assert isinstance(aid, str)
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
            authid=authid,
            exclude_authid=exclude_authid,
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
        assert isinstance(link_id, str)
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
            'forward_events': link_config.forward_local_events,
            'forward_invocations': link_config.forward_local_invocations,
        }
        local_realm = self._realm.config['name']

        local_authid = link_config.authid or util.generate_serial_number()
        local_authrole = 'trusted'
        local_config = ComponentConfig(local_realm, local_extra)
        local_session = RLinkLocalSession(local_config)

        # Get public key for remote session authentication BEFORE creating the session
        # onConnect() cannot return a Deferred, so we need to fetch the key here
        public_key = yield self._controller.get_public_key()

        # setup remote session
        #
        remote_extra = {
            'rlink_manager': self,
            'other': None,
            'on_ready': Deferred(),
            'authid': link_config.authid,
            'exclude_authid': link_config.exclude_authid,
            'forward_events': link_config.forward_remote_events,
            'forward_invocations': link_config.forward_remote_invocations,
            'pubkey': public_key,  # Pre-fetched public key for cryptosign authentication
            'rlink': link_id,
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
