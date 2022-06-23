#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import re

from twisted.internet.protocol import Protocol, Factory

__all__ = ('FlashPolicyProtocol', 'FlashPolicyFactory')


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
