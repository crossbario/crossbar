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

from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY, _URI_PAT_LOOSE_NON_EMPTY
from autobahn.twisted.wamp import FutureMixin

from crossbar.router.subscription import SubscriptionMap
from crossbar.router.types import RouterOptions
from crossbar.router.interfaces import IRouter

__all__ = ('Broker',)


class Broker(FutureMixin):

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
        self._subscription_map = SubscriptionMap()

        # map: session_id -> session (needed for exclude/eligible)
        self._session_id_to_session = {}

        # check all topic URIs with strict rules
        self._option_uri_strict = self._options.uri_check == RouterOptions.URI_CHECK_STRICT

        # supported features from "WAMP Advanced Profile"
        self._role_features = role.RoleBrokerFeatures(publisher_identification=True, subscriber_blackwhite_listing=True, publisher_exclusion=True)

    def attach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.attach`
        """
        if session._session_id not in self._session_id_to_session:
            self._session_id_to_session[session._session_id] = session
        else:
            raise Exception("session with ID {} already attached".format(session._session_id))

    def detach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.detach`
        """
        if session._session_id in self._session_id_to_session:
            del self._session_id_to_session[session._session_id]
        else:
            raise Exception("session with ID {} not attached".format(session._session_id))

    def processPublish(self, session, publish):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processPublish`
        """
        # check topic URI
        #
        if (not self._option_uri_strict and not _URI_PAT_LOOSE_NON_EMPTY.match(publish.topic)) or \
           (self._option_uri_strict and not _URI_PAT_STRICT_NON_EMPTY.match(publish.topic)):

            if publish.acknowledge:
                reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, ["publish with invalid topic URI '{0}'".format(publish.topic)])
                session._transport.send(reply)

            return

        # get subscriptions active on the topic published to
        #
        subscriptions = self._subscription_map.get_subscriptions(publish.topic)

        # go on if there are any active subscriptions or the publish is to be acknowledged
        #
        if subscriptions or publish.acknowledge:

            # new ID for the publication
            #
            publication = util.id()

            # send publish acknowledge immediately when requested
            #
            if publish.acknowledge:
                msg = message.Published(publish.request, publication)
                session._transport.send(msg)

            # publisher disclosure (FIXME: too simplistic)
            #
            if publish.discloseMe:
                publisher = session._session_id
            else:
                publisher = None

            # skip publisher
            #
            if publish.excludeMe is None or publish.excludeMe:
                me_also = False
            else:
                me_also = True

            # iterate over all subscriptions ..
            #
            for subscription in subscriptions:

                # initial list of receivers are all subscribers on a subscription ..
                #
                receivers = subscription.subscribers

                # filter by "eligible" receivers
                #
                if publish.eligible:

                    # map eligible session IDs to eligible sessions
                    eligible = []
                    for session_id in publish.eligible:
                        if session_id in self._session_id_to_session:
                            eligible.append(self._session_id_to_session[session_id])

                    # filter receivers for eligible sessions
                    receivers = set(eligible) & receivers

                # remove "excluded" receivers
                #
                if publish.exclude:

                    # map excluded session IDs to excluded sessions
                    exclude = []
                    for s in publish.exclude:
                        if s in self._session_id_to_session:
                            exclude.append(self._session_id_to_session[s])

                    # filter receivers for excluded sessions
                    if exclude:
                        receivers = receivers - set(exclude)

                # if receivers is non-empty, dispatch event ..
                #
                if receivers:
                    msg = message.Event(subscription.id,
                                        publication,
                                        args=publish.args,
                                        kwargs=publish.kwargs,
                                        publisher=publisher)
                    for receiver in receivers:
                        if me_also or receiver != session:
                            # the receiving subscriber session might have been lost in the meantime ..
                            if receiver._transport:
                                receiver._transport.send(msg)

        # if publish.topic in self._topic_to_sessions or publish.acknowledge:

        #     # validate payload
        #     #
        #     try:
        #         self._router.validate('event', publish.topic, publish.args, publish.kwargs)
        #     except Exception as e:
        #         reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_ARGUMENT, ["publish to topic URI '{0}' with invalid application payload: {1}".format(publish.topic, e)])
        #         session._transport.send(reply)
        #         return

        #     # authorize action
        #     #
        #     d = self._as_future(self._router.authorize, session, publish.topic, IRouter.ACTION_PUBLISH)

        #     def on_authorize_success(authorized):

        #         if not authorized:

        #             if publish.acknowledge:
        #                 reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.NOT_AUTHORIZED, ["session not authorized to publish to topic '{0}'".format(publish.topic)])
        #                 session._transport.send(reply)

        #         else:

        #             # continue processing if either a) there are subscribers to the topic or b) the publish is to be acknowledged
        #             #
        #             if publish.topic in self._topic_to_sessions and self._topic_to_sessions[publish.topic]:

        #                 # initial list of receivers are all subscribers ..
        #                 #
        #                 subscription, receivers = self._topic_to_sessions[publish.topic]

        #                 # filter by "eligible" receivers
        #                 #
        #                 if publish.eligible:
        #                     eligible = []
        #                     for s in publish.eligible:
        #                         if s in self._session_id_to_session:
        #                             eligible.append(self._session_id_to_session[s])

        #                     receivers = set(eligible) & receivers

        #                 # remove "excluded" receivers
        #                 #
        #                 if publish.exclude:
        #                     exclude = []
        #                     for s in publish.exclude:
        #                         if s in self._session_id_to_session:
        #                             exclude.append(self._session_id_to_session[s])
        #                     if exclude:
        #                         receivers = receivers - set(exclude)

        #                 # remove publisher
        #                 #
        #                 if publish.excludeMe is None or publish.excludeMe:
        #                     #   receivers.discard(session) # bad: this would modify our actual subscriber list
        #                     me_also = False
        #                 else:
        #                     me_also = True

        #             else:
        #                 subscription, receivers, me_also = None, [], False

        #             publication = util.id()

        #             # send publish acknowledge when requested
        #             #
        #             if publish.acknowledge:
        #                 msg = message.Published(publish.request, publication)
        #                 session._transport.send(msg)

        #             # if receivers is non-empty, dispatch event ..
        #             #
        #             if receivers:
        #                 if publish.discloseMe:
        #                     publisher = session._session_id
        #                 else:
        #                     publisher = None
        #                 msg = message.Event(subscription,
        #                                     publication,
        #                                     args=publish.args,
        #                                     kwargs=publish.kwargs,
        #                                     publisher=publisher)
        #                 for receiver in receivers:
        #                     if me_also or receiver != session:
        #                         # the subscribing session might have been lost in the meantime ..
        #                         if receiver._transport:
        #                             receiver._transport.send(msg)

        #     def on_authorize_error(err):
        #         if publish.acknowledge:
        #             reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.AUTHORIZATION_FAILED, ["failed to authorize session for publishing to topic URI '{0}': {1}".format(publish.topic, err.value)])
        #             session._transport.send(reply)

        #     self._add_future_callbacks(d, on_authorize_success, on_authorize_error)

    def processSubscribe(self, session, subscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processSubscribe`
        """
        # check topic URI
        #
        if (not self._option_uri_strict and not _URI_PAT_LOOSE_NON_EMPTY.match(subscribe.topic)) or \
           (self._option_uri_strict and not _URI_PAT_STRICT_NON_EMPTY.match(subscribe.topic)):

            # invalid URI for topic
            #
            reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.INVALID_URI, ["subscribe for invalid topic URI '{0}'".format(subscribe.topic)])
            session._transport.send(reply)

        else:

            # authorize action
            #
            d = self._as_future(self._router.authorize, session, subscribe.topic, IRouter.ACTION_SUBSCRIBE)

            def on_authorize_success(authorized):
                if not authorized:
                    # error reply since session is not authorized to subscribe
                    #
                    reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.NOT_AUTHORIZED, ["session is not authorized to subscribe to topic '{0}'".format(subscribe.topic)])

                else:
                    # ok, session authorized to subscribe. now get the subscription
                    #
                    subscription, was_already_subscribed, is_first_subscriber = self._subscription_map.add_subscriber(session, subscribe.topic, subscribe.match)

                    # publish WAMP meta events
                    #
                    if self._router._realm:
                        service_session = self._router._realm.session
                        if service_session and not subscribe.topic.startswith(u'wamp.topic'):
                            if is_first_subscriber:
                                print "on_first_subscribe"
                                service_session.publish(u'wamp.topic.on_first_subscribe', session._session_id, subscription.__getstate__())
                            if not was_already_subscribed:
                                print "on_subscribe"
                                service_session.publish(u'wamp.topic.on_subscribe', session._session_id, subscription.id)

                    # acknowledge subscribe with subscription ID
                    #
                    reply = message.Subscribed(subscribe.request, subscription.id)

                # send out reply to subscribe requestor
                #
                session._transport.send(reply)

            def on_authorize_error(err):
                # authorization itself failed (not this is different from authorization done, but not authorized)
                #
                reply = message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.AUTHORIZATION_FAILED, ["failed to authorize session for subscribing to topic URI '{0}': {1}".format(subscribe.topic, err.value)])
                session._transport.send(reply)

            self._add_future_callbacks(d, on_authorize_success, on_authorize_error)

    def processUnsubscribe(self, session, unsubscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processUnsubscribe`
        """
        print "processUnsubscribe"
        return
        # assert(session in self._session_to_subscriptions)

        if unsubscribe.subscription in self._subscription_to_sessions:

            topic, subscribers = self._subscription_to_sessions[unsubscribe.subscription]

            subscribers.discard(session)

            if not subscribers:
                del self._subscription_to_sessions[unsubscribe.subscription]

            _, subscribers = self._topic_to_sessions[topic]

            subscribers.discard(session)

            if not subscribers:
                del self._topic_to_sessions[topic]

            self._session_to_subscriptions[session].discard(unsubscribe.subscription)

            reply = message.Unsubscribed(unsubscribe.request)

        else:
            reply = message.Error(message.Unsubscribe.MESSAGE_TYPE, unsubscribe.request, ApplicationError.NO_SUCH_SUBSCRIPTION)

        session._transport.send(reply)
