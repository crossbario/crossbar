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

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import SubscribeOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession

from txaio import make_logger

__all__ = ('NodeManagementSession', 'NodeManagementBridgeSession')


class NodeManagementSession(ApplicationSession):

    """
    This session is used for any uplink CDC connection.
    """

    log = make_logger()

    def onConnect(self):
        self.log.info("CDC connection established")

        extra = {
            # forward the client pubkey: this allows us to omit authid as
            # the router can identify us with the pubkey already
            u'pubkey': self.config.extra['node_key'].public_key(),

            # not yet implemented. a public key the router should provide
            # a trustchain for it's public key. the trustroot can eg be
            # hard-coded in the client, or come from a command line option.
            u'trustroot': None,

            # not yet implemented. for authenticating the router, this
            # challenge will need to be signed by the router and send back
            # in AUTHENTICATE for client to verify. A string with a hex
            # encoded 32 bytes random value.
            u'challenge': None,

            # https://tools.ietf.org/html/rfc5929
            u'channel_binding': u'tls-unique'
        }

        # now request to join ..
        self.join(realm=None,
                  authmethods=[u'cryptosign'],
                  authextra=extra)

    def onChallenge(self, challenge):
        self.log.info("authentication challenge received: {challenge}", challenge=challenge)

        if challenge.method == u'cryptosign':
            # alright, we've got a challenge from the router.

            # not yet implemented. check the trustchain the router provided against
            # our trustroot, and check the signature provided by the
            # router for our previous challenge. if both are ok, everything
            # is fine - the router is authentic wrt our trustroot.

            # sign the challenge with our private key.
            signed_challenge = self.config.extra['node_key'].sign_challenge(self, challenge)

            # send back the signed challenge for verification
            return signed_challenge

        else:
            raise Exception("don't know how to compute challenge for authmethod {}".format(challenge.method))

    def onJoin(self, details):
        # SessionDetails(realm=<com.crossbario.cdc.mrealm-test1>, session=3537745190930657, authid=<node0>, authrole=<cdc-node>, authmethod=cryptosign, authprovider=dynamic, authextra={'bar': 'baz', 'foo': 42})
        self.log.info("CDC uplink (remote leg) ready: {details}", details=details)
        self.config.extra['on_ready'].callback((self, details.realm, details.authid, details.authextra))

    def onLeave(self, details):
        if details.reason != u"wamp.close.normal":
            self.log.warn("CDC session detached: '{reason}' - {message}", reason=details.reason, message=details.message)
        else:
            self.log.debug("CDC session detached: '{reason}' - {message}", reason=details.reason, message=details.message)

        if not self.config.extra['on_ready'].called:
            self.config.extra['on_ready'].errback(Exception("CDC session failed to get ready"))

        self.config.extra['on_exit'].callback(details.reason)

        self.disconnect()

    def onDisconnect(self):
        self.log.debug("CDC session disconnected")

        node = self.config.extra['node']

        # FIXME: the node shutdown behavior should be more sophisticated than this!
        shutdown_on_cdc_lost = False

        if shutdown_on_cdc_lost:
            if node._controller:
                node._controller.shutdown()


