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

import copy
import pprint

from collections.abc import Mapping, Sequence

from twisted.internet.defer import Deferred, inlineCallbacks

from autobahn import util
from autobahn.wamp.types import SessionIdent

from crossbar._util import hl, hlid, hltype, hluserid
from crossbar.common.checkconfig import check_dict_args, check_realm_name, check_connecting_transport
from crossbar.common.twisted.endpoint import create_connecting_endpoint_from_config

from autobahn.wamp.types import SubscribeOptions, PublishOptions, RegisterOptions, CallOptions, ComponentConfig
from autobahn.wamp.message import Event, Invocation
from autobahn.wamp.exception import ApplicationError, TransportLost
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

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
        def on_subscription_create(sub_id, sub_details, details=None):
            """
            Event handler fired when a new subscription was created on this router.

            The handler will then also subscribe on the other router, and when receiving
            events, re-publish those on this router.

            :param sub_id:
            :param sub_details:
            :param details:
            :return:
            """
            if sub_id in self._subs:
                # this should not happen actually, but not sure ..
                self.log.error(
                    'on_subscription_create: sub ID {sub_id} already in map {method}',
                    sub_id=sub_id,
                    method=hltype(BridgeSession._setup_event_forwarding))
                return

            self._subs[sub_id] = sub_details

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
                this_forward = {
                    'session': details.publisher,
                    'authid': details.publisher_authid,
                    'authrole': details.publisher_authrole,
                }

                if details.forward_for:
                    # the event comes already forwarded from a router node ..
                    if len(details.forward_for) >= 0:
                        self.log.debug('SKIP! already forwarded')
                        return

                    forward_for = copy.deepcopy(details.forward_for)
                    forward_for.append(this_forward)
                else:
                    forward_for = [this_forward]

                options = PublishOptions(
                    acknowledge=True,
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

            sub = yield other.subscribe(on_event, uri, options=SubscribeOptions(details=True))
            self._subs[sub_id]['sub'] = sub

            self.log.debug(
                "created forwarding subscription: me={me} other={other} sub_id={sub_id} sub_details={sub_details} details={details}",
                me=self._session_id,
                other=other,
                sub_id=sub_id,
                sub_details=sub_details,
                details=details,
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

            yield self._subs[sub_id]['sub'].unsubscribe()

            del self._subs[sub_id]

            self.log.debug("{other} unsubscribed from {uri}".format(other=other, uri=uri))

        # get current subscriptions on the router
        #
        subs = yield self.call("wamp.subscription.list")
        for sub_id in subs['exact']:
            sub = yield self.call("wamp.subscription.get", sub_id)

            if not sub['uri'].startswith("wamp."):
                yield on_subscription_create(sub_id, sub)

        # listen to when new subscriptions are created on the local router
        yield self.subscribe(
            on_subscription_create,
            "wamp.subscription.on_create",
            options=SubscribeOptions(details_arg="details"))

        yield self.subscribe(
            on_subscription_delete,
            "wamp.subscription.on_delete",
            options=SubscribeOptions(details_arg="details"))

        self.log.debug("{me}: event forwarding setup done", me=self)

    @inlineCallbacks
    def _setup_invocation_forwarding(self, other):

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

            :param reg_id:
            :param reg_details:
            :param details:
            :return:
            """
            if reg_details['uri'].startswith("wamp."):
                return

            if reg_details['id'] in self._regs:
                # this should not happen actually, but not sure ..
                self.log.error(
                    'on_registration_create: reg ID {reg_id} already in map {method}',
                    reg_id=reg_details['id'],
                    method=hltype(BridgeSession._setup_invocation_forwarding))
                return

            self._regs[reg_details['id']] = reg_details
            self._regs[reg_details['id']]['reg'] = None

            uri = reg_details['uri']
            ERR_MSG = [None]

            @inlineCallbacks
            def on_call(*args, **kwargs):

                assert 'details' in kwargs

                details = kwargs.pop('details')
                options = kwargs.pop('options', None)

                if details.caller is None or details.caller_authrole is None or details.caller_authid is None:
                    raise RuntimeError(
                        "Internal error attempting rlink forwarding"
                    )

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

            reg = yield other.register(
                on_call,
                uri,
                options=RegisterOptions(
                    details_arg='details',
                    invoke=reg_details.get('invoke', None),
                )
            )

            if not reg:
                raise Exception("fatal: could not forward-register '{}'".format(uri))

            # so ... if, during that "yield" above while we register
            # on the "other" router, *this* router may have already
            # un-registered. If that happened, our registration will
            # be gone, so we immediately un-register on the other side
            if reg_details['id'] not in self._regs:
                self.log.info("registration already gone: {uri}", uri=reg_details['uri'])
                yield reg.unregister()
            else:
                self._regs[reg_details['id']]['reg'] = reg

            self.log.info(
                "created forwarding registration: me={me} other={other} reg_id={reg_id} reg_details={reg_details} details={details} reg_session={reg_session}",
                me=self._session_id,
                other=other._session_id,
                reg_id=reg_details['id'],
                reg_details=reg_details,
                details=details,
                reg_session=reg_session,
            )

        # called when a registration is removed from the local router
        @inlineCallbacks
        def on_registration_delete(session_id, reg_id, details=None):
            self.log.info(
                "Registration deleted: {me} {session} {reg_id} {details}",
                me=self,
                session=session_id,
                reg_id=reg_id,
                details=details,
            )

            reg_details = self._regs.get(reg_id, None)
            if not reg_details:
                self.log.info("registration not tracked - huh??")
                return

            uri = reg_details['uri']

            reg = self._regs[reg_id]['reg']
            if reg is None:
                # see above; we might have un-registered here before
                # we got an answer from the other router
                self.log.info("registration has no 'reg'")
            else:
                yield reg.unregister()

            del self._regs[reg_id]

            self.log.info("{other} unsubscribed from {uri}".format(other=other, uri=uri))

        # get current registrations on the router
        regs = yield self.call("wamp.registration.list")
        for reg_id in regs['exact']:
            reg = yield self.call("wamp.registration.get", reg_id)
            assert reg['id'] == reg_id, "Logic error, registration IDs don't match"
            yield on_registration_create(self._session_id, reg)

        # listen to when new registrations are created on the local router
        yield self.subscribe(
            on_registration_create,
            "wamp.registration.on_create",
            options=SubscribeOptions(details_arg="details"))

        # listen to when a registration is removed from the local router
        yield self.subscribe(
            on_registration_delete,
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
        authextra = {
            'rlink': self.config.extra['rlink']
        }
        self.join(self.config.realm,
                  authid=self.config.extra['rlink'],
                  authextra=authextra)
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
        self._subs = {}
        self._rlink_manager = self.config.extra['rlink_manager']

    def onConnect(self):
        self.log.debug('{klass}.onConnect()', klass=self.__class__.__name__)

        authid = self.config.extra.get('authid', None)
        authrole = self.config.extra.get('authrole', None)
        authextra = self.config.extra.get('authextra', {})
        authmethods = ['cryptosign']

        authextra.update({
            # forward the client pubkey: this allows us to omit authid as
            # the router can identify us with the pubkey already
            'pubkey': self._rlink_manager._controller._node_key.public_key(),

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
        })

        self.log.info(
            '{klass}.join(realm="{realm}", authmethods={authmethods}, authid="{authid}", authrole="{authrole}", authextra={authextra})',
            klass=self.__class__.__name__,
            realm=self.config.realm,
            authmethods=authmethods,
            authid=authid,
            authrole=authrole,
            authextra=authextra)

        self.join(
            self.config.realm, authmethods=authmethods, authid=authid, authrole=authrole, authextra=authextra)

    def onChallenge(self, challenge):
        self.log.debug(
            '{klass}.onChallenge(challenge={challenge})', klass=self.__class__.__name__, challenge=challenge)

        if challenge.method == 'cryptosign':
            # alright, we've got a challenge from the router.

            # not yet implemented. check the trustchain the router provided against
            # our trustroot, and check the signature provided by the
            # router for our previous challenge. if both are ok, everything
            # is fine - the router is authentic wrt our trustroot.

            # sign the challenge with our private key.
            signed_challenge = self._rlink_manager._controller._node_key.sign_challenge(self, challenge)

            # send back the signed challenge for verification
            return signed_challenge

        else:
            raise Exception(
                'internal error: we asked to authenticate using wamp-cryptosign, but now received a challenge for {}'
                .format(challenge.method))

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

    def onLeave(self, details):
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
        :rtype: :class:`crossbarfx.edge.worker.rlink.RLinkConfig`
        """
        # assert isinstance(personality, Personality)
        assert type(obj) == dict
        assert id is None or type(id) == str

        if id:
            obj['id'] = id

        check_dict_args({
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
            assert type(aid) == str
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

    log = make_logger()

    def __init__(self, realm, controller):
        """

        :param realm: The (local) router realm this object is managing links for.
        :type realm: :class:`crossbarfx.edge.worker.router.ExtRouterRealm`
        """
        # assert isinstance(realm, ExtRouterRealm)

        # ExtRouterRealm
        self._realm = realm
        self._controller = controller

        # map: link_id -> RLink
        self._links = {}

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
            raise ApplicationError('crossbar.error.already_running',
                                   'router link {} already running'.format(link_id))

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
        connecting_endpoint = create_connecting_endpoint_from_config(
            link_config.transport['endpoint'], self._controller.cbdir, self._controller._reactor, self.log)
        try:
            # connect the local session
            #
            self._realm.controller._router_session_factory.add(
                local_session, self._realm.router, authid=local_authid, authrole=local_authrole, authextra=local_extra)

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
            remote_runner = ApplicationRunner(
                url=link_config.transport['url'], realm=remote_realm, extra=remote_extra)

            yield remote_runner.run(
                remote_session,
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
