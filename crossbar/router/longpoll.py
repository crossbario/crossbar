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

import json

from collections import deque

from twisted.web.resource import Resource, NoResource

# Each of the following 2 trigger a reactor import at module level
# See https://twistedmatrix.com/trac/ticket/8246 for fixing it
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from autobahn.util import generate_token, _LazyHexFormatter

from autobahn.wamp.websocket import parseSubprotocolIdentifier

from autobahn.wamp.exception import SerializationError, \
    TransportLost

from txaio import make_logger
from txaio import failure_format_traceback, failure_message, create_failure


__all__ = (
    'WampLongPollResource',
)


class WampLongPollResourceSessionSend(Resource):
    """
    A Web resource for sending via XHR that is part of :class:`autobahn.twisted.longpoll.WampLongPollResourceSession`.
    """

    log = make_logger()

    def __init__(self, parent):
        """

        :param parent: The Web parent resource for the WAMP session.
        :type parent: Instance of :class:`autobahn.twisted.longpoll.WampLongPollResourceSession`.
        """
        Resource.__init__(self)
        self._parent = parent

    def render_POST(self, request):
        """
        A client sends a message via WAMP-over-Longpoll by HTTP/POSTing
        to this Web resource. The body of the POST should contain a batch
        of WAMP messages which are serialized according to the selected
        serializer, and delimited by a single ``\0`` byte in between two WAMP
        messages in the batch.
        """
        payload = request.content.read()
        self.log.debug(
            "WampLongPoll: receiving data for transport '{tid}'\n{octets}",
            tid=self._parent._transport_id,
            octets=_LazyHexFormatter(payload),
        )

        try:
            # process (batch of) WAMP message(s)
            self._parent.onMessage(payload, None)

        except Exception:
            f = create_failure()
            self.log.error(
                "Could not unserialize WAMP message: {msg}",
                msg=failure_message(f),
            )
            self.log.debug("{tb}", tb=failure_format_traceback(f))
            return self._parent._parent._fail_request(
                request,
                b"could not unserialize WAMP message."
            )

        else:
            request.setResponseCode(http.NO_CONTENT)
            self._parent._parent._set_standard_headers(request)
            self._parent._isalive = True
            return b""


class WampLongPollResourceSessionReceive(Resource):
    """
    A Web resource for receiving via XHR that is part of :class:`autobahn.twisted.longpoll.WampLongPollResourceSession`.
    """

    log = make_logger()

    def __init__(self, parent):
        """

        :param parent: The Web parent resource for the WAMP session.
        :type parent: Instance of :class:`autobahn.twisted.longpoll.WampLongPollResourceSession`.
        """
        Resource.__init__(self)
        self._parent = parent
        self.reactor = self._parent._parent.reactor

        self._queue = deque()
        self._request = None
        self._killed = False

        # FIXME: can we read the loglevel from self.log currently set?
        if False:
            def logqueue():
                if not self._killed:
                    self.log.debug(
                        "WampLongPoll: transport '{tid}' - currently polled"
                        " {is_polled}, pending messages {pending}",
                        tid=self._parent._transport_id,
                        is_polled=self._request is not None,
                        pending=len(self._queue),
                    )
                    self.reactor.callLater(1, logqueue)
            logqueue()

    def queue(self, data):
        """
        Enqueue data to be received by client.

        :param data: The data to be received by the client.
        :type data: bytes
        """
        self._queue.append(data)
        self._trigger()

    def _kill(self):
        """
        Kill any outstanding request.
        """
        if self._request:
            self._request.finish()
            self._request = None
        self._killed = True

    def _trigger(self):
        """
        Trigger batched sending of queued messages.
        """
        if self._request and len(self._queue):

            if self._parent._serializer._serializer._batched:
                # in batched mode, write all pending messages
                while len(self._queue) > 0:
                    msg = self._queue.popleft()
                    self._request.write(msg)
            else:
                # in unbatched mode, only write 1 pending message
                msg = self._queue.popleft()
                if isinstance(msg, bytes):
                    self._request.write(msg)
                else:
                    self.log.error(
                        "internal error: cannot write data of type {type_} - {msg}",
                        type_=type(msg),
                        msg=msg,
                    )

            self._request.finish()
            self._request = None

    def render_POST(self, request):
        """
        A client receives WAMP messages by issuing a HTTP/POST to this
        Web resource. The request will immediately return when there are
        messages pending to be received. When there are no such messages
        pending, the request will "just hang", until either a message
        arrives to be received or a timeout occurs.
        """
        # remember request, which marks the session as being polled
        self._request = request

        self._parent._parent._set_standard_headers(request)
        mime_type = self._parent._serializer.MIME_TYPE
        if isinstance(mime_type, str):
            mime_type = mime_type.encode('utf8')
        request.setHeader(b'content-type', mime_type)

        def cancel(_):
            self.log.debug(
                "WampLongPoll: poll request for transport '{tid}' has gone away",
                tid=self._parent._transport_id,
            )
            self._request = None

        request.notifyFinish().addErrback(cancel)

        self._parent._isalive = True
        self._trigger()

        return NOT_DONE_YET


