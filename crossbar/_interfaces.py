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

"""
Interfaces used internally inside Crossbar.io to abstract/decouple different software components.

.. note::

    These interfaces are solely for internal use and not exposed or supposed to be used
    by users or from outside.
"""

import abc

from autobahn.wamp import ISession

__all__ = ('IRealmContainer',)


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
