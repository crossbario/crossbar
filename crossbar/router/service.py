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

from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure

from autobahn import wamp, util
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import RegisterOptions
from autobahn.wamp.request import Registration

from crossbar.router.observation import is_protected_uri

from txaio import make_logger

__all__ = ('RouterServiceAgent',)


def is_restricted_session(session):
    return session._authrole is None or session._authrole == u'trusted'


class RouterServiceAgent(ApplicationSession):

    """
    User router-realm service session, and WAMP meta API implementation.

    Router service session which is used internally by a router to
    issue WAMP calls or publish events, and which provides WAMP meta API
    procedures.
    """

    log = make_logger()

    def __init__(self, config, router, schemas=None):
        """
        Ctor.

        :param config: WAMP application component configuration.
        :type config: Instance of :class:`autobahn.wamp.types.ComponentConfig`.
        :param router: The router this service session is running for.
        :type: router: instance of :class:`crossbar.router.session.CrossbarRouter`
        :param schemas: An (optional) initial schema dictionary to load.
        :type schemas: dict
        """
        ApplicationSession.__init__(self, config)
        self._router = router

        self._schemas = {}
        if schemas:
            self._schemas.update(schemas)
            self.log.info(
                'initialized schemas cache with {entries} entries',
                entries=len(self._schemas),
            )

        # the service session can expose its API on multiple sessions
        # by default, it exposes its API only on itself, and that means, on the
        # router-realm the user started
        self._expose_on_sessions = []

        enable_meta_api = self.config.extra.get('enable_meta_api', True) if self.config.extra else True
        if enable_meta_api:
            self._expose_on_sessions.append((self, None, None))

        # optionally, when this option is set, the service session exposes its API
        # additionally on the management session to the local node router (and from there, to CFC)
        bridge_meta_api = self.config.extra.get('bridge_meta_api', False) if self.config.extra else False
        if bridge_meta_api:

            management_session = self.config.extra.get('management_session', None) if self.config.extra else None
            if management_session is None:
                raise Exception('logic error: missing management_session in extra')

            bridge_meta_api_prefix = self.config.extra.get('bridge_meta_api_prefix', None) if self.config.extra else None
            if bridge_meta_api_prefix is None:
                raise Exception('logic error: missing bridge_meta_api_prefix in extra')

            self._expose_on_sessions.append((management_session, bridge_meta_api_prefix, u'-'))

    def publish(self, topic, *args, **kwargs):
        # WAMP meta events published over the service session are published on the
        # service session itself (the first in the list of sessions to expose), and potentially
        # more sessions - namely the management session on the local node router
        dl = []
        for session, prefix, replace_dots in self._expose_on_sessions:

            translated_topic = topic

            # we cannot subscribe in CFC to topics of the form
            # crossbarfabriccenter.node.<node_id>.worker.<worker_id>.realm.<realm_id>.root.*,
            # where * is an arbitrary suffix including dots, eg "wamp.session.on_join"
            #
            # to work around that, we replace the "."s in the suffix with "-", and reverse that
            # in CFC
            if replace_dots:
                translated_topic = translated_topic.replace(u'.', replace_dots)

            if prefix:
                translated_topic = u'{}{}'.format(prefix, translated_topic)

            self.log.debug('RouterServiceAgent.publish("{topic}") -> "{translated_topic}" on "{realm}"',
                           topic=topic, translated_topic=translated_topic, realm=session._realm)

            dl.append(ApplicationSession.publish(session, translated_topic, *args, **kwargs))

        # to keep the interface of ApplicationSession.publish, we only return the first
        # publish return (that is the return from publishing to the user router-realm)
        if len(dl) > 0:
            return dl[0]

    @inlineCallbacks
    def onJoin(self, details):
        self.log.debug(
            'Router service session attached: {details}',
            details=details,
        )

        # register our API on all configured sessions and then fire onready
        #
        on_ready = self.config.extra.get('onready', None) if self.config.extra else None
        try:
            for session, prefix, _ in self._expose_on_sessions:
                regs = yield session.register(self, options=RegisterOptions(details_arg='details'), prefix=prefix)
                for reg in regs:
                    if isinstance(reg, Registration):
                        self.log.debug('Registered WAMP meta procedure <{proc}> on realm "{realm}"', proc=reg.procedure, realm=session._realm)
                    elif isinstance(reg, Failure):
                        err = reg.value
                        if isinstance(err, ApplicationError):
                            self.log.warn('Failed to register WAMP meta procedure on realm "{realm}": {error} ("{message}")', realm=session._realm, error=err.error, message=err.error_message())
                        else:
                            self.log.warn('Failed to register WAMP meta procedure on realm "{realm}": {error}', realm=session._realm, error=str(err))
                    else:
                        self.log.warn('Failed to register WAMP meta procedure on realm "{realm}": {error}', realm=session._realm, error=str(reg))
        except Exception as e:
            self.log.failure()
            if on_ready:
                on_ready.errback(e)
            self.leave()
        else:
            self.log.info('RouterServiceAgent ready (realm_name="{realm}", on_ready={on_ready})', realm=self._realm, on_ready=on_ready)
            if on_ready:
                on_ready.callback(self)

    def onUserError(self, failure, msg):
        # ApplicationError's are raised explicitly and by purpose to signal
        # the peer. The error has already been handled "correctly" from our side.
        # Anything else wasn't explicitly treated .. the error "escaped" explicit
        # processing on our side. It needs to be logged to CB log, and CB code
        # needs to be expanded!
        if not isinstance(failure.value, ApplicationError):
            super(RouterServiceAgent, self).onUserError(failure, msg)

    @wamp.register(u'wamp.session.list')
    def session_list(self, filter_authroles=None, details=None):
        """
        Get list of session IDs of sessions currently joined on the router.

        :param filter_authroles: If provided, only return sessions with an authrole from this list.
        :type filter_authroles: None or list

        :returns: List of WAMP session IDs (order undefined).
        :rtype: list
        """
        assert(filter_authroles is None or isinstance(filter_authroles, list))

        session_ids = []
        for session in self._router._session_id_to_session.values():
            if not is_restricted_session(session):
                if filter_authroles is None or session._session_details[u'authrole'] in filter_authroles:
                    session_ids.append(session._session_id)
        return session_ids

    @wamp.register(u'wamp.session.count')
    def session_count(self, filter_authroles=None, details=None):
        """
        Count sessions currently joined on the router.

        :param filter_authroles: If provided, only count sessions with an authrole from this list.
        :type filter_authroles: None or list

        :returns: Count of joined sessions.
        :rtype: int
        """
        assert(filter_authroles is None or isinstance(filter_authroles, list))

        session_count = 0
        for session in self._router._session_id_to_session.values():
            if not is_restricted_session(session):
                if filter_authroles is None or session._session_details[u'authrole'] in filter_authroles:
                    session_count += 1
        return session_count

    @wamp.register(u'wamp.session.get')
    def session_get(self, session_id, details=None):
        """
        Get details for given session.

        :param session_id: The WAMP session ID to retrieve details for.
        :type session_id: int

        :returns: WAMP session details.
        :rtype: dict or None
        """
        self.log.debug('wamp.session.get("{session_id}")', session_id=session_id)
        if session_id in self._router._session_id_to_session:
            session = self._router._session_id_to_session[session_id]
            if not is_restricted_session(session):
                session_info = session._session_details.marshal()
                session_info[u'transport'] = None if session._transport is None else session._transport._transport_info
                return session_info
        raise ApplicationError(
            ApplicationError.NO_SUCH_SESSION,
            u'no session with ID {} exists on this router'.format(session_id),
        )

    @wamp.register(u'wamp.session.add_testament')
    def session_add_testament(self, topic, args, kwargs, publish_options=None, scope=u"destroyed", details=None):
        """
        Add a testament to the current session.

        :param topic: The topic to publish the testament to.
        :type topic: str

        :param args: A list of arguments for the publish.
        :type args: list or tuple

        :param kwargs: A dict of keyword arguments for the publish.
        :type kwargs: dict

        :param publish_options: The publish options for the publish.
        :type publish_options: None or dict

        :param scope: The scope of the testament, either "detached" or
            "destroyed".
        :type scope: str

        :returns: The publication ID.
        :rtype: int
        """
        session = self._router._session_id_to_session[details.caller]

        if scope not in [u"destroyed", u"detached"]:
            raise ApplicationError(u"wamp.error.testament_error", u"scope must be destroyed or detached")

        pub_id = util.id()

        # Get the publish options, remove some explicit keys
        publish_options = publish_options or {}
        publish_options.pop("acknowledge", None)
        publish_options.pop("exclude_me", None)

        pub = message.Publish(
            request=pub_id,
            topic=topic,
            args=args,
            kwargs=kwargs,
            **publish_options)

        session._testaments[scope].append(pub)

        return pub_id

    @wamp.register(u'wamp.session.flush_testaments')
    def session_flush_testaments(self, scope=u"destroyed", details=None):
        """
        Flush the testaments of a given scope.

        :param scope: The scope to flush, either "detached" or "destroyed".
        :type scope: str

        :returns: Number of flushed testament events.
        :rtype: int
        """
        session = self._router._session_id_to_session[details.caller]

        if scope not in [u"destroyed", u"detached"]:
            raise ApplicationError(u"wamp.error.testament_error", u"scope must be destroyed or detached")

        flushed = len(session._testaments[scope])

        session._testaments[scope] = []

        return flushed

    @wamp.register(u'wamp.session.kill')
    def session_kill(self, session_id, reason=None, message=None, details=None):
        """
        Forcefully kill a session.

        :param session_id: The WAMP session ID of the session to kill.
        :type session_id: int
        :param reason: A reason URI provided to the killed session.
        :type reason: str or None
        """
        if session_id in self._router._session_id_to_session:
            session = self._router._session_id_to_session[session_id]
            if not is_restricted_session(session):
                session.leave(reason=reason, message=message)
                return
        raise ApplicationError(
            ApplicationError.NO_SUCH_SESSION,
            u'no session with ID {} exists on this router'.format(session_id),
        )

    @wamp.register(u'wamp.registration.remove_callee')
    def registration_remove_callee(self, registration_id, callee_id, reason=None, details=None):
        """
        Forcefully remove callee from registration.

        :param registration_id: The ID of the registration to remove the callee from.
        :type registration_id: int
        :param callee_id: The WAMP session ID of the callee to remove.
        :type callee_id: int
        """
        callee = self._router._session_id_to_session.get(callee_id, None)

        if not callee:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SESSION,
                u'no session with ID {} exists on this router'.format(callee_id),
            )

        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)
        if registration:
            if is_protected_uri(registration.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to remove callee for protected URI "{}"'.format(registration.uri),
                )

            if callee not in registration.observers:
                raise ApplicationError(
                    ApplicationError.NO_SUCH_REGISTRATION,
                    u'session {} is not registered on registration {} on this dealer'.format(callee_id, registration_id),
                )

            self._router._dealer.removeCallee(registration, callee, reason=reason)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_REGISTRATION,
                u'no registration with ID {} exists on this dealer'.format(registration_id),
            )

    @wamp.register(u'wamp.subscription.remove_subscriber')
    def subscription_remove_subscriber(self, subscription_id, subscriber_id, reason=None, details=None):
        """
        Forcefully remove subscriber from subscription.

        :param subscription_id: The ID of the subscription to remove the subscriber from.
        :type subscription_id: int
        :param subscriber_id: The WAMP session ID of the subscriber to remove.
        :type subscriber_id: int
        """
        subscriber = self._router._session_id_to_session.get(subscriber_id, None)

        if not subscriber:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SESSION,
                message=u'no session with ID {} exists on this router'.format(subscriber_id),
            )

        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)
        if subscription:
            if is_protected_uri(subscription.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to remove subscriber for protected URI "{}"'.format(subscription.uri),
                )

            if subscriber not in subscription.observers:
                raise ApplicationError(
                    ApplicationError.NO_SUCH_SUBSCRIPTION,
                    u'session {} is not subscribed on subscription {} on this broker'.format(subscriber_id, subscription_id),
                )

            self._router._broker.removeSubscriber(subscription, subscriber, reason=reason)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    @wamp.register(u'wamp.registration.get')
    def registration_get(self, registration_id, details=None):
        """
        Get registration details.

        :param registration_id: The ID of the registration to retrieve.
        :type registration_id: int

        :returns: The registration details.
        :rtype: dict
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)

        if registration:
            if is_protected_uri(registration.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to get registration for protected URI "{}"'.format(registration.uri),
                )

            registration_details = {
                u'id': registration.id,
                u'created': registration.created,
                u'uri': registration.uri,
                u'match': registration.match,
                u'invoke': registration.extra.invoke,
            }
            return registration_details
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_REGISTRATION,
                u'no registration with ID {} exists on this dealer'.format(registration_id),
            )

    @wamp.register(u'wamp.subscription.get')
    def subscription_get(self, subscription_id, details=None):
        """
        Get subscription details.

        :param subscription_id: The ID of the subscription to retrieve.
        :type subscription_id: int

        :returns: The subscription details.
        :rtype: dict
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)

        if subscription:
            if is_protected_uri(subscription.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to get subscription for protected URI "{}"'.format(subscription.uri),
                )

            subscription_details = {
                u'id': subscription.id,
                u'created': subscription.created,
                u'uri': subscription.uri,
                u'match': subscription.match,
            }
            return subscription_details
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    @wamp.register(u'wamp.registration.list')
    def registration_list(self, session_id=None, details=None):
        """
        List current registrations.

        :returns: A dictionary with three entries for the match policies 'exact', 'prefix'
            and 'wildcard', with a list of registration IDs for each.
        :rtype: dict
        """
        if session_id:

            s2r = self._router._dealer._session_to_registrations
            session = None

            if session_id in self._router._session_id_to_session:
                session = self._router._session_id_to_session[session_id]
                if is_restricted_session(session):
                    session = None

            if not session or session not in s2r:
                raise ApplicationError(
                    ApplicationError.NO_SUCH_SESSION,
                    u'no session with ID {} exists on this router'.format(session_id),
                )

            _regs = s2r[session]

            regs = {
                u'exact': [reg.id for reg in _regs if reg.match == u'exact'],
                u'prefix': [reg.id for reg in _regs if reg.match == u'prefix'],
                u'wildcard': [reg.id for reg in _regs if reg.match == u'wildcard'],
            }
            return regs

        else:

            registration_map = self._router._dealer._registration_map

            registrations_exact = []
            for registration in registration_map._observations_exact.values():
                if not is_protected_uri(registration.uri, details):
                    registrations_exact.append(registration.id)

            registrations_prefix = []
            for registration in registration_map._observations_prefix.values():
                if not is_protected_uri(registration.uri, details):
                    registrations_prefix.append(registration.id)

            registrations_wildcard = []
            for registration in registration_map._observations_wildcard.values():
                if not is_protected_uri(registration.uri, details):
                    registrations_wildcard.append(registration.id)

            regs = {
                u'exact': registrations_exact,
                u'prefix': registrations_prefix,
                u'wildcard': registrations_wildcard,
            }

            return regs

    @wamp.register(u'wamp.subscription.list')
    def subscription_list(self, session_id=None, details=None):
        """
        List current subscriptions.

        :returns: A dictionary with three entries for the match policies 'exact', 'prefix'
            and 'wildcard', with a list of subscription IDs for each.
        :rtype: dict
        """
        if session_id:

            s2s = self._router._broker._session_to_subscriptions
            session = None

            if session_id in self._router._session_id_to_session:
                session = self._router._session_id_to_session[session_id]
                if is_restricted_session(session):
                    session = None

            if not session or session not in s2s:
                raise ApplicationError(
                    ApplicationError.NO_SUCH_SESSION,
                    u'no session with ID {} exists on this router'.format(session_id),
                )

            _subs = s2s[session]

            subs = {
                u'exact': [sub.id for sub in _subs if sub.match == u'exact'],
                u'prefix': [sub.id for sub in _subs if sub.match == u'prefix'],
                u'wildcard': [sub.id for sub in _subs if sub.match == u'wildcard'],
            }
            return subs

        else:

            subscription_map = self._router._broker._subscription_map

            subscriptions_exact = []
            for subscription in subscription_map._observations_exact.values():
                if not is_protected_uri(subscription.uri, details):
                    subscriptions_exact.append(subscription.id)

            subscriptions_prefix = []
            for subscription in subscription_map._observations_prefix.values():
                if not is_protected_uri(subscription.uri, details):
                    subscriptions_prefix.append(subscription.id)

            subscriptions_wildcard = []
            # FIXME
            # for subscription in subscription_map._observations_wildcard.values():
            #     if not is_protected_uri(subscription.uri, details):
            #         subscriptions_wildcard.append(subscription.id)

            subs = {
                u'exact': subscriptions_exact,
                u'prefix': subscriptions_prefix,
                u'wildcard': subscriptions_wildcard,
            }

            return subs

    @wamp.register(u'wamp.registration.match')
    def registration_match(self, procedure, details=None):
        """
        Given a procedure URI, return the registration best matching the procedure.

        This essentially models what a dealer does for dispatching an incoming call.

        :param procedure: The procedure to match.
        :type procedure: str

        :returns: The best matching registration or ``None``.
        :rtype: obj or None
        """
        registration = self._router._dealer._registration_map.best_matching_observation(procedure)

        if registration and not is_protected_uri(registration.uri, details):
            return registration.id
        else:
            return None

    @wamp.register(u'wamp.subscription.match')
    def subscription_match(self, topic, details=None):
        """
        Given a topic URI, returns all subscriptions matching the topic.

        This essentially models what a broker does for dispatching an incoming publication.

        :param topic: The topic to match.
        :type topic: str

        :returns: All matching subscriptions or ``None``.
        :rtype: obj or None
        """
        subscriptions = self._router._broker._subscription_map.match_observations(topic)

        if subscriptions:
            subscription_ids = []
            for subscription in subscriptions:
                if not is_protected_uri(subscription.uri, details):
                    subscription_ids.append(subscription.id)
            if subscription_ids:
                return subscription_ids
            else:
                return None
        else:
            return None

    @wamp.register(u'wamp.registration.lookup')
    def registration_lookup(self, procedure, options=None, details=None):
        """
        Given a procedure URI (and options), return the registration (if any) managing the procedure.

        This essentially models what a dealer does when registering for a procedure.

        :param procedure: The procedure to lookup the registration for.
        :type procedure: str
        :param options: Same options as when registering a procedure.
        :type options: dict or None

        :returns: The ID of the registration managing the procedure or ``None``.
        :rtype: int or None
        """
        options = options or {}
        match = options.get(u'match', u'exact')

        registration = self._router._dealer._registration_map.get_observation(procedure, match)

        if registration and not is_protected_uri(registration.uri, details):
            return registration.id
        else:
            return None

    @wamp.register(u'wamp.subscription.lookup')
    def subscription_lookup(self, topic, options=None, details=None):
        """
        Given a topic URI (and options), return the subscription (if any) managing the topic.

        This essentially models what a broker does when subscribing for a topic.

        :param topic: The topic to lookup the subscription for.
        :type topic: str
        :param options: Same options as when subscribing to a topic.
        :type options: dict or None

        :returns: The ID of the subscription managing the topic or ``None``.
        :rtype: int or None
        """
        options = options or {}
        match = options.get(u'match', u'exact')

        subscription = self._router._broker._subscription_map.get_observation(topic, match)

        if subscription and not is_protected_uri(subscription.uri, details):
            return subscription.id
        else:
            return None

    @wamp.register(u'wamp.registration.list_callees')
    def registration_list_callees(self, registration_id, details=None):
        """
        Retrieve list of callees (WAMP session IDs) registered on (attached to) a registration.

        :param registration_id: The ID of the registration to get callees for.
        :type registration_id: int

        :returns: A list of WAMP session IDs of callees currently attached to the registration.
        :rtype: list
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)

        if registration:
            if is_protected_uri(registration.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to list callees for protected URI "{}"'.format(registration.uri),
                )

            session_ids = []
            for callee in registration.observers:
                session_ids.append(callee._session_id)
            return session_ids
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_REGISTRATION,
                u'no registration with ID {} exists on this dealer'.format(registration_id),
            )

    @wamp.register(u'wamp.subscription.list_subscribers')
    def subscription_list_subscribers(self, subscription_id, details=None):
        """
        Retrieve list of subscribers (WAMP session IDs) subscribed on (attached to) a subscription.

        :param subscription_id: The ID of the subscription to get subscribers for.
        :type subscription_id: int

        :returns: A list of WAMP session IDs of subscribers currently attached to the subscription.
        :rtype: list
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)

        if subscription:
            if is_protected_uri(subscription.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to list subscribers for protected URI "{}"'.format(subscription.uri),
                )

            session_ids = []
            for subscriber in subscription.observers:
                session_ids.append(subscriber._session_id)
            return session_ids
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    @wamp.register(u'wamp.registration.count_callees')
    def registration_count_callees(self, registration_id, details=None):
        """
        Retrieve number of callees registered on (attached to) a registration.

        :param registration_id: The ID of the registration to get the number of callees for.
        :type registration_id: int

        :returns: Number of callees currently attached to the registration.
        :rtype: int
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)

        if registration:
            if is_protected_uri(registration.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to count callees for protected URI "{}"'.format(registration.uri),
                )
            return len(registration.observers)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_REGISTRATION,
                u'no registration with ID {} exists on this dealer'.format(registration_id),
            )

    @wamp.register(u'wamp.subscription.count_subscribers')
    def subscription_count_subscribers(self, subscription_id, details=None):
        """
        Retrieve number of subscribers subscribed on (attached to) a subscription.

        :param subscription_id: The ID of the subscription to get the number subscribers for.
        :type subscription_id: int

        :returns: Number of subscribers currently attached to the subscription.
        :rtype: int
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)

        if subscription:
            if is_protected_uri(subscription.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to count subscribers for protected URI "{}"'.format(subscription.uri),
                )

            return len(subscription.observers)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    @wamp.register(u'wamp.subscription.get_events')
    def subscription_get_events(self, subscription_id, limit=10, details=None):
        """
        Return history of events for given subscription.

        :param subscription_id: The ID of the subscription to get events for.
        :type subscription_id: int
        :param limit: Return at most this many events.
        :type limit: int

        :returns: List of events.
        :rtype: list
        """
        self.log.debug('subscription_get_events({subscription_id}, {limit})', subscription_id=subscription_id, limit=limit)

        if not self._router._broker._event_store:
            raise ApplicationError(
                u'wamp.error.history_unavailable',
                message=u'event history not available or enabled',
            )

        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)

        if subscription:
            if is_protected_uri(subscription.uri, details):
                raise ApplicationError(
                    ApplicationError.NOT_AUTHORIZED,
                    message=u'not authorized to retrieve event history for protected URI "{}"'.format(subscription.uri),
                )

            events = self._router._broker._event_store.get_events(subscription_id, limit)
            if events is None:
                # a return value of None in above signals that event history really
                # is not available/enabled (which is different from an empty history!)
                raise ApplicationError(
                    u'wamp.error.history_unavailable',
                    message=u'event history for the given subscription is not available or enabled',
                )
            else:
                return events
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    def schema_describe(self, uri=None, details=None):
        """
        Describe a given URI or all URIs.

        :param uri: The URI to describe or ``None`` to retrieve all declarations.
        :type uri: str

        :returns: A list of WAMP schema declarations.
        :rtype: list
        """
        raise Exception('not implemented')

    def schema_define(self, uri, schema, details=None):
        """
        Declare metadata for a given URI.

        :param uri: The URI for which to declare metadata.
        :type uri: str
        :param schema: The WAMP schema declaration for
           the URI or `None` to remove any declarations for the URI.
        :type schema: dict

        :returns: ``None`` if declaration was unchanged, ``True`` if
           declaration was new, ``False`` if declaration existed, but was modified.
        :rtype: bool or None
        """
        raise Exception('not implemented')