class WampLongPollResourceSessionClose(Resource):
    """
    A Web resource for closing the Long-poll session WampLongPollResourceSession.
    """

    log = make_logger()

    def __init__(self, parent):
        """

        :param parent: The Web parent resource for the WAMP session.
        :type parent: Instance of :class:`autobahn.twisted.longpoll.WampLongPollResourceSession`.
        """
        Resource.__init__(self)
        self._parent = parent

    def render_POST(self, request):
        """
        A client may actively close a session (and the underlying long-poll transport)
        by issuing a HTTP/POST with empty body to this resource.
        """
        self.log.debug(
            "WampLongPoll: closing transport '{tid}'",
            tid=self._parent._transport_id,
        )

        # now actually close the session
        self._parent.close()

        self.log.debug(
            "WampLongPoll: session ended and transport {tid} closed",
            tid=self._parent._transport_id,
        )

        request.setResponseCode(http.NO_CONTENT)
        self._parent._parent._set_standard_headers(request)
        return b""


class WampLongPollResourceSession(Resource):
    """
    A Web resource representing an open WAMP session.
    """

    log = make_logger()

    def __init__(self, parent, transport_details):
        """
        Create a new Web resource representing a WAMP session.

        :param parent: The parent Web resource.
        :type parent: Instance of :class:`autobahn.twisted.longpoll.WampLongPollResource`.
        :param transport_details: Details on the WAMP-over-Longpoll transport session.
        :type transport_details: dict
        """
        Resource.__init__(self)

        self._parent = parent
        self.reactor = self._parent.reactor

        self._transport_details = transport_details
        self._transport_id = transport_details['transport']
        self._serializer = transport_details['serializer']
        self._session = None

        # session authentication information
        #
        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None

        self._send = WampLongPollResourceSessionSend(self)
        self._receive = WampLongPollResourceSessionReceive(self)
        self._close = WampLongPollResourceSessionClose(self)

        self.putChild(b"send", self._send)
        self.putChild(b"receive", self._receive)
        self.putChild(b"close", self._close)

        self._isalive = False

        # kill inactive sessions after this timeout
        #
        killAfter = self._parent._killAfter
        if killAfter > 0:
            def killIfDead():
                if not self._isalive:
                    self.log.debug(
                        "WampLongPoll: killing inactive WAMP session with transport '{tid}'",
                        tid=self._transport_id,
                    )

                    self.onClose(False, 5000, "session inactive")
                    self._receive._kill()
                    if self._transport_id in self._parent._transports:
                        del self._parent._transports[self._transport_id]
                else:
                    self.log.debug(
                        "WampLongPoll: transport '{tid}' is still alive",
                        tid=self._transport_id,
                    )

                    self._isalive = False
                    self.reactor.callLater(killAfter, killIfDead)

            self.reactor.callLater(killAfter, killIfDead)
        else:
            self.log.debug(
                "WampLongPoll: transport '{tid}' automatic killing of inactive session disabled",
                tid=self._transport_id,
            )

        self.log.debug(
            "WampLongPoll: session resource for transport '{tid}' initialized)",
            tid=self._transport_id,
        )

        self.onOpen()

    def render_GET(self, request):
        self._parent._set_standard_headers(request)

        res = {
            u'transport': self._transport_id,
            u'session': self._session._session_id if self._session else None
        }
        return json.dumps(res).encode()

    def close(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.close`
        """
        if self.isOpen():
            self.onClose(True, 1000, u"session closed")
            self._receive._kill()
            del self._parent._transports[self._transport_id]
        else:
            raise TransportLost()

    def abort(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.abort`
        """
        if self.isOpen():
            self.onClose(True, 1000, u"session aborted")
            self._receive._kill()
            del self._parent._transports[self._transport_id]
        else:
            raise TransportLost()

    # noinspection PyUnusedLocal
    def onClose(self, wasClean, code, reason):
        """
        Callback from :func:`autobahn.websocket.interfaces.IWebSocketChannel.onClose`
        """
        if self._session:
            try:
                self._session.onClose(wasClean)
            except Exception:
                # ignore exceptions raised here, but log ..
                self.log.failure("invoking session's onClose failed")
            self._session = None

    def onOpen(self):
        """
        Callback from :func:`autobahn.websocket.interfaces.IWebSocketChannel.onOpen`
        """
        self._session = self._parent._factory()
        # noinspection PyBroadException
        try:
            self._session.onOpen(self)
        except Exception:
            # ignore exceptions raised here, but log ..
            self.log.failure("Invoking session's onOpen failed")

    def onMessage(self, payload, isBinary):
        """
        Callback from :func:`autobahn.websocket.interfaces.IWebSocketChannel.onMessage`
        """
        for msg in self._serializer.unserialize(payload, isBinary):
            self.log.debug(
                "WampLongPoll: RX {octets}",
                octets=_LazyHexFormatter(msg),
            )
            self._session.onMessage(msg)

    def send(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.send`
        """
        if self.isOpen():
            try:
                self.log.debug(
                    "WampLongPoll: TX {octets}",
                    octets=_LazyHexFormatter(msg),
                )
                payload, isBinary = self._serializer.serialize(msg)
            except Exception as e:
                # all exceptions raised from above should be serialization errors ..
                f = create_failure()
                self.log.error(
                    "Unable to serialize WAMP application payload: {msg}",
                    msg=failure_message(f),
                )
                self.log.debug("{tb}", tb=failure_format_traceback(f))
                raise SerializationError("unable to serialize WAMP application payload ({0})".format(e))
            else:
                self._receive.queue(payload)
        else:
            raise TransportLost()

    def isOpen(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.isOpen`
        """
        return self._session is not None


class WampLongPollResourceOpen(Resource):
    """
    A Web resource for creating new WAMP sessions.
    """

    log = make_logger()

    def __init__(self, parent):
        """

        :param parent: The parent Web resource.
        :type parent: Instance of :class:`autobahn.twisted.longpoll.WampLongPollResource`.
        """
        Resource.__init__(self)
        self._parent = parent

    def render_POST(self, request):
        """
        Request to create a new WAMP session.
        """
        self.log.debug("WampLongPoll: creating new session ..")

        payload = request.content.read().decode('utf8')
        try:
            options = json.loads(payload)
        except Exception:
            f = create_failure()
            self.log.error(
                "Couldn't parse WAMP request body: {msg}",
                msg=failure_message(f),
            )
            self.log.debug("{msg}", msg=failure_format_traceback(f))
            return self._parent._fail_request(request, b"could not parse WAMP session open request body")

        if not isinstance(options, dict):
            return self._parent._fail_request(request, b"invalid type for WAMP session open request")

        if u'protocols' not in options:
            return self._parent._fail_request(request, "missing attribute 'protocols' in WAMP session open request")

        # determine the protocol to speak
        #
        protocol = None
        serializer = None
        for p in options[u'protocols']:
            version, serializerId = parseSubprotocolIdentifier(p)
            if version == 2 and serializerId in self._parent._serializers.keys():
                serializer = self._parent._serializers[serializerId]
                protocol = p
                break

        if protocol is None:
            return self._fail_request(
                request,
                b"no common protocol to speak (I speak: {0})".format(
                    ["wamp.2.{0}".format(s) for s in self._parent._serializers.keys()])
            )

        # make up new transport ID
        #
        if self._parent._debug_transport_id:
            # use fixed transport ID for debugging purposes
            transport = self._parent._debug_transport_id
        else:
            transport = generate_token(1, 12)

        # this doesn't contain all the info (when a header key appears multiple times)
        # http_headers_received = request.getAllHeaders()
        http_headers_received = {}
        for key, values in request.requestHeaders.getAllRawHeaders():
            if key not in http_headers_received:
                http_headers_received[key] = []
            http_headers_received[key].extend(values)

        transport_details = {
            u'transport': transport,
            u'serializer': serializer,
            u'protocol': protocol,
            u'peer': request.getClientIP(),
            u'http_headers_received': http_headers_received,
            u'http_headers_sent': None
        }

        # create instance of WampLongPollResourceSession or subclass thereof ..
        #
        self._parent._transports[transport] = self._parent.protocol(self._parent, transport_details)

        # create response
        #
        self._parent._set_standard_headers(request)
        request.setHeader(b'content-type', b'application/json; charset=utf-8')

        result = {
            u'transport': transport,
            u'protocol': protocol
        }

        self.log.debug(
            "WampLongPoll: new session created on transport"
            " '{transport}'".format(
                transport=transport,
            )
        )

        payload = json.dumps(result)
        return payload.encode()


class WampLongPollResource(Resource):
    """
    A WAMP-over-Longpoll resource for use with Twisted Web Resource trees.

    This class provides an implementation of the WAMP-over-Longpoll transport
    for WAMP.

    The Resource exposes the following paths (child resources).

    Opening a new WAMP session:

       * ``<base-url>/open``

    Once a transport is created and the session is opened:

       * ``<base-url>/<transport-id>/send``
       * ``<base-url>/<transport-id>/receive``
       * ``<base-url>/<transport-id>/close``
    """

    log = make_logger()

    protocol = WampLongPollResourceSession

    def __init__(self,
                 factory,
                 serializers=None,
                 timeout=10,
                 killAfter=30,
                 queueLimitBytes=128 * 1024,
                 queueLimitMessages=100,
                 debug_transport_id=None,
                 reactor=None):
        """
        Create new HTTP WAMP Web resource.

        :param factory: A (router) session factory.
        :type factory: Instance of :class:`autobahn.twisted.wamp.RouterSessionFactory`.
        :param serializers: List of WAMP serializers.
        :type serializers: list of obj (which implement :class:`autobahn.wamp.interfaces.ISerializer`)
        :param timeout: XHR polling timeout in seconds.
        :type timeout: int
        :param killAfter: Kill WAMP session after inactivity in seconds.
        :type killAfter: int
        :param queueLimitBytes: Kill WAMP session after accumulation of this many bytes in send queue (XHR poll).
        :type queueLimitBytes: int
        :param queueLimitMessages: Kill WAMP session after accumulation of this many message in send queue (XHR poll).
        :type queueLimitMessages: int
        :param debug: Enable debug logging.
        :type debug: bool
        :param debug_transport_id: If given, use this fixed transport ID.
        :type debug_transport_id: str
        :param reactor: The Twisted reactor to run under.
        :type reactor: obj
        """
        Resource.__init__(self)

        # RouterSessionFactory
        self._factory = factory

        # lazy import to avoid reactor install upon module import
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor

        self._debug_transport_id = debug_transport_id
        self._timeout = timeout
        self._killAfter = killAfter
        self._queueLimitBytes = queueLimitBytes
        self._queueLimitMessages = queueLimitMessages

        if serializers is None:
            serializers = []

            # try CBOR WAMP serializer
            try:
                from autobahn.wamp.serializer import CBORSerializer
                serializers.append(CBORSerializer(batched=True))
                serializers.append(CBORSerializer())
            except ImportError:
                pass

            # try MsgPack WAMP serializer
            try:
                from autobahn.wamp.serializer import MsgPackSerializer
                serializers.append(MsgPackSerializer(batched=True))
                serializers.append(MsgPackSerializer())
            except ImportError:
                pass

            # try UBJSON WAMP serializer
            try:
                from autobahn.wamp.serializer import UBJSONSerializer
                serializers.append(UBJSONSerializer(batched=True))
                serializers.append(UBJSONSerializer())
            except ImportError:
                pass

            # try JSON WAMP serializer
            try:
                from autobahn.wamp.serializer import JsonSerializer
                serializers.append(JsonSerializer(batched=True))
                serializers.append(JsonSerializer())
            except ImportError:
                pass

            if not serializers:
                raise Exception("could not import any WAMP serializers")

        self._serializers = {}
        for ser in serializers:
            self._serializers[ser.SERIALIZER_ID] = ser

        self._transports = {}

        # <Base URL>/open
        #
        self.putChild(b"open", WampLongPollResourceOpen(self))

        self.log.debug("WampLongPollResource initialized")

    def render_GET(self, request):
        request.setHeader(b'content-type', b'text/html; charset=UTF-8')
        peer = b"{0}:{1}".format(request.client.host, request.client.port)
        return self._get_notice(peer=peer)

    def getChild(self, name, request):
        """
        Returns send/receive/close resource for transport.

        .. seealso::

           * :class:`twisted.web.resource.Resource`
           * :class:`zipfile.ZipFile`
        """

        name = name.decode('utf8')

        if name not in self._transports:
            if not name:
                return self
            else:
                self.log.error("No WAMP transport '{name}'", name=name)
                return NoResource("no WAMP transport '{0}'".format(name))

        if len(request.postpath) == 0 or (len(request.postpath) == 1 and request.postpath[0] in [b'send', b'receive', b'close']):
            return self._transports[name]
        else:
            return NoResource("invalid WAMP transport operation '{0}'".format(request.postpath))

    def _set_standard_headers(self, request):
        """
        Set standard HTTP response headers.
        """
        origin = request.getHeader(b"origin")
        if origin is None or origin == b"null":
            origin = b"*"
        request.setHeader(b'access-control-allow-origin', origin)
        request.setHeader(b'access-control-allow-credentials', b'true')
        request.setHeader(b'cache-control', b'no-store, no-cache, must-revalidate, max-age=0')

        headers = request.getHeader(b'access-control-request-headers')
        if headers is not None:
            request.setHeader(b'access-control-allow-headers', headers)

    def _fail_request(self, request, msg):
        """
        Fails a request to the long-poll service.
        """
        self._set_standard_headers(request)
        request.setHeader(b'content-type', b'text/plain; charset=UTF-8')
        request.setResponseCode(http.BAD_REQUEST)
        return msg

    def _get_notice(self, peer, redirect_url=None, redirect_after=0):
        """
        Render a user notice (HTML page) when the Long-Poll root resource
        is accessed via HTTP/GET (by a user).

        :param redirect_url: Optional URL to redirect the user to.
        :type redirect_url: str
        :param redirect_after: When ``redirect_url`` is provided, redirect after this time (seconds).
        :type redirect_after: int
        """
        if redirect_url:
            redirect = b"""<meta http-equiv="refresh" content="{};URL='{}'">""".format(redirect_after, redirect_url)
        else:
            redirect = b""

        html = b"""
<!DOCTYPE html>
<html>
   <head>
      %s
      <style>
         body {
            color: #333;
            background-color: #ffde00;
            font-family: "Segoe UI", "Lucida Grande", "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 16px;
         }

         a, a:visited, a:hover {
            color: #333;
         }
      </style>
   </head>
   <body>
      <h1>Crossbar.io</h1>
      <p>I am not Web server, but a <b>WAMP-over-Longpoll</b> listening transport.</p>
   </body>
</html>
""" % (redirect,)
        return html
