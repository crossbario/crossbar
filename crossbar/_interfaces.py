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

from autobahn.wamp import ISession

__all__ = ('IRealmContainer', )


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
    def has_role(self, realm: str, role: str) -> bool:
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
