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

import json

from twisted.internet.defer import inlineCallbacks

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

from crossbar.router.observation import is_protected_uri

from txaio import make_logger

__all__ = ('RouterServiceSession',)


def _is_restricted_session(session):
    return session._authrole is None or session._authrole == u'trusted'


# # extract schema information from WAMP-flavored Markdown
# #
# schemas = None
# if 'schemas' in realm:
#     schemas = {}
#     schema_pat = re.compile(r"```javascript(.*?)```", re.DOTALL)
#     cnt_files = 0
#     cnt_decls = 0
#     for schema_file in realm.pop('schemas'):
#         schema_file = os.path.join(self._cbdir, schema_file)
#         self.log.info("{worker}: processing WAMP-flavored Markdown file {schema_file} for WAMP schema declarations",
#                       worker=worker_logname, schema_file=schema_file)
#         with open(schema_file, 'r') as f:
#             cnt_files += 1
#             for d in schema_pat.findall(f.read()):
#                 try:
#                     o = json.loads(d)
#                     if isinstance(o, dict) and '$schema' in o and o['$schema'] == u'http://wamp.ws/schema#':
#                         uri = o['uri']
#                         if uri not in schemas:
#                             schemas[uri] = {}
#                         schemas[uri].update(o)
#                         cnt_decls += 1
#                 except Exception:
#                     self.log.failure("{worker}: WARNING - failed to process declaration in {schema_file} - {log_failure.value}",
#                                      worker=worker_logname, schema_file=schema_file)
#     self.log.info("{worker}: processed {cnt_files} files extracting {cnt_decls} schema declarations and {len_schemas} URIs",
#                   worker=worker_logname, cnt_files=cnt_files, cnt_decls=cnt_decls, len_schemas=len(schemas))


