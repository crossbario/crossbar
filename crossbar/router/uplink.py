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

from __future__ import absolute_import

from twisted.internet.defer import Deferred, inlineCallbacks

from autobahn.wamp import auth
from autobahn.wamp.types import SubscribeOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

from txaio import make_logger

__all__ = ('LocalSession',)


class BridgeSession(ApplicationSession):

    log = make_logger()

    @inlineCallbacks
    def _setup_event_forwarding(self, other):

        self.log.info("setup event forwarding between {me} and {other} ..", me=self, other=other)

        self._subs = {}

        # listen to when new subscriptions are created on the router
        #
        @inlineCallbacks
        def on_subscription_create(sub_id, sub_details, details=None):
            self.log.info(
                "Subscription created: {me} {sub_id} {sub_details} {details}",
                me=self,
                sub_id=sub_id,
                sub_details=sub_details,
                details=details,
            )

            self._subs[sub_id] = sub_details

            uri = sub_details['uri']

            def on_event(*args, **kwargs):
                details = kwargs.pop('details')
                # FIXME: setup things so out (the node's) identity gets disclosed
                self.publish(uri, *args, options=PublishOptions(), **kwargs)
                self.log.info(
                    "forwarded from {other} event to {me} ({dir}): args={args}, details={details}",
                    other=other,
                    me=self,
                    dir=self._DIR,
                    args=args,
                    details=details,
                )

            sub = yield other.subscribe(on_event, uri, options=SubscribeOptions(details_arg="details"))
            self._subs[sub_id]['sub'] = sub

            self.log.info("{other} subscribed to {me}".format(other=other, me=uri))

        yield self.subscribe(on_subscription_create, u"wamp.subscription.on_create", options=SubscribeOptions(details_arg="details"))

        # listen to when a subscription is removed from the router
        #
        @inlineCallbacks
        def on_subscription_delete(session_id, sub_id, details=None):
            self.log.info(
                "Subscription deleted: {me} {session} {sub_id} {details}",
                me=self,
                session=session_id,
                sub_id=sub_id,
                details=details,
            )

            sub_details = self._subs.get(sub_id, None)
            if not sub_details:
                self.log.info("subscription not tracked - huh??")
                return

            uri = sub_details['uri']

            yield self._subs[sub_id]['sub'].unsubscribe()

            del self._subs[sub_id]

            self.log.info("{other} unsubscribed from {uri}".format(other=other, uri=uri))

        yield self.subscribe(on_subscription_delete, u"wamp.subscription.on_delete", options=SubscribeOptions(details_arg="details"))

        # get current subscriptions on the router
        #
        subs = yield self.call(u"wamp.subscription.list")
        for sub_id in subs['exact']:
            sub = yield self.call(u"wamp.subscription.get", sub_id)
            yield on_subscription_create(sub['id'], sub)

        self.log.info("event forwarding setup done.")


class LocalSession(BridgeSession):
    """
    This session is the local leg of the router uplink and runs embedded inside the local router.
    """

    log = make_logger()

    _DIR = "=>"

    @inlineCallbacks
    def onJoin(self, details):
        uplink_config = self.config.extra['uplink']
        uplink_realm = details.realm
        uplink_transport = uplink_config['transport']

        extra = {
            'onready': Deferred(),
            'local': self,
        }
        runner = ApplicationRunner(url=uplink_transport['url'], realm=uplink_realm, extra=extra)
        yield runner.run(RemoteSession, start_reactor=False)

        edge_session = yield extra['onready']

        yield self._setup_event_forwarding(edge_session)

        if self.config.extra and 'onready' in self.config.extra:
            self.config.extra['onready'].callback(self)


class RemoteSession(BridgeSession):
    """
    This session is the remote leg of the router uplink.
    """

    log = make_logger()

    _DIR = "<="

    def onConnect(self):
        self.log.info("Uplink connected")

        realm = self.config.realm
        authid = self.config.extra.get('authid', None)
        if authid:
            self.log.debug("Uplink - joining realm '{realm}' as '{authid}' ..", realm=realm, authid=authid)
            self.join(realm, [u"wampcra"], authid)
        else:
            self.log.debug("Uplink - joining realm '{realm}' ..", realm=realm)
            self.join(realm)

    def onChallenge(self, challenge):
        if challenge.method == u"wampcra":
            authkey = self.config.extra['authkey'].encode('utf8')
            signature = auth.compute_wcs(authkey, challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        else:
            raise Exception("don't know how to compute challenge for authmethod {}".format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("Uplink joined realm '{realm}' on uplink router", realm=details.realm)

        yield self._setup_event_forwarding(self.config.extra['local'])

        if self.config.extra and 'onready' in self.config.extra:
            self.config.extra['onready'].callback(self)

        self.log.info("Uplink ready.")

    def onLeave(self, details):
        if details.reason != u"wamp.close.normal":
            self.log.warn("Uplink left: {defailts}", details=details)
        else:
            self.log.debug("Uplink detached: {details}", details=details)
        self.disconnect()

    def onDisconnect(self):
        self.log.info("Uplink disconnected")
