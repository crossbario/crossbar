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

from __future__ import absolute_import, division

import txaio

from autobahn import util
from autobahn.wamp import role
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError

from autobahn.wamp.message import \
    _URI_PAT_STRICT_NON_EMPTY, _URI_PAT_LOOSE_NON_EMPTY, \
    _URI_PAT_STRICT_EMPTY, _URI_PAT_LOOSE_EMPTY, \
    _URI_PAT_STRICT_LAST_EMPTY, _URI_PAT_LOOSE_LAST_EMPTY

from crossbar.router.observation import UriObservationMap
from crossbar.router import RouterOptions

from txaio import make_logger

__all__ = ('Broker',)


class SubscriptionExtra(object):

    __slots__ = ('retained_events',)

    def __init__(self, retained_events=None):
        self.retained_events = retained_events or []


class Broker(object):
    """
    Basic WAMP broker.
    """

    log = make_logger()

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
                                                      session_meta_api=True,
                                                      subscription_meta_api=True,
                                                      subscriber_blackwhite_listing=True,
                                                      publisher_exclusion=True,
                                                      subscription_revocation=True,
                                                      event_retention=True,
                                                      payload_transparency=True,
                                                      payload_encryption_cryptobox=True)

        # store for event history
        if self._router._store:
            self._event_store = self._router._store.event_store
        else:
            self._event_store = None

        # if there is a store, let the store attach itself to all the subscriptions
        # it is configured to track
        if self._event_store:
            self._event_store.attach_subscription_map(self._subscription_map)

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
                was_deleted = False

                # delete it if there are no subscribers and no retained events
                #
                if was_subscribed and was_last_subscriber and not subscription.extra.retained_events:
                    was_deleted = True
                    self._subscription_map.delete_observation(subscription)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not subscription.uri.startswith(u'wamp.'):
                        if was_subscribed:
                            service_session.publish(u'wamp.subscription.on_unsubscribe', session._session_id, subscription.id)
                        if was_deleted:
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
                self._router.send(session, reply)
            return

        # disallow publication to topics starting with "wamp." other than for
        # trusted sessions (that are sessions built into Crossbar.io routing core)
        #
        if session._authrole is not None and session._authrole != u"trusted":
            is_restricted = publish.topic.startswith(u"wamp.")
            if is_restricted:
                if publish.acknowledge:
                    reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, [u"publish with restricted topic URI '{0}'".format(publish.topic)])
                    self._router.send(session, reply)
                return

        # get subscriptions active on the topic published to
        #
        subscriptions = self._subscription_map.match_observations(publish.topic)

        # check if the event is being persisted by checking if we ourself are among the observers
        # on _any_ matching subscription
        # we've been previously added to observer lists on subscriptions ultimately from
        # node configuration and during the broker starts up.
        store_event = False
        if self._event_store:
            for subscription in subscriptions:
                if self._event_store in subscription.observers:
                    store_event = True
                    break
        if store_event:
            self.log.debug('Persisting event on topic "{topic}"', topic=publish.topic)

        # check if the event is to be retained by inspecting the 'retain' flag
        retain_event = False
        if publish.retain:
            retain_event = True

        # go on if (otherwise there isn't anything to do anyway):
        #
        #   - there are any active subscriptions OR
        #   - the publish is to be acknowledged OR
        #   - the event is to be persisted OR
        #   - the event is to be retained
        #
        if subscriptions or publish.acknowledge or store_event or retain_event:

            # If it's a MQTT publish, we need to adjust the arguments.
            if getattr(publish, "_mqtt_publish", False):
                from crossbar.adapter.mqtt.wamp import mqtt_payload_transform
                tfd = mqtt_payload_transform(self._router._mqtt_payload_format,
                                             publish.payload)

                if not tfd:
                    # If we have no message to give, drop it entirely
                    return
                else:
                    publish.payload = None
                    publish.args, publish.kwargs = tfd

            # validate payload
            #
            if publish.payload is None:
                try:
                    self._router.validate('event', publish.topic, publish.args, publish.kwargs)
                except Exception as e:
                    if publish.acknowledge:
                        reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_ARGUMENT, [u"publish to topic URI '{0}' with invalid application payload: {1}".format(publish.topic, e)])
                        self._router.send(session, reply)
                    return

            # authorize PUBLISH action
            #
            d = self._router.authorize(session, publish.topic, u'publish')

            def on_authorize_success(authorization):

                # the call to authorize the action _itself_ succeeded. now go on depending on whether
                # the action was actually authorized or not ..
                #
                if not authorization[u'allow']:

                    if publish.acknowledge:
                        reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.NOT_AUTHORIZED, [u"session not authorized to publish to topic '{0}'".format(publish.topic)])
                        self._router.send(session, reply)

                else:

                    # new ID for the publication
                    #
                    publication = util.id()

                    # persist event (this is done only once, regardless of the number of subscriptions
                    # the event matches on)
                    #
                    if store_event:
                        self._event_store.store_event(session._session_id, publication, publish.topic, publish.args, publish.kwargs)

                    # retain event on the topic
                    #
                    if retain_event:
                        observation = self._subscription_map.get_observation(publish.topic)

                        if not observation:
                            # No observation, lets make a new one
                            observation = self._subscription_map.create_observation(publish.topic, extra=SubscriptionExtra())

                        if observation.extra.retained_events:
                            if not publish.eligible and not publish.exclude:
                                observation.extra.retained_events = [publish]
                            else:
                                observation.extra.retained_events.append(publish)
                        else:
                            observation.extra.retained_events = [publish]

                    # send publish acknowledge immediately when requested
                    #
                    if publish.acknowledge:
                        reply = message.Published(publish.request, publication)
                        self._router.send(session, reply)

                    # publisher disclosure
                    #
                    if authorization[u'disclose']:
                        disclose = True
                    elif (publish.topic.startswith(u"wamp.") or
                          publish.topic.startswith(u"crossbar.")):
                        disclose = True
                    else:
                        disclose = False

                    if disclose:
                        publisher = session._session_id
                        publisher_authid = session._authid
                        publisher_authrole = session._authrole
                    else:
                        publisher = None
                        publisher_authid = None
                        publisher_authrole = None

                    # skip publisher
                    #
                    if publish.exclude_me is None or publish.exclude_me:
                        me_also = False
                    else:
                        me_also = True

                    # iterate over all subscriptions ..
                    #
                    for subscription in subscriptions:

                        # persist event history, but check if it is persisted on the individual subscription!
                        #
                        if store_event and self._event_store in subscription.observers:
                            self._event_store.store_event_history(publication, subscription.id)

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
                        receivers_cnt = len(receivers) - (1 if self in receivers else 0)
                        if receivers_cnt:

                            # for pattern-based subscriptions, the EVENT must contain
                            # the actual topic being published to
                            #
                            if subscription.match != message.Subscribe.MATCH_EXACT:
                                topic = publish.topic
                            else:
                                topic = None

                            if publish.payload:
                                msg = message.Event(subscription.id,
                                                    publication,
                                                    payload=publish.payload,
                                                    publisher=publisher,
                                                    publisher_authid=publisher_authid,
                                                    publisher_authrole=publisher_authrole,
                                                    topic=topic,
                                                    enc_algo=publish.enc_algo,
                                                    enc_key=publish.enc_key,
                                                    enc_serializer=publish.enc_serializer)
                            else:
                                msg = message.Event(subscription.id,
                                                    publication,
                                                    args=publish.args,
                                                    kwargs=publish.kwargs,
                                                    publisher=publisher,
                                                    publisher_authid=publisher_authid,
                                                    publisher_authrole=publisher_authrole,
                                                    topic=topic)
                            for receiver in receivers:
                                if (me_also or receiver != session) and receiver != self._event_store:
                                    # the receiving subscriber session
                                    # might have no transport, or no
                                    # longer be joined
                                    if receiver._session_id and receiver._transport:
                                        self._router.send(receiver, msg)

            def on_authorize_error(err):
                """
                the call to authorize the action _itself_ failed (note this is
                different from the call to authorize succeed, but the
                authorization being denied)
                """
                self.log.failure("Authorization failed", failure=err)
                if publish.acknowledge:
                    reply = message.Error(
                        message.Publish.MESSAGE_TYPE,
                        publish.request,
                        ApplicationError.AUTHORIZATION_FAILED,
                        [u"failed to authorize session for publishing to topic URI '{0}': {1}".format(publish.topic, err.value)]
                    )
                    self._router.send(session, reply)

            txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processSubscribe(self, session, subscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processSubscribe`
        """
        # check topic URI: for SUBSCRIBE, must be valid URI (either strict or loose), and all
        # URI components must be non-empty for normal subscriptions, may be empty for
        # wildcard subscriptions and must be non-empty for all but the last component for
        # prefix subscriptions
        #
        if self._option_uri_strict:
            if subscribe.match == u"wildcard":
                uri_is_valid = _URI_PAT_STRICT_EMPTY.match(subscribe.topic)
            elif subscribe.match == u"prefix":
                uri_is_valid = _URI_PAT_STRICT_LAST_EMPTY.match(subscribe.topic)
            else:
                uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(subscribe.topic)
        else:
            if subscribe.match == u"wildcard":
                uri_is_valid = _URI_PAT_LOOSE_EMPTY.match(subscribe.topic)
            elif subscribe.match == u"prefix":
                uri_is_valid = _URI_PAT_LOOSE_LAST_EMPTY.match(subscribe.topic)
            else:
                uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(subscribe.topic)

        if not uri_is_valid:
            reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.INVALID_URI, [u"subscribe for invalid topic URI '{0}'".format(subscribe.topic)])
            self._router.send(session, reply)
            return

        # authorize SUBSCRIBE action
        #
        d = self._router.authorize(session, subscribe.topic, u'subscribe')

        def on_authorize_success(authorization):
            if not authorization[u'allow']:
                # error reply since session is not authorized to subscribe
                #
                replies = [message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to subscribe to topic '{0}'".format(subscribe.topic)])]

            else:
                # ok, session authorized to subscribe. now get the subscription
                #
                subscription, was_already_subscribed, is_first_subscriber = self._subscription_map.add_observer(session, subscribe.topic, subscribe.match, extra=SubscriptionExtra())

                if not was_already_subscribed:
                    self._session_to_subscriptions[session].add(subscription)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not subscription.uri.startswith(u'wamp.'):
                        if is_first_subscriber:
                            subscription_details = {
                                u'id': subscription.id,
                                u'created': subscription.created,
                                u'uri': subscription.uri,
                                u'match': subscription.match,
                            }
                            service_session.publish(u'wamp.subscription.on_create', session._session_id, subscription_details)
                        if not was_already_subscribed:
                            service_session.publish(u'wamp.subscription.on_subscribe', session._session_id, subscription.id)

                # check for retained events
                #
                def _get_retained_event():

                    if subscription.extra.retained_events:
                        retained_events = list(subscription.extra.retained_events)
                        retained_events.reverse()

                        for publish in retained_events:
                            authorised = False

                            if not publish.exclude and not publish.eligible:
                                authorised = True
                            elif session._session_id in publish.eligible and session._session_id not in publish.exclude:
                                authorised = True

                            if authorised:
                                publication = util.id()

                                if publish.payload:
                                    msg = message.Event(subscription.id,
                                                        publication,
                                                        payload=publish.payload,
                                                        retained=True,
                                                        enc_algo=publish.enc_algo,
                                                        enc_key=publish.enc_key,
                                                        enc_serializer=publish.enc_serializer)
                                else:
                                    msg = message.Event(subscription.id,
                                                        publication,
                                                        args=publish.args,
                                                        kwargs=publish.kwargs,
                                                        retained=True)

                                return [msg]
                    return []

                # acknowledge subscribe with subscription ID
                #
                replies = [message.Subscribed(subscribe.request, subscription.id)]
                if subscribe.get_retained:
                    replies.extend(_get_retained_event())

            # send out reply to subscribe requestor
            #
            [self._router.send(session, reply) for reply in replies]

        def on_authorize_error(err):
            """
            the call to authorize the action _itself_ failed (note this is
            different from the call to authorize succeed, but the
            authorization being denied)
            """
            # XXX same as another code-block, can we collapse?
            self.log.failure("Authorization failed", failure=err)
            reply = message.Error(
                message.Subscribe.MESSAGE_TYPE,
                subscribe.request,
                ApplicationError.AUTHORIZATION_FAILED,
                [u"failed to authorize session for subscribing to topic URI '{0}': {1}".format(subscribe.topic, err.value)]
            )
            self._router.send(session, reply)

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

        self._router.send(session, reply)

    def _unsubscribe(self, subscription, session):

        # drop session from subscription observers
        #
        was_subscribed, was_last_subscriber = self._subscription_map.drop_observer(session, subscription)
        was_deleted = False

        if was_subscribed and was_last_subscriber and not subscription.extra.retained_events:
            was_deleted = True
            self._subscription_map.delete_observation(subscription)

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
                if was_deleted:
                    service_session.publish(u'wamp.subscription.on_delete', session._session_id, subscription.id)

        return was_subscribed, was_last_subscriber

    def removeSubscriber(self, subscription, session, reason=None):
        """
        Actively unsubscribe a subscriber session from a subscription.
        """
        was_subscribed, was_last_subscriber = self._unsubscribe(subscription, session)

        if 'subscriber' in session._session_roles and session._session_roles['subscriber'] and session._session_roles['subscriber'].subscription_revocation:
            reply = message.Unsubscribed(0, subscription=subscription.id, reason=reason)
            self._router.send(session, reply)

        return was_subscribed, was_last_subscriber
