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
        :returns: True if the given realm exists
        """

    @abc.abstractmethod
    def has_role(self, realm: str, role: str) -> bool:
        """
        :returns: True if the given role exists inside the realm
        """

    @abc.abstractmethod
    def get_service_session(self, realm: str, role: str) -> ISession:
        """
        :returns: ApplicationSession suitable for use by dynamic
            authenticators
        """
