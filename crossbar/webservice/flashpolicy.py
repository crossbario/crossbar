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

import re

from twisted.internet.protocol import Protocol, Factory

__all__ = (
    'FlashPolicyProtocol',
    'FlashPolicyFactory'
)


class FlashPolicyProtocol(Protocol):
    """
    Flash Player 9 (version 9.0.124.0 and above) implements a strict new access
    policy for Flash applications that make Socket or XMLSocket connections to
    a remote host. It now requires the presence of a socket policy file
    on the server.

    We want this to support the Flash WebSockets bridge which is needed for
    older browser, in particular MSIE9/8.

    .. seealso::
       * `Flash policy files background <http://www.lightsphere.com/dev/articles/flash_socket_policy.html>`_
    """

    REQUESTPAT = re.compile(r"^\s*<policy-file-request\s*/>")
    REQUESTMAXLEN = 200
    REQUESTTIMEOUT = 5
    POLICYFILE = """<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="%s" to-ports="%s" /></cross-domain-policy>"""

    def __init__(self, allowedDomain, allowedPorts):
        """

        :param allowedPort: The port to which Flash player should be allowed to connect.
        :type allowedPort: int
        """
        self._allowedDomain = allowedDomain
        self._allowedPorts = allowedPorts
        self.received = ""
        self.dropConnection = None

    def connectionMade(self):
        # DoS protection
        ##
        def dropConnection():
            self.transport.abortConnection()
            self.dropConnection = None
        self.dropConnection = self.factory.reactor.callLater(FlashPolicyProtocol.REQUESTTIMEOUT, dropConnection)

    def connectionLost(self, reason):
        if self.dropConnection:
            self.dropConnection.cancel()
            self.dropConnection = None

    def dataReceived(self, data):
        self.received += data
        if FlashPolicyProtocol.REQUESTPAT.match(self.received):
            # got valid request: send policy file
            ##
            self.transport.write(FlashPolicyProtocol.POLICYFILE % (self._allowedDomain, self._allowedPorts))
            self.transport.loseConnection()
        elif len(self.received) > FlashPolicyProtocol.REQUESTMAXLEN:
            # possible DoS attack
            ##
            self.transport.abortConnection()
        else:
            # need more data
            ##
            pass


class FlashPolicyFactory(Factory):

    def __init__(self, allowedDomain=None, allowedPorts=None, reactor=None):
        """

        :param allowedDomain: The domain from which to allow Flash to connect from.
           If ``None``, allow from anywhere.
        :type allowedDomain: str or None
        :param allowedPorts: The ports to which Flash player should be allowed to connect.
           If ``None``, allow any ports.
        :type allowedPorts: list of int or None
        :param reactor: Twisted reactor to use. If not given, autoimport.
        :type reactor: obj
        """
        # lazy import to avoid reactor install upon module import
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor

        self._allowedDomain = str(allowedDomain) or "*"

        if allowedPorts:
            self._allowedPorts = ",".join([str(port) for port in allowedPorts])
        else:
            self._allowedPorts = "*"

    def buildProtocol(self, addr):
        proto = FlashPolicyProtocol(self._allowedDomain, self._allowedPorts)
        proto.factory = self
        return proto