class RouterServiceSession(ApplicationSession):

    """
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
            self.log.info('initialized schemas cache with {} entries'.format(len(self._schemas)))

    @inlineCallbacks
    def onJoin(self, details):
        self.log.debug('Router service session attached: {}'.format(details))

        regs = yield self.register(self)
        self.log.debug('Registered {} procedures'.format(len(regs)))

        if self.config.extra and 'onready' in self.config.extra:
            self.config.extra['onready'].callback(self)

    def onUserError(self, failure, msg):
        # ApplicationError's are raised explicitly and by purpose to signal
        # the peer. The error has already been handled "correctly" from our side.
        # Anything else wasn't explicitly treated .. the error "escaped" explicit
        # processing on our side. It needs to be logged to CB log, and CB code
        # needs to be expanded!
        if not isinstance(failure.value, ApplicationError):
            super(RouterServiceSession, self).onUserError(failure, msg)

    @wamp.register(u'wamp.session.list')
    def session_list(self, filter_authroles=None):
        """
        Get list of session IDs of sessions currently joined on the router.

        :param filter_authroles: If provided, only return sessions with an authrole from this list.
        :type filter_authroles: None or list

        :returns: List of WAMP session IDs (order undefined).
        :rtype: list
        """
        assert(filter_authroles is None or type(filter_authroles) == list)
        session_ids = []
        for session in self._router._session_id_to_session.values():
            if not _is_restricted_session(session):
                if filter_authroles is None or session._session_details[u'authrole'] in filter_authroles:
                    session_ids.append(session._session_id)
        return session_ids

    @wamp.register(u'wamp.session.count')
    def session_count(self, filter_authroles=None):
        """
        Count sessions currently joined on the router.

        :param filter_authroles: If provided, only count sessions with an authrole from this list.
        :type filter_authroles: None or list

        :returns: Count of joined sessions.
        :rtype: int
        """
        assert(filter_authroles is None or type(filter_authroles) == list)
        session_count = 0
        for session in self._router._session_id_to_session.values():
            if not _is_restricted_session(session):
                if filter_authroles is None or session._session_details[u'authrole'] in filter_authroles:
                    session_count += 1
        return session_count

    @wamp.register(u'wamp.session.get')
    def session_get(self, session_id):
        """
        Get details for given session.

        :param session_id: The WAMP session ID to retrieve details for.
        :type session_id: int

        :returns: WAMP session details.
        :rtype: dict or None
        """
        if session_id in self._router._session_id_to_session:
            session = self._router._session_id_to_session[session_id]
            if not _is_restricted_session(session):
                return session._session_details
        raise ApplicationError(
            ApplicationError.NO_SUCH_SESSION,
            u'no session with ID {} exists on this router'.format(session_id),
        )

    @wamp.register(u'wamp.session.kill')
    def session_kill(self, session_id, reason=None, message=None):
        """
        Forcefully kill a session.

        :param session_id: The WAMP session ID of the session to kill.
        :type session_id: int
        :param reason: A reason URI provided to the killed session.
        :type reason: unicode or None
        """
        if session_id in self._router._session_id_to_session:
            session = self._router._session_id_to_session[session_id]
            if not _is_restricted_session(session):
                session.leave(reason=reason, message=message)
                return
        raise ApplicationError(
            ApplicationError.NO_SUCH_SESSION,
            u'no session with ID {} exists on this router'.format(session_id),
        )

    @wamp.register(u'wamp.registration.remove_callee')
    def registration_remove_callee(self, registration_id, callee_id, reason=None):
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
        if registration and not is_protected_uri(registration.uri):

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
    def subscription_remove_subscriber(self, subscription_id, subscriber_id, reason=None):
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
        if subscription and not is_protected_uri(subscription.uri):

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
    def registration_get(self, registration_id):
        """
        Get registration details.

        :param registration_id: The ID of the registration to retrieve.
        :type registration_id: int

        :returns: The registration details.
        :rtype: dict
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)
        if registration and not is_protected_uri(registration.uri):
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
    def subscription_get(self, subscription_id):
        """
        Get subscription details.

        :param subscription_id: The ID of the subscription to retrieve.
        :type subscription_id: int

        :returns: The subscription details.
        :rtype: dict
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)
        if subscription and not is_protected_uri(subscription.uri):
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
    def registration_list(self):
        """
        List current registrations.

        :returns: A dictionary with three entries for the match policies 'exact', 'prefix'
            and 'wildcard', with a list of registration IDs for each.
        :rtype: dict
        """
        registration_map = self._router._dealer._registration_map

        registrations_exact = []
        for registration in registration_map._observations_exact.values():
            if not is_protected_uri(registration.uri):
                registrations_exact.append(registration.id)

        registrations_prefix = []
        for registration in registration_map._observations_prefix.values():
            if not is_protected_uri(registration.uri):
                registrations_prefix.append(registration.id)

        registrations_wildcard = []
        for registration in registration_map._observations_wildcard.values():
            if not is_protected_uri(registration.uri):
                registrations_wildcard.append(registration.id)

        return {
            u'exact': registrations_exact,
            u'prefix': registrations_prefix,
            u'wildcard': registrations_wildcard,
        }

    @wamp.register(u'wamp.subscription.list')
    def subscription_list(self):
        """
        List current subscriptions.

        :returns: A dictionary with three entries for the match policies 'exact', 'prefix'
            and 'wildcard', with a list of subscription IDs for each.
        :rtype: dict
        """
        subscription_map = self._router._broker._subscription_map

        subscriptions_exact = []
        for subscription in subscription_map._observations_exact.values():
            if not is_protected_uri(subscription.uri):
                subscriptions_exact.append(subscription.id)

        subscriptions_prefix = []
        for subscription in subscription_map._observations_prefix.values():
            if not is_protected_uri(subscription.uri):
                subscriptions_prefix.append(subscription.id)

        subscriptions_wildcard = []
        # FIXME
        # for subscription in subscription_map._observations_wildcard.values():
        #     if not is_protected_uri(subscription.uri):
        #         subscriptions_wildcard.append(subscription.id)

        return {
            u'exact': subscriptions_exact,
            u'prefix': subscriptions_prefix,
            u'wildcard': subscriptions_wildcard,
        }

    @wamp.register(u'wamp.registration.match')
    def registration_match(self, procedure):
        """
        Given a procedure URI, return the registration best matching the procedure.

        This essentially models what a dealer does for dispatching an incoming call.

        :param procedure: The procedure to match.
        :type procedure: unicode

        :returns: The best matching registration or ``None``.
        :rtype: obj or None
        """
        registration = self._router._dealer._registration_map.best_matching_observation(procedure)
        if registration and not is_protected_uri(registration.uri):
            return registration.id
        else:
            return None

    @wamp.register(u'wamp.subscription.match')
    def subscription_match(self, topic):
        """
        Given a topic URI, returns all subscriptions matching the topic.

        This essentially models what a broker does for dispatching an incoming publication.

        :param topic: The topic to match.
        :type topic: unicode

        :returns: All matching subscriptions or ``None``.
        :rtype: obj or None
        """
        subscriptions = self._router._broker._subscription_map.match_observations(topic)
        if subscriptions:
            subscription_ids = []
            for subscription in subscriptions:
                if not is_protected_uri(subscription.uri):
                    subscription_ids.append(subscription.id)
            if subscription_ids:
                return subscription_ids
            else:
                return None
        else:
            return None

    @wamp.register(u'wamp.registration.lookup')
    def registration_lookup(self, procedure, options=None):
        """
        Given a procedure URI (and options), return the registration (if any) managing the procedure.

        This essentially models what a dealer does when registering for a procedure.

        :param procedure: The procedure to lookup the registration for.
        :type procedure: unicode
        :param options: Same options as when registering a procedure.
        :type options: dict or None

        :returns: The ID of the registration managing the procedure or ``None``.
        :rtype: int or None
        """
        options = options or {}
        match = options.get(u'match', u'exact')
        registration = self._router._dealer._registration_map.get_observation(procedure, match)
        if registration and not is_protected_uri(registration.uri):
            return registration.id
        else:
            return None

    @wamp.register(u'wamp.subscription.lookup')
    def subscription_lookup(self, topic, options=None):
        """
        Given a topic URI (and options), return the subscription (if any) managing the topic.

        This essentially models what a broker does when subscribing for a topic.

        :param topic: The topic to lookup the subscription for.
        :type topic: unicode
        :param options: Same options as when subscribing to a topic.
        :type options: dict or None

        :returns: The ID of the subscription managing the topic or ``None``.
        :rtype: int or None
        """
        options = options or {}
        match = options.get(u'match', u'exact')
        subscription = self._router._broker._subscription_map.get_observation(topic, match)
        if subscription and not is_protected_uri(subscription.uri):
            return subscription.id
        else:
            return None

    @wamp.register(u'wamp.registration.list_callees')
    def registration_list_callees(self, registration_id):
        """
        Retrieve list of callees (WAMP session IDs) registered on (attached to) a registration.

        :param registration_id: The ID of the registration to get callees for.
        :type registration_id: int

        :returns: A list of WAMP session IDs of callees currently attached to the registration.
        :rtype: list
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)
        if registration and not is_protected_uri(registration.uri):
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
    def subscription_list_subscribers(self, subscription_id):
        """
        Retrieve list of subscribers (WAMP session IDs) subscribed on (attached to) a subscription.

        :param subscription_id: The ID of the subscription to get subscribers for.
        :type subscription_id: int

        :returns: A list of WAMP session IDs of subscribers currently attached to the subscription.
        :rtype: list
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)
        if subscription and not is_protected_uri(subscription.uri):
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
    def registration_count_callees(self, registration_id):
        """
        Retrieve number of callees registered on (attached to) a registration.

        :param registration_id: The ID of the registration to get the number of callees for.
        :type registration_id: int

        :returns: Number of callees currently attached to the registration.
        :rtype: int
        """
        registration = self._router._dealer._registration_map.get_observation_by_id(registration_id)
        if registration and not is_protected_uri(registration.uri):
            return len(registration.observers)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_REGISTRATION,
                u'no registration with ID {} exists on this dealer'.format(registration_id),
            )

    @wamp.register(u'wamp.subscription.count_subscribers')
    def subscription_count_subscribers(self, subscription_id):
        """
        Retrieve number of subscribers subscribed on (attached to) a subscription.

        :param subscription_id: The ID of the subscription to get the number subscribers for.
        :type subscription_id: int

        :returns: Number of subscribers currently attached to the subscription.
        :rtype: int
        """
        subscription = self._router._broker._subscription_map.get_observation_by_id(subscription_id)
        if subscription and not is_protected_uri(subscription.uri):
            return len(subscription.observers)
        else:
            raise ApplicationError(
                ApplicationError.NO_SUCH_SUBSCRIPTION,
                u'no subscription with ID {} exists on this broker'.format(subscription_id),
            )

    @wamp.register(u'wamp.subscription.get_events')
    def subscription_get_events(self, subscription_id, limit=10):
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

        if subscription and not is_protected_uri(subscription.uri):
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

    @wamp.register(u'wamp.test.exception')
    def test_exception(self):
        raise ApplicationError(u'wamp.error.history_unavailable')

    @wamp.register(u'wamp.schema.describe')
    def schema_describe(self, uri=None):
        """
        Describe a given URI or all URIs.

        :param uri: The URI to describe or ``None`` to retrieve all declarations.
        :type uri: unicode

        :returns: A list of WAMP schema declarations.
        :rtype: list
        """
        if uri:
            return self._schemas.get(uri, None)
        else:
            return self._schemas

    @wamp.register(u'wamp.schema.define')
    def schema_define(self, uri, schema):
        """
        Declare metadata for a given URI.

        :param uri: The URI for which to declare metadata.
        :type uri: unicode
        :param schema: The WAMP schema declaration for
           the URI or `None` to remove any declarations for the URI.
        :type schema: dict

        :returns: ``None`` if declaration was unchanged, ``True`` if
           declaration was new, ``False`` if declaration existed, but was modified.
        :rtype: bool or None
        """
        if not schema:
            if uri in self._schemas:
                del self._schemas
                self.publish(u'wamp.schema.on_undefine', uri)
                return uri
            else:
                return None

        if uri not in self._schemas:
            was_new = True
            was_modified = False
        else:
            was_new = False
            if json.dumps(schema) != json.dumps(self._schemas[uri]):
                was_modified = True
            else:
                was_modified = False

        if was_new or was_modified:
            self._schemas[uri] = schema
            self.publish(u'wamp.schema.on_define', uri, schema, was_new)
            return was_new
        else:
            return None
