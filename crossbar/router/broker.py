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

import copy

import txaio

from autobahn import util
from autobahn.wamp import role, message, types
from autobahn.wamp.exception import ApplicationError

from autobahn.wamp.message import \
    _URI_PAT_STRICT_NON_EMPTY, _URI_PAT_LOOSE_NON_EMPTY, \
    _URI_PAT_STRICT_EMPTY, _URI_PAT_LOOSE_EMPTY, \
    _URI_PAT_STRICT_LAST_EMPTY, _URI_PAT_LOOSE_LAST_EMPTY

from crossbar.router.observation import UriObservationMap
from crossbar.router import RouterOptions

from txaio import make_logger

__all__ = ('Broker',)


class RetainedEvent(object):

    __slots__ = (
        'publish',
        'publisher',
        'publisher_authid',
        'publisher_authrole',
    )

    def __init__(self,
                 publish,
                 publisher=None,
                 publisher_authid=None,
                 publisher_authrole=None):
        self.publish = publish
        self.publisher = publisher
        self.publisher_authid = publisher_authid
        self.publisher_authrole = publisher_authrole


class SubscriptionExtra(object):

    __slots__ = ('retained_events',)

    def __init__(self, retained_events=None):
        self.retained_events = retained_events or []


class Broker(object):
    """
    Basic WAMP broker.
    """

    log = make_logger()

    def __init__(self, router, reactor, options=None):
        """

        :param router: The router this broker is part of.
        :type router: Object that implements :class:`crossbar.router.interfaces.IRouter`.

        :param options: Router options.
        :type options: Instance of :class:`crossbar.router.types.RouterOptions`.
        """
        self._router = router
        self._reactor = reactor
        self._options = options or RouterOptions()

        # generator for WAMP request IDs
        self._request_id_gen = util.IdGenerator()

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

                # publish WAMP meta events, if we have a service session, but
                # not for the meta API itself!
                #
                if self._router._realm and \
                   self._router._realm.session and \
                   not subscription.uri.startswith(u'wamp.'):

                    def _publish(subscription):
                        service_session = self._router._realm.session
                        options = types.PublishOptions(
                            correlation_id=None,
                            correlation_is_anchor=True,
                            correlation_is_last=False
                        )
                        if was_subscribed:
                            service_session.publish(
                                u'wamp.subscription.on_unsubscribe',
                                session._session_id,
                                subscription.id,
                                options=options,
                            )
                        if was_deleted:
                            options.correlation_is_last = True
                            service_session.publish(
                                u'wamp.subscription.on_delete',
                                session._session_id,
                                subscription.id,
                                options=options,
                            )
                    # we postpone actual sending of meta events until we return to this client session
                    self._reactor.callLater(0, _publish, subscription)

            del self._session_to_subscriptions[session]

        else:
            raise Exception("session with ID {} not attached".format(session._session_id))

    def _filter_publish_receivers(self, receivers, publish):
        """
        Internal helper.

        Does all filtering on a candidate set of Publish receivers,
        based on all the white/blacklist options in 'publish'.
        """
        # filter by "eligible" receivers
        #
        if publish.eligible:

            # map eligible session IDs to eligible sessions
            eligible = set()
            for session_id in publish.eligible:
                if session_id in self._router._session_id_to_session:
                    eligible.add(self._router._session_id_to_session[session_id])

            # filter receivers for eligible sessions
            receivers = eligible & receivers

        # if "eligible_authid" we only accept receivers that have the correct authid
        if publish.eligible_authid:
            eligible = set()
            for aid in publish.eligible_authid:
                eligible.update(self._router._authid_to_sessions.get(aid, set()))
            receivers = receivers & eligible

        # if "eligible_authrole" we only accept receivers that have the correct authrole
        if publish.eligible_authrole:
            eligible = set()
            for ar in publish.eligible_authrole:
                eligible.update(self._router._authrole_to_sessions.get(ar, set()))
            receivers = receivers & eligible

        # remove "excluded" receivers
        #
        if publish.exclude:

            # map excluded session IDs to excluded sessions
            exclude = set()
            for s in publish.exclude:
                if s in self._router._session_id_to_session:
                    exclude.add(self._router._session_id_to_session[s])

            # filter receivers for excluded sessions
            if exclude:
                receivers = receivers - exclude

        # remove auth-id based receivers
        if publish.exclude_authid:
            for aid in publish.exclude_authid:
                receivers = receivers - self._router._authid_to_sessions.get(aid, set())

        # remove authrole based receivers
        if publish.exclude_authrole:
            for ar in publish.exclude_authrole:
                receivers = receivers - self._router._authrole_to_sessions.get(ar, set())

        return receivers

    def processPublish(self, session, publish):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processPublish`
        """
        if self._router.is_traced:
            if not publish.correlation_id:
                publish.correlation_id = self._router.new_correlation_id()
                publish.correlation_is_anchor = True
            if not publish.correlation_uri:
                publish.correlation_uri = publish.topic

        # check topic URI: for PUBLISH, must be valid URI (either strict or loose), and
        # all URI components must be non-empty
        if self._option_uri_strict:
            uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(publish.topic)
        else:
            uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(publish.topic)

        if not uri_is_valid:
            if publish.acknowledge:
                if self._router.is_traced:
                    publish.correlation_is_last = False
                    self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, [u"publish with invalid topic URI '{0}' (URI strict checking {1})".format(publish.topic, self._option_uri_strict)])
                reply.correlation_id = publish.correlation_id
                reply.correlation_uri = publish.topic
                reply.correlation_is_anchor = False
                reply.correlation_is_last = True
                self._router.send(session, reply)

            else:
                if self._router.is_traced:
                    publish.correlation_is_last = True
                    self._router._factory._worker._maybe_trace_rx_msg(session, publish)
            return

        # disallow publication to topics starting with "wamp." other than for
        # trusted sessions (that are sessions built into Crossbar.io routing core)
        #
        if session._authrole is not None and session._authrole != u"trusted":
            is_restricted = publish.topic.startswith(u"wamp.")
            if is_restricted:
                if publish.acknowledge:
                    if self._router.is_traced:
                        publish.correlation_is_last = False
                        self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                    reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_URI, [u"publish with restricted topic URI '{0}'".format(publish.topic)])
                    reply.correlation_id = publish.correlation_id
                    reply.correlation_uri = publish.topic
                    reply.correlation_is_anchor = False
                    reply.correlation_is_last = True
                    self._router.send(session, reply)

                else:
                    if self._router.is_traced:
                        publish.correlation_is_last = True
                        self._router._factory._worker._maybe_trace_rx_msg(session, publish)

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
        if not (subscriptions or publish.acknowledge or store_event or retain_event):

            # the received PUBLISH message is the only one received/sent
            # for this WAMP action, so mark it as "last" (there is another code path below!)
            if self._router.is_traced:
                if publish.correlation_is_last is None:
                    publish.correlation_is_last = True
                self._router._factory._worker._maybe_trace_rx_msg(session, publish)

        else:

            # validate payload
            #
            if publish.payload is None:
                try:
                    self._router.validate('event', publish.topic, publish.args, publish.kwargs)
                except Exception as e:
                    if publish.acknowledge:
                        if self._router.is_traced:
                            publish.correlation_is_last = False
                            self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                        reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.INVALID_ARGUMENT, [u"publish to topic URI '{0}' with invalid application payload: {1}".format(publish.topic, e)])
                        reply.correlation_id = publish.correlation_id
                        reply.correlation_uri = publish.topic
                        reply.correlation_is_anchor = False
                        reply.correlation_is_last = True
                        self._router.send(session, reply)
                    else:
                        if self._router.is_traced:
                            publish.correlation_is_last = True
                            self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                    return

            # authorize PUBLISH action
            #
            d = self._router.authorize(session, publish.topic, u'publish', options=publish.marshal_options())

            def on_authorize_success(authorization):

                # the call to authorize the action _itself_ succeeded. now go on depending on whether
                # the action was actually authorized or not ..
                #
                if not authorization[u'allow']:

                    if publish.acknowledge:
                        if self._router.is_traced:
                            publish.correlation_is_last = False
                            self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                        reply = message.Error(message.Publish.MESSAGE_TYPE, publish.request, ApplicationError.NOT_AUTHORIZED, [u"session not authorized to publish to topic '{0}'".format(publish.topic)])
                        reply.correlation_id = publish.correlation_id
                        reply.correlation_uri = publish.topic
                        reply.correlation_is_anchor = False
                        reply.correlation_is_last = True
                        self._router.send(session, reply)

                    else:
                        if self._router.is_traced:
                            publish.correlation_is_last = True
                            self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                else:

                    # new ID for the publication
                    #
                    publication = util.id()

                    # publisher disclosure
                    #
                    if authorization[u'disclose']:
                        disclose = True
                    elif (publish.topic.startswith(u"wamp.") or publish.topic.startswith(u"crossbar.")):
                        disclose = True
                    else:
                        disclose = False

                    forward_for = None
                    if disclose:
                        if publish.forward_for:
                            publisher = publish.forward_for[0]['session']
                            publisher_authid = publish.forward_for[0]['authid']
                            publisher_authrole = publish.forward_for[0]['authrole']
                            forward_for = publish.forward_for + [
                                {
                                    'session': session._session_id,
                                    'authid': session._authid,
                                    'authrole': session._authrole,
                                }
                            ]
                        else:
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

                    # persist event (this is done only once, regardless of the number of subscriptions
                    # the event matches on)
                    #
                    if store_event:
                        self._event_store.store_event(session, publication, publish)

                    # retain event on the topic
                    #
                    if retain_event:
                        retained_event = RetainedEvent(publish, publisher, publisher_authid, publisher_authrole)

                        observation = self._subscription_map.get_observation(publish.topic)

                        if not observation:
                            # No observation, lets make a new one
                            observation = self._subscription_map.create_observation(publish.topic, extra=SubscriptionExtra())
                        else:
                            # this can happen if event-history is
                            # enabled on the topic: the event-store
                            # creates an observation before any client
                            # could possible hit the code above
                            if observation.extra is None:
                                observation.extra = SubscriptionExtra()
                            elif not isinstance(observation.extra, SubscriptionExtra):
                                raise Exception(
                                    "incorrect 'extra' for '{}'".format(publish.topic)
                                )

                        if observation.extra.retained_events:
                            if not publish.eligible and not publish.exclude:
                                observation.extra.retained_events = [retained_event]
                            else:
                                observation.extra.retained_events.append(retained_event)
                        else:
                            observation.extra.retained_events = [retained_event]

                    subscription_to_receivers = {}
                    total_receivers_cnt = 0

                    # iterate over all subscriptions and determine actual receivers of the event
                    # under the respective subscription. also persist events (independent of whether
                    # there is any actual receiver right now on the subscription)
                    #
                    for subscription in subscriptions:

                        # initial list of receivers are all subscribers on a subscription ..
                        #
                        receivers = subscription.observers
                        receivers = self._filter_publish_receivers(receivers, publish)

                        # if receivers is non-empty, dispatch event ..
                        #
                        receivers_cnt = len(receivers) - (1 if self in receivers else 0)
                        if receivers_cnt:

                            total_receivers_cnt += receivers_cnt
                            subscription_to_receivers[subscription] = receivers

                    # send publish acknowledge before dispatching
                    #
                    if publish.acknowledge:
                        if self._router.is_traced:
                            publish.correlation_is_last = False
                            self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                        reply = message.Published(publish.request, publication)
                        reply.correlation_id = publish.correlation_id
                        reply.correlation_uri = publish.topic
                        reply.correlation_is_anchor = False
                        reply.correlation_is_last = total_receivers_cnt == 0
                        self._router.send(session, reply)
                    else:
                        if self._router.is_traced and publish.correlation_is_last is None:
                            if total_receivers_cnt == 0:
                                publish.correlation_is_last = True
                            else:
                                publish.correlation_is_last = False

                    # now actually dispatch the events!
                    # for chunked dispatching, this will be filled with deferreds for each chunk
                    # processed. when the complete list of deferreds is done, that means the
                    # event has been sent out to all applicable receivers
                    all_dl = []

                    if total_receivers_cnt:

                        # list of receivers that should have received the event, but we could not
                        # send the event, since the receiver has disappeared in the meantime
                        vanished_receivers = []

                        for subscription, receivers in subscription_to_receivers.items():

                            storing_event = store_event and self._event_store in subscription.observers

                            self.log.debug('dispatching for subscription={subscription}, storing_event={storing_event}',
                                           subscription=subscription, storing_event=storing_event)

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
                                                    enc_serializer=publish.enc_serializer,
                                                    forward_for=forward_for)
                            else:
                                msg = message.Event(subscription.id,
                                                    publication,
                                                    args=publish.args,
                                                    kwargs=publish.kwargs,
                                                    publisher=publisher,
                                                    publisher_authid=publisher_authid,
                                                    publisher_authrole=publisher_authrole,
                                                    topic=topic,
                                                    forward_for=forward_for)

                            # if the publish message had a correlation ID, this will also be the
                            # correlation ID of the event message sent out
                            msg.correlation_id = publish.correlation_id
                            msg.correlation_uri = publish.topic
                            msg.correlation_is_anchor = False
                            msg.correlation_is_last = False

                            chunk_size = self._options.event_dispatching_chunk_size

                            if chunk_size and len(receivers) > chunk_size:
                                self.log.debug('chunked dispatching to {receivers_size} with chunk_size={chunk_size}',
                                               receivers_size=len(receivers), chunk_size=chunk_size)
                            else:
                                self.log.debug('unchunked dispatching to {receivers_size} receivers',
                                               receivers_size=len(receivers))

                            # note that we're using one code-path for both chunked and unchunked
                            # dispatches; the *first* chunk is always done "synchronously" (before
                            # the first call-later) so "un-chunked mode" really just means we know
                            # we'll be done right now and NOT do a call_later...

                            # a Deferred that fires when all chunks are done
                            all_d = txaio.create_future()
                            all_dl.append(all_d)

                            # all the event messages are the same except for the last one, which
                            # needs to have the "is_last" flag set if we're doing a trace
                            if self._router.is_traced:
                                last_msg = copy.deepcopy(msg)
                                last_msg.correlation_id = msg.correlation_id
                                last_msg.correlation_uri = msg.correlation_uri
                                last_msg.correlation_is_anchor = False
                                last_msg.correlation_is_last = True

                            def _notify_some(receivers):

                                # we do a first pass over the proposed chunk of receivers
                                # because not all of them will have a transport, and if this
                                # will be the last chunk of receivers we need to figure out
                                # which event is last...
                                receivers_this_chunk = []
                                for receiver in receivers[:chunk_size]:
                                    if receiver._session_id and receiver._transport:
                                        receivers_this_chunk.append(receiver)
                                    else:
                                        vanished_receivers.append(receiver)

                                receivers = receivers[chunk_size:]

                                # XXX note there's still going to be some edge-cases here .. if
                                # we are NOT the last chunk, but all the next chunk's receivers
                                # (could be only 1 in that chunk!) vanish before we run our next
                                # batch, then a "last" event will never go out ...

                                # we now actually do the deliveries, but now we know which
                                # receiver is the last one
                                if receivers or not self._router.is_traced:

                                    # NOT the last chunk (or we're not traced so don't care)
                                    for receiver in receivers_this_chunk:

                                        # send out WAMP msg to peer
                                        self._router.send(receiver, msg)
                                        if self._event_store or storing_event:
                                            self._event_store.store_event_history(publication, subscription.id, receiver)
                                else:
                                    # last chunk, so last receiver gets the different message
                                    for receiver in receivers_this_chunk[:-1]:
                                        self._router.send(receiver, msg)
                                        if self._event_store or storing_event:
                                            self._event_store.store_event_history(publication, subscription.id, receiver)

                                    # FIXME: I don't get the following comment and code path. when, how? and what to
                                    # do about event store? => storing_event
                                    #
                                    # we might have zero valid receivers
                                    if receivers_this_chunk:
                                        self._router.send(receivers_this_chunk[-1], last_msg)
                                        # FIXME: => storing_event

                                if receivers:
                                    # still more to do ..
                                    return txaio.call_later(0, _notify_some, receivers)
                                else:
                                    # all done! resolve all_d, which represents all receivers
                                    # to a single subscription matching the event
                                    txaio.resolve(all_d, None)

                            _notify_some([
                                recv for recv in receivers
                                if (me_also or recv != session) and recv != self._event_store
                            ])

                    return txaio.gather(all_dl)

            def on_authorize_error(err):
                """
                the call to authorize the action _itself_ failed (note this is
                different from the call to authorize succeed, but the
                authorization being denied)
                """
                self.log.failure("Authorization failed", failure=err)
                if publish.acknowledge:

                    if self._router.is_traced:
                        publish.correlation_is_last = False
                        self._router._factory._worker._maybe_trace_rx_msg(session, publish)

                    reply = message.Error(
                        message.Publish.MESSAGE_TYPE,
                        publish.request,
                        ApplicationError.AUTHORIZATION_FAILED,
                        [u"failed to authorize session for publishing to topic URI '{0}': {1}".format(publish.topic, err.value)]
                    )
                    reply.correlation_id = publish.correlation_id
                    reply.correlation_uri = publish.topic
                    reply.correlation_is_anchor = False
                    self._router.send(session, reply)
                else:
                    if self._router.is_traced:
                        publish.correlation_is_last = True
                        self._router._factory._worker._maybe_trace_rx_msg(session, publish)

            txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processSubscribe(self, session, subscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processSubscribe`
        """
        if self._router.is_traced:
            if not subscribe.correlation_id:
                subscribe.correlation_id = self._router.new_correlation_id()
                subscribe.correlation_is_anchor = True
                subscribe.correlation_is_last = False
            if not subscribe.correlation_uri:
                subscribe.correlation_uri = subscribe.topic
            self._router._factory._worker._maybe_trace_rx_msg(session, subscribe)

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
            reply.correlation_id = subscribe.correlation_id
            reply.correlation_uri = subscribe.topic
            reply.correlation_is_anchor = False
            reply.correlation_is_last = True
            self._router.send(session, reply)
            return

        # authorize SUBSCRIBE action
        #
        d = self._router.authorize(session, subscribe.topic, u'subscribe', options=subscribe.marshal_options())

        def on_authorize_success(authorization):
            if not authorization[u'allow']:
                # error reply since session is not authorized to subscribe
                #
                replies = [message.Error(message.Subscribe.MESSAGE_TYPE, subscribe.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to subscribe to topic '{0}'".format(subscribe.topic)])]
                replies[0].correlation_id = subscribe.correlation_id
                replies[0].correlation_uri = subscribe.topic
                replies[0].correlation_is_anchor = False
                replies[0].correlation_is_last = True

            else:
                # ok, session authorized to subscribe. now get the subscription
                #
                subscription, was_already_subscribed, is_first_subscriber = self._subscription_map.add_observer(session, subscribe.topic, subscribe.match, extra=SubscriptionExtra())

                if not was_already_subscribed:
                    self._session_to_subscriptions[session].add(subscription)

                # publish WAMP meta events, if we have a service session, but
                # not for the meta API itself!
                #
                if self._router._realm and \
                   self._router._realm.session and \
                   not subscription.uri.startswith(u'wamp.') and \
                   (is_first_subscriber or not was_already_subscribed):

                    has_follow_up_messages = True

                    def _publish():
                        service_session = self._router._realm.session
                        options = types.PublishOptions(
                            correlation_id=subscribe.correlation_id,
                            correlation_is_anchor=False,
                            correlation_is_last=False,
                        )
                        if is_first_subscriber:
                            subscription_details = {
                                u'id': subscription.id,
                                u'created': subscription.created,
                                u'uri': subscription.uri,
                                u'match': subscription.match,
                            }
                            service_session.publish(
                                u'wamp.subscription.on_create',
                                session._session_id,
                                subscription_details,
                                options=options,
                            )
                        if not was_already_subscribed:
                            options.correlation_is_last = True
                            service_session.publish(
                                u'wamp.subscription.on_subscribe',
                                session._session_id,
                                subscription.id,
                                options=options,
                            )
                    # we postpone actual sending of meta events until we return to this client session
                    self._reactor.callLater(0, _publish)

                else:
                    has_follow_up_messages = False

                # check for retained events
                #
                def _get_retained_event():

                    if subscription.extra.retained_events:
                        retained_events = list(subscription.extra.retained_events)
                        retained_events.reverse()

                        for retained_event in retained_events:
                            authorized = False

                            if not retained_event.publish.exclude and not retained_event.publish.eligible:
                                authorized = True
                            elif session._session_id in retained_event.publish.eligible and session._session_id not in retained_event.publish.exclude:
                                authorized = True

                            if authorized:
                                publication = util.id()

                                if retained_event.publish.payload:
                                    msg = message.Event(subscription.id,
                                                        publication,
                                                        payload=retained_event.publish.payload,
                                                        enc_algo=retained_event.publish.enc_algo,
                                                        enc_key=retained_event.publish.enc_key,
                                                        enc_serializer=retained_event.publish.enc_serializer,
                                                        publisher=retained_event.publisher,
                                                        publisher_authid=retained_event.publisher_authid,
                                                        publisher_authrole=retained_event.publisher_authrole,
                                                        retained=True)
                                else:
                                    msg = message.Event(subscription.id,
                                                        publication,
                                                        args=retained_event.publish.args,
                                                        kwargs=retained_event.publish.kwargs,
                                                        publisher=retained_event.publisher,
                                                        publisher_authid=retained_event.publisher_authid,
                                                        publisher_authrole=retained_event.publisher_authrole,
                                                        retained=True)

                                msg.correlation_id = subscribe.correlation_id
                                msg.correlation_uri = subscribe.topic
                                msg.correlation_is_anchor = False
                                msg.correlation_is_last = False

                                return [msg]
                    return []

                # acknowledge subscribe with subscription ID
                #
                replies = [message.Subscribed(subscribe.request, subscription.id)]
                replies[0].correlation_id = subscribe.correlation_id
                replies[0].correlation_uri = subscribe.topic
                replies[0].correlation_is_anchor = False
                replies[0].correlation_is_last = False
                if subscribe.get_retained:
                    replies.extend(_get_retained_event())

                replies[-1].correlation_is_last = not has_follow_up_messages

            # send out reply to subscribe requestor
            #
            [self._router.send(session, reply) for reply in replies]

        def on_authorize_error(err):
            """
            the call to authorize the action _itself_ failed (note this is
            different from the call to authorize succeed, but the
            authorization being denied)
            """
            self.log.failure("Authorization of 'subscribe' for '{uri}' failed",
                             uri=subscribe.topic, failure=err)
            reply = message.Error(
                message.Subscribe.MESSAGE_TYPE,
                subscribe.request,
                ApplicationError.AUTHORIZATION_FAILED,
                [u"failed to authorize session for subscribing to topic URI '{0}': {1}".format(subscribe.topic, err.value)]
            )
            reply.correlation_id = subscribe.correlation_id
            reply.correlation_uri = subscribe.topic
            reply.correlation_is_anchor = False
            reply.correlation_is_last = True
            self._router.send(session, reply)

        txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processUnsubscribe(self, session, unsubscribe):
        """
        Implements :func:`crossbar.router.interfaces.IBroker.processUnsubscribe`
        """
        if self._router.is_traced:
            if not unsubscribe.correlation_id:
                unsubscribe.correlation_id = self._router.new_correlation_id()
                unsubscribe.correlation_is_anchor = True
                unsubscribe.correlation_is_last = False

        # get subscription by subscription ID or None (if it doesn't exist on this broker)
        #
        subscription = self._subscription_map.get_observation_by_id(unsubscribe.subscription)

        if subscription:

            if self._router.is_traced and not unsubscribe.correlation_uri:
                unsubscribe.correlation_uri = subscription.uri

            if session in subscription.observers:

                was_subscribed, was_last_subscriber, has_follow_up_messages = self._unsubscribe(subscription, session, unsubscribe)

                reply = message.Unsubscribed(unsubscribe.request)

                if self._router.is_traced:
                    reply.correlation_uri = subscription.uri
                    reply.correlation_is_last = not has_follow_up_messages
            else:
                # subscription exists on this broker, but the session that wanted to unsubscribe wasn't subscribed
                #
                reply = message.Error(message.Unsubscribe.MESSAGE_TYPE, unsubscribe.request, ApplicationError.NO_SUCH_SUBSCRIPTION)
                if self._router.is_traced:
                    reply.correlation_uri = reply.error
                    reply.correlation_is_last = True

        else:
            # subscription doesn't even exist on this broker
            #
            reply = message.Error(message.Unsubscribe.MESSAGE_TYPE, unsubscribe.request, ApplicationError.NO_SUCH_SUBSCRIPTION)
            if self._router.is_traced:
                reply.correlation_uri = reply.error
                reply.correlation_is_last = True

        if self._router.is_traced:
            self._router._factory._worker._maybe_trace_rx_msg(session, unsubscribe)

            reply.correlation_id = unsubscribe.correlation_id
            reply.correlation_is_anchor = False

        self._router.send(session, reply)

    def _unsubscribe(self, subscription, session, unsubscribe=None):

        # drop session from subscription observers
        #
        was_subscribed, was_last_subscriber = self._subscription_map.drop_observer(session, subscription)
        was_deleted = False

        if was_subscribed and was_last_subscriber and not subscription.extra.retained_events:
            self._subscription_map.delete_observation(subscription)
            was_deleted = True

        # remove subscription from session->subscriptions map
        #
        if was_subscribed:
            self._session_to_subscriptions[session].discard(subscription)

        # publish WAMP meta events, if we have a service session, but
        # not for the meta API itself!
        #
        if self._router._realm and \
           self._router._realm.session and \
           not subscription.uri.startswith(u'wamp.') and \
           (was_subscribed or was_deleted):

            has_follow_up_messages = True

            def _publish():
                service_session = self._router._realm.session

                if unsubscribe and self._router.is_traced:
                    options = types.PublishOptions(
                        correlation_id=unsubscribe.correlation_id,
                        correlation_is_anchor=False,
                        correlation_is_last=False
                    )
                else:
                    options = None

                if was_subscribed:
                    service_session.publish(
                        u'wamp.subscription.on_unsubscribe',
                        session._session_id,
                        subscription.id,
                        options=options,
                    )

                if was_deleted:
                    if options:
                        options.correlation_is_last = True

                    service_session.publish(
                        u'wamp.subscription.on_delete',
                        session._session_id,
                        subscription.id,
                        options=options,
                    )

            # we postpone actual sending of meta events until we return to this client session
            self._reactor.callLater(0, _publish)

        else:

            has_follow_up_messages = False

        return was_subscribed, was_last_subscriber, has_follow_up_messages

    def removeSubscriber(self, subscription, session, reason=None):
        """
        Actively unsubscribe a subscriber session from a subscription.
        """
        was_subscribed, was_last_subscriber, _ = self._unsubscribe(subscription, session)

        if 'subscriber' in session._session_roles and session._session_roles['subscriber'] and session._session_roles['subscriber'].subscription_revocation:
            reply = message.Unsubscribed(0, subscription=subscription.id, reason=reason)
            reply.correlation_uri = subscription.uri
            self._router.send(session, reply)

        return was_subscribed, was_last_subscriber