class NodeManagementBridgeSession(ApplicationSession):

    """
    The management bridge is a WAMP session that lives on the local management router,
    but has access to a 2nd WAMP session that lives on the uplink CDC router.

    The bridge is responsible for forwarding calls from CDC into the local node,
    and for forwarding events from the local node to CDC.
    """

    log = make_logger()

    def __init__(self, config):
        ApplicationSession.__init__(self, config)
        self._manager = None
        self._management_realm = None
        self._node_id = None
        self._regs = {}

    def attach_manager(self, manager, management_realm, node_id):
        """
        Attach management uplink session when the latter has been fully established
        and is ready to be used.

        :param manager: uplink session.
        :type manager: instance of `autobahn.wamp.protocol.ApplicationSession`
        :param management_realm: The management realm that was assigned by CDC to this node.
        :type management_realm: unicode
        :param node_id: The node ID that was assigned by CDC to this node.
        :type node_id: unicode
        """
        assert(self._manager is None)
        self.log.info('NodeManagementBridgeSession: manager attached (as node "{node_id}" on management realm "{management_realm}")', node_id=node_id, management_realm=management_realm)
        self._manager = manager
        self._management_realm = management_realm
        self._node_id = node_id

    def detach_manager(self):
        """
        Detach management uplink session (eg when that session has been lost).
        """
        assert(self._manager is not None)
        self._manager = None
        self._management_realm = None
        self._node_id = None

    def _translate_uri(self, uri):
        """
        Translate a local URI (one that is used on the local node management router)
        to a remote URI (one used on the uplink management session at the CDC router
        for the management realm).

        Example:

            crossbar.worker.worker-001.start_manhole
                ->
            com.crossbario.cdc.node.<node_id>.worker.<worker_id>.start_manhole

        The complete namespace "com.crossbario.cdc.node.*"" is part of the node
        management API.
        """
        _PREFIX = 'crossbar.'
        _TARGET_PREFIX = 'com.crossbario.cdc.node.'

        if uri.startswith(_PREFIX):
            suffix = uri[len(_PREFIX):]
            mapped_uri = u''.join([_TARGET_PREFIX, self._node_id, suffix])
            self.log.info("mapped URI {uri} to {mapped_uri}", uri=uri, mapped_uri=mapped_uri)
            return mapped_uri
        else:
            raise Exception("don't know how to translate URI {}".format(uri))

    @inlineCallbacks
    def onJoin(self, details):

        self.log.info("Joined realm '{realm}' on node management router", realm=details.realm)

        # setup event forwarding (events originating locally are forwarded uplink)
        #
        @inlineCallbacks
        def on_management_event(*args, **kwargs):
            if not (self._manager and self._manager.is_attached()):
                self.log.warn("Can't foward management event: CDC session not attached")
                return

            details = kwargs.pop('details')

            # a node local event such as 'crossbar.node.on_ready' is mogrified to 'local.crossbar.node.on_ready'
            # (one reason is that URIs such as 'wamp.*' and 'crossbar.*' are restricted to trusted sessions, and
            # the management bridge is connecting over network to the uplink CDC and hence can't be trusted)
            #
            topic = self._translate_uri(details.topic)

            try:
                yield self._manager.publish(topic, *args, options=PublishOptions(acknowledge=True), **kwargs)
            except Exception:
                self.log.failure(
                    "Failed to forward event on topic '{topic}': {log_failure.value}",
                    topic=topic,
                )
            else:
                self.log.info("Forwarded management event on topic '{topic}'", topic=topic)

        yield self.subscribe(on_management_event, u"crossbar.", options=SubscribeOptions(match=u"prefix", details_arg="details"))

        # setup call forwarding (calls originating remotely from CDC are forwarded locally)
        #
        @inlineCallbacks
        def on_registration_create(session_id, registration):
            # we use the WAMP meta API implemented by CB to get notified whenever a procedure is
            # registered/unregister on the node management router, setup a forwarding procedure
            # and register that on the uplink CDC router

            if not (self._manager and self._manager.is_attached()):
                self.log.warn("Can't create forward management registration: CDC session not attached")
                return

            local_uri = registration['uri']
            remote_uri = self._translate_uri(local_uri)

            self.log.info('Setup management API forwarding: {remote_uri} -> {local_uri}', remote_uri=remote_uri, local_uri=local_uri)

            def forward_call(*args, **kwargs):
                return self.call(local_uri, *args, **kwargs)

            try:
                reg = yield self._manager.register(forward_call, remote_uri)
            except Exception:
                self.log.failure(
                    "Failed to register management procedure '{remote_uri}': {log_failure.value}",
                    remote_uri=remote_uri,
                )
            else:
                self._regs[registration['id']] = reg
                self.log.debug("Management procedure registered: '{remote_uri}'", remote_uri=reg.procedure)

        yield self.subscribe(on_registration_create, u'wamp.registration.on_create')

        # tear down call forwarding
        #
        @inlineCallbacks
        def on_registration_delete(session_id, registration_id):
            if not (self._manager and self._manager.is_attached()):
                self.log.warn("Can't delete forward management registration: CDC session not attached")
                return

            reg = self._regs.pop(registration_id, None)

            if reg:
                yield reg.unregister()
                self.log.debug("Management procedure unregistered: '{remote_uri}'", remote_uri=reg.procedure)
            else:
                self.log.warn("Could not remove forwarding for unmapped registration_id {reg_id}", reg_id=registration_id)

        yield self.subscribe(on_registration_delete, u'wamp.registration.on_delete')

        self.log.info("CDC uplink (local leg) ready!")
