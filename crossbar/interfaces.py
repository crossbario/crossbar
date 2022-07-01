#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
Interfaces used internally inside Crossbar.io to abstract/decouple different software components.

.. note::

    These interfaces are solely for internal use and not exposed or supposed to be used
    by users or from outside.
"""

import abc
from typing import Union, Dict, List, Any, Optional, Tuple

from autobahn.wamp.interfaces import ISession
from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge, CloseDetails, SessionDetails
from autobahn.wamp.message import Publish
from autobahn.xbr._schema import FbsRepository

from crossbar.router.observation import UriObservationMap

__all__ = (
    'IPendingAuth',
    'IRealmContainer',
    'IRealmStore',
    'IInventory',
)


class IPendingAuth(abc.ABC):
    """
    Interface to pending WAMP authentications.
    """
    @abc.abstractmethod
    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:
        """
        When a HELLO message is received, this gets called to open the pending authentication.

        :param realm: The realm to client wishes to join (if the client did announce a realm).
        :param details: The details of the client provided for HELLO.
        :returns: Either return a challenge, or immediately accept or deny session.
        """

    @abc.abstractmethod
    def authenticate(self, signature: str) -> Union[Accept, Deny]:
        """
        The client has answered with a WAMP AUTHENTICATE message. Verify the message and accept or deny.

        :param signature: Signature over the challenge as received from the authenticating session.
        :returns: Either accept or deny the session.
        """


class IRealmContainer(abc.ABC):
    """
    Interface to containers of routing realms the authentication system can query
    about the existence of realms and roles during authentication.
    """
    @abc.abstractmethod
    def has_realm(self, realm: str) -> bool:
        """
        Check if a route to a realm with the given name is currently running.

        :param realm: Realm name (the WAMP name, _not_ the run-time object ID).
        :returns: True if a route to the realm (for any role) exists.
        """

    @abc.abstractmethod
    def has_role(self, realm: str, authrole: str) -> bool:
        """
        Check if a role with the given name is currently running in the given realm.

        :param realm: WAMP realm (the WAMP name, _not_ the run-time object ID).
        :param authrole: WAMP authentication role (the WAMP URI, _not_ the run-time object ID).
        :returns: True if a route to the realm for the role exists.
        """

    @abc.abstractmethod
    def get_service_session(self, realm: str, role: str) -> ISession:
        """
        Returns a service session on the given realm using the given role.
        Service sessions are used for:

        * access dynamic authenticators (see :method:`crossbar.router.auth.pending.PendingAuth._init_dynamic_authenticator`)
        * access the WAMP meta API for the realm (see :method:`crossbar.worker.router.RouterController.start_router_realm`)
        * forward to/from WAMP for the HTTP bridge (see :class:`crossbar.webservice.rest.RouterWebServiceRestPublisher`, :class:`crossbar.webservice.rest.RouterWebServiceRestCaller`, :class:`crossbar.webservice.rest.RouterWebServiceWebhook`)

        :param realm: WAMP realm name.
        :param role: WAMP authentication role name.
        :returns: A service session joined on the given realm and role.
        """

    @abc.abstractmethod
    def get_controller_session(self) -> ISession:
        """
        Returns a control session connected to the local node management router.
        Control sessions are used for:

        * registering the realm container control interface
        * access the node security module

        :returns: A control session joined on the local node controller
            management realm, named `"crossbar"`.
        """


class IRealmStore(abc.ABC):
    """
    Realm store interface common to transient and persistent store implementations.
    """
    @property
    @abc.abstractmethod
    def type(self) -> str:
        """

        :return: Return type of realm store, e.g. ``"memory"`` or ``"cfxdb"``.
        """

    @property
    @abc.abstractmethod
    def is_running(self) -> bool:
        """

        :return: True if this realm store is currently running.
        """

    @abc.abstractmethod
    def start(self):
        """
        Initialize and start this realm store.

        .. note::

            This procedure may or may not run asynchronously
            depending on store type.
        """

    @abc.abstractmethod
    def stop(self):
        """
        Stop this realm store and retain all data.

        .. note::

            This procedure may or may not run asynchronously
            depending on store type.
        """

    @abc.abstractmethod
    def store_session_joined(self, session: ISession, details: SessionDetails):
        """

        :param session: Session that has joined a realm.
        :param details: Session details of the joined session.
        """

    @abc.abstractmethod
    def store_session_left(self, session: ISession, details: CloseDetails):
        """

        :param session: Session that has left a realm it was previously joined on.
        :param details: Session close details.
        """

    @abc.abstractmethod
    def get_session_by_session_id(self, session_id: int, joined_at: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get session information by WAMP session ID. If there is no session stored, return ``None``.

        .. note::

            In the rare event there is more than one session for the same WAMP session ID
            (which may happen as the WAMP session ID is effectively 56 bit), the procedure
            will return the information for the session with the most recent ``joined_at``
            timestamp.

        :param session_id: The WAMP session ID of the session for which to return information.
        :param joined_at: If there are more than one session for the given ``session_id``,
            only return the session with the given joining timestamp (or newer).
        :return: A set of information for the stored session.
        """

    @abc.abstractmethod
    def get_sessions_by_authid(self, authid: str) -> Optional[List[Tuple[str, int]]]:
        """
        Return session IDs and session joined timestamps given a WAMP authid, ordered by
        timestamps in reverse chronological order.

        :param authid: The WAMP authid to retrieve sessions for.
        :return: List of pairs ``(session_id, joined_at)`` or ``None`` if there are no
            sessions stored for the given ``authid``.
        """

    @abc.abstractmethod
    def attach_subscription_map(self, subscription_map: UriObservationMap):
        """

        :param subscription_map:
        :return:
        """

    @abc.abstractmethod
    def store_event(self, session: ISession, publication_id: int, publish: Publish):
        """
        Store event to event history.

        :param session: The publishing session.
        :param publication_id: The WAMP publication ID under which the publish-action happens.
        :param publish: The WAMP publish message.
        """

    @abc.abstractmethod
    def store_event_history(self, publication_id: int, subscription_id: int, receiver: ISession):
        """
        Store publication history for subscription.

        :param publication_id: The ID of the event publication to be persisted.
        :param subscription_id: The ID of the subscription the event (identified by the publication ID),
            was published to, because the event's topic matched the subscription.
        :param receiver: The receiving session.
        """

    @abc.abstractmethod
    def get_events(self, subscription_id: int, limit: Optional[int] = None):
        """
        Retrieve given number of last events for a given subscription.

        If no events are yet stored, an empty list ``[]`` is returned.
        If no history is maintained at all for the given subscription, ``None`` is returned.

        This procedure is called by the service session of Crossbar.io and
        exposed under the WAMP meta API procedure ``wamp.subscription.get_events``.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :param limit: Limit number of events returned.
        :return: List of events: at most ``limit`` events in reverse chronological order.
        """

    @abc.abstractmethod
    def get_event_history(self,
                          subscription_id: int,
                          from_ts: int,
                          until_ts: int,
                          reverse: Optional[bool] = None,
                          limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve event history for time range for a given subscription.

        If no history is maintained for the given subscription, None is returned.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :param from_ts: Filter events from this date (epoch time in ns).
        :param until_ts: Filter events until before this date (epoch time in ns).
        :param reverse:
        :param limit:
        """

    @abc.abstractmethod
    def maybe_queue_call(self, session: ISession, call, registration, authorization):
        """

        :param session:
        :param call:
        :param registration:
        :param authorization:
        :return:
        """

    @abc.abstractmethod
    def get_queued_call(self, registration):
        """

        :param registration:
        :return:
        """

    @abc.abstractmethod
    def pop_queued_call(self, registration):
        """

        :param registration:
        :return:
        """


class IInventory(abc.ABC):
    """
    Realm inventory interface.
    """
    @property
    @abc.abstractmethod
    def type(self) -> str:
        """

        :return: Return type of realm inventory, e.g. ``"wamp.eth"``.
        """

    @property
    @abc.abstractmethod
    def repo(self) -> FbsRepository:
        """

        :return:
        """

    @property
    @abc.abstractmethod
    def is_running(self) -> bool:
        """

        :return: True if this realm inventory is currently running.
        """

    @abc.abstractmethod
    def start(self):
        """
        Initialize and start this realm inventory.

        .. note::

            This procedure may or may not run asynchronously
            depending on inventory type.
        """

    @abc.abstractmethod
    def stop(self):
        """
        Stop this realm inventory and retain all data.

        .. note::

            This procedure may or may not run asynchronously
            depending on inventory type.
        """
