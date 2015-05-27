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

import os

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

from crossbar._logging import make_logger

__all__ = ('NodeManagementSession',)


class NodeManagementSession(ApplicationSession):

    def onJoin(self, details):
        self.config.extra['onready'].callback(self)


class NodeManagementBridgeSession(ApplicationSession):

    log = make_logger()

    def __init__(self, config, management_session):
        ApplicationSession.__init__(self, config)
        self._management_session = management_session

    def _forward_call(self, *args, **kwargs):
        return self.call()

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("Management bridge attached to node router.")

        self._regs = {}

        @inlineCallbacks
        def on_registration_create(session_id, registration):
            uri = registration['uri']

            def forward_call(*args, **kwargs):
                return self.call(uri, *args, **kwargs)

            reg = yield self._management_session.register(forward_call, uri)
            self._regs[registration['id']] = reg

            self.log.info("Management bridge - forwarding procedure: {procedure}",
                          procedure=reg.procedure)

        yield self.subscribe(on_registration_create, u'wamp.registration.on_create')

        @inlineCallbacks
        def on_registration_delete(session_id, registration_id):
            reg = self._regs.pop(registration_id, None)

            if reg:
                yield reg.unregister()
                self.log.info("Management bridge - removed procedure {procedure}",
                              procedure=reg.procedure)
            else:
                self.log.warn("Management bridge - WARNING: on_registration_delete() for unmapped registration_id {reg_id}",
                              reg_id=registration_id)

        yield self.subscribe(on_registration_delete, u'wamp.registration.on_delete')

        self.log.info("Management bridge ready.")


class NodeManagementSessionOld(ApplicationSession):

    """
    """
    log = make_logger()

    def __init__(self):
        ApplicationSession.__init__(self)

    def onConnect(self):
        self.join("crossbar.cloud")

    def is_paired(self):
        return False

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("Connected to Crossbar.io Management Cloud.")

        from twisted.internet import reactor

        self.factory.node_session.setControllerSession(self)

        if not self.is_paired():
            try:
                node_info = {}
                node_publickey = "public key"
                activation_code = yield self.call('crossbar.cloud.get_activation_code', node_info, node_publickey)
            except Exception:
                self.log.failure("internal error: {log_failure.value}")
            else:
                self.log.info("Log into https://console.crossbar.io to configure your instance using the activation code: {}".format(activation_code))

                reg = None

                def activate(node_id, certificate):
                    # check if certificate was issued by Tavendo
                    # check if certificate matches node key
                    # persist node_id
                    # persist certificate
                    # restart node
                    reg.unregister()

                    self.publish('crossbar.node.onactivate', node_id)

                    self.log.info("Restarting node in 5 seconds ...")
                    reactor.callLater(5, self.factory.node_controller_session.restart_node)

                reg = yield self.register(activate, 'crossbar.node.activate.{}'.format(activation_code))
        else:
            pass

        yield self.register(self.factory.node_controller_session.get_node_worker_processes, 'crossbar.node.get_node_worker_processes')

        self.publish('com.myapp.topic1', os.getpid())
