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

from autobahn import util
from autobahn.wamp import role
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError

from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY, \
    _URI_PAT_LOOSE_NON_EMPTY, _URI_PAT_STRICT_EMPTY, _URI_PAT_LOOSE_EMPTY

from crossbar.router.observation import UriObservationMap
from crossbar.router import RouterOptions, RouterAction

import txaio

__all__ = ('Broker',)


class Broker(object):
    """
    Basic WAMP broker.
    """

    def __init__(self, router, options=None):
        """

        :param router: The router this dealer is part of.
        :type router: Object that implements :class:`crossbar.router.interfaces.IRouter`.
        :param options: Router options.
        :type options: Instance of :class:`crossbar.router.types.RouterOptions`.
        """
        self._router = router
        self._options = options or RouterOptions()

        # subscription map managed by this broker
        self._subscription_map = UriObservationMap()

        # map: session -> set of subscriptions (needed for detach)
        self._session_to_subscriptions = {}

        # check all topic URIs with strict rules
        self._option_uri_strict = self._options.uri_check == RouterOptions.URI_CHECK_STRICT

        # supported features from "WAMP Advanced Profile"
        self._role_features = role.RoleBrokerFeatures(publisher_identification=True,
                                                      pattern_based_subscription=True,
                                                      subscription_meta_api=True,
                                                      subscriber_blackwhite_listing=True,
                                                      publisher_exclusion=True,
                                                      subscription_revocation=True)

    def attach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.attach`
        """
        if session not in self._session_to_subscriptions:
            self._session_to_subscriptions[session] = set()
        else:
            raise Exception(u"session with ID {} already attached".format(session._session_id))

    def detach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.detach`
        """
        if session in self._session_to_subscriptions:

            for subscription in self._session_to_subscriptions[session]:

                was_subscribed, was_last_subscriber = self._subscription_map.drop_observer(session, subscription)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not subscription.uri.startswith(u'wamp.'):
                        if was_subscribed:
                            service_session.publish(u'wamp.subscription.on_unsubscribe', session._session_id, subscription.id)
                        if was_last_subscriber:
                            service_session.publish(u'wamp.subscription.on_delete', session._session_id, subscription.id)

            del self._session_to_subscriptions[session]

        else:
            raise Exception("session with ID {} not attached".format(session._session_id))

    def processPublish(self, session, publish):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processPublish`
        """
        # check topic URI: for PUBLISH, must be valid URI (either strict or loose), and
        # all URI components must be non-empty
        if self._option_uri_strict:
            uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(publish.topic)
        else:
            uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(publish.topic)

        if not uri_is_valid:
            if publish.acknowledge:
                reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, [u"publish with invalid topic URI '{0}' (URI strict checking {1})".format(publish.topic, self._option_uri_strict)])
                session._transport.send(reply)
            return

        # disallow publication to topics starting with "wamp." and
        # "crossbar." other than for trusted session (that are sessions
        # built into Crossbar.io)
        if session._authrole is not None and session._authrole != u"trusted":
            if publish.topic.startswith(u"wamp.") or publish.topic.startswith(u"crossbar."):
                if publish.acknowledge:
                    reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, [u"publish with restricted topic URI '{0}'".format(publish.topic)])
                    session._transport.send(reply)
                return

        # get subscriptions active on the topic published to
        #
        subscriptions = self._subscription_map.match_observations(publish.topic)

        # go on if there are any active subscriptions or the publish is to be acknowledged
        # otherwise there isn't anything to do anyway.
        #
        if subscriptions or publish.acknowledge:

            # validate payload
            #
            try:
                self._router.validate('event', publish.topic, publish.args, publish.kwargs)
            except Exception as e:
                if publish.acknowledge:
                    reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_ARGUMENT, [u"publish to topic URI '{0}' with invalid application payload: {1}".format(publish.topic, e)])
                    session._transport.send(reply)
                return

            # authorize PUBLISH action
            #
            d = txaio.as_future(self._router.authorize, session, publish.topic, RouterAction.ACTION_PUBLISH)

            def on_authorize_success(authorized):

                # the call to authorize the action _itself_ succeeded. now go on depending on whether
                # the action was actually authorized or not ..
                #
                if not authorized:

                    if publish.acknowledge:
                        reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.NOT_AUTHORIZED, [u"session not authorized to publish to topic '{0}'".format(publish.topic)])
                        session._transport.send(reply)

                else:

                    # new ID for the publication
                    #
                    publication = util.id()

                    # send publish acknowledge immediately when requested
                    #
                    if publish.acknowledge:
                        msg = message.Published(publish.request, publication)
                        session._transport.send(msg)

                    # publisher disclosure
                    #
                    if publish.disclose_me:
                        publisher = session._session_id
                    else:
                        publisher = None

                    # skip publisher
                    #
                    if publish.exclude_me is None or publish.exclude_me:
                        me_also = False
                    else:
                        me_also = True

                    # iterate over all subscriptions ..
                    #
                    for subscription in subscriptions:

                        # initial list of receivers are all subscribers on a subscription ..
                        #
                        receivers = subscription.observers

                        # filter by "eligible" receivers
                        #
                        if publish.eligible:

                            # map eligible session IDs to eligible sessions
                            eligible = []
                            for session_id in publish.eligible:
                                if session_id in self._router._session_id_to_session:
                                    eligible.append(self._router._session_id_to_session[session_id])

                            # filter receivers for eligible sessions
                            receivers = set(eligible) & receivers

                        # remove "excluded" receivers
                        #
                        if publish.exclude:

                            # map excluded session IDs to excluded sessions
                            exclude = []
                            for s in publish.exclude:
                                if s in self._router._session_id_to_session:
                                    exclude.append(self._router._session_id_to_session[s])

                            # filter receivers for excluded sessions
                            if exclude:
                                receivers = receivers - set(exclude)

                        # if receivers is non-empty, dispatch event ..
                        #
                        if receivers:

                            # for pattern-based subscriptions, the EVENT must contain
                            # the actual topic being published to
                            #
                            if subscription.match != message.Subscribe.MATCH_EXACT:
                                topic = publish.topic
                            else:
                                topic = None

                            msg = message.Event(subscription.id,
                                                publication,
                                                args=publish.args,
                                                kwargs=publish.kwargs,
                                                publisher=publisher,
                                                topic=topic)
                            for receiver in receivers:
                                if me_also or receiver != session:
                                    # the receiving subscriber session might have been lost in the meantime ..
                                    if receiver._transport:
                                        receiver._transport.send(msg)

            def on_authorize_error(err):

                # the call to authorize the action _itself_ failed (note this is different from the
                # call to authorize succeed, but the authorization being denied)
                #
                if publish.acknowledge:
                    reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.AUTHORIZATION_FAILED, [u"failed to authorize session for publishing to topic URI '{0}': {1}".format(publish.topic, err.value)])
                    session._transport.send(reply)

            txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processSubscribe(self, session, subscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processSubscribe`
        """
        # check topic URI: for SUBSCRIBE, must be valid URI (either strict or loose), and all
        # URI components must be non-empty other than for wildcard subscriptions
        #
        if self._option_uri_strict:
            if subscribe.match == u"wildcard":
                uri_is_valid = _URI_PAT_STRICT_EMPTY.match(subscribe.topic)
            else:
                uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(subscribe.topic)
        else:
            if subscribe.match == u"wildcard":
                uri_is_valid = _URI_PAT_LOOSE_EMPTY.match(subscribe.topic)
            else:
                uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(subscribe.topic)

        if not uri_is_valid:
            reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.INVALID_URI, [u"subscribe for invalid topic URI '{0}'".format(subscribe.topic)])
            session._transport.send(reply)
            return

        # authorize action
        #
        d = txaio.as_future(self._router.authorize, session, subscribe.topic, RouterAction.ACTION_SUBSCRIBE)

        def on_authorize_success(authorized):
            if not authorized:
                # error reply since session is not authorized to subscribe
                #
                reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to subscribe to topic '{0}'".format(subscribe.topic)])

            else:
                # ok, session authorized to subscribe. now get the subscription
                #
                subscription, was_already_subscribed, is_first_subscriber = self._subscription_map.add_observer(session, subscribe.topic, subscribe.match)

                if not was_already_subscribed:
                    self._session_to_subscriptions[session].add(subscription)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not subscription.uri.startswith(u'wamp.'):
                        if is_first_subscriber:
                            subscription_details = {
                                'id': subscription.id,
                                'created': subscription.created,
                                'uri': subscription.uri,
                                'match': subscription.match,
                            }
                            service_session.publish(u'wamp.subscription.on_create', session._session_id, subscription_details)
                        if not was_already_subscribed:
                            service_session.publish(u'wamp.subscription.on_subscribe', session._session_id, subscription.id)

                # acknowledge subscribe with subscription ID
                #
                reply = message.Subscribed(subscribe.request, subscription.id)

            # send out reply to subscribe requestor
            #
            session._transport.send(reply)

        def on_authorize_error(err):
            # the call to authorize the action _itself_ failed (note this is different from the
            # call to authorize succeed, but the authorization being denied)
            #
            reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.AUTHORIZATION_FAILED, [u"failed to authorize session for subscribing to topic URI '{0}': {1}".format(subscribe.topic, err.value)])
            session._transport.send(reply)

        txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processUnsubscribe(self, session, unsubscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processUnsubscribe`
        """
        # get subscription by subscription ID or None (if it doesn't exist on this broker)
        #
        subscription = self._subscription_map.get_observation_by_id(unsubscribe.subscription)

        if subscription:

            if session in subscription.observers:

                was_subscribed, was_last_subscriber = self._unsubscribe(subscription, session)

                reply = message.Unsubscribed(unsubscribe.request)
            else:
                # subscription exists on this broker, but the session that wanted to unsubscribe wasn't subscribed
                #
                reply = message.Error(message.Unsubscribe.MESSAGE_TYPE, unsubscribe.request, ApplicationError.NO_SUCH_SUBSCRIPTION)

        else:
            # subscription doesn't even exist on this broker
            #
            reply = message.Error(message.Unsubscribe.MESSAGE_TYPE, unsubscribe.request, ApplicationError.NO_SUCH_SUBSCRIPTION)

        session._transport.send(reply)

    def _unsubscribe(self, subscription, session):

        # drop session from subscription observers
        #
        was_subscribed, was_last_subscriber = self._subscription_map.drop_observer(session, subscription)

        # remove subscription from session->subscriptions map
        #
        if was_subscribed:
            self._session_to_subscriptions[session].discard(subscription)

        # publish WAMP meta events
        #
        if self._router._realm:
            service_session = self._router._realm.session
            if service_session and not subscription.uri.startswith(u'wamp.'):
                if was_subscribed:
                    service_session.publish(u'wamp.subscription.on_unsubscribe', session._session_id, subscription.id)
                if was_last_subscriber:
                    service_session.publish(u'wamp.subscription.on_delete', session._session_id, subscription.id)

        return was_subscribed, was_last_subscriber

    def removeSubscriber(self, subscription, session, reason=None):
        """
        Actively unsubscribe a subscriber session from a subscription.
        """
        was_subscribed, was_last_subscriber = self._unsubscribe(subscription, session)

        if 'subscriber' in session._session_roles and session._session_roles['subscriber'] and session._session_roles['subscriber'].subscription_revocation:
            reply = message.Unsubscribed(0, subscription=subscription.id, reason=reason)
            session._transport.send(reply)

        return was_subscribed, was_last_subscriber
