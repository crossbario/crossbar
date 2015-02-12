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

from twisted.python import log
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

__all__ = ('NodeManagementSession',)


class NodeManagementSession(ApplicationSession):

    """
    """

    def __init__(self):
        ApplicationSession.__init__(self)

    def onConnect(self):
        self.join("crossbar.cloud")

    def is_paired(self):
        return False

    @inlineCallbacks
    def onJoin(self, details):
        log.msg("Connected to Crossbar.io Management Cloud.")

        from twisted.internet import reactor

        self.factory.node_session.setControllerSession(self)

        if not self.is_paired():
            try:
                node_info = {}
                node_publickey = "public key"
                activation_code = yield self.call('crossbar.cloud.get_activation_code', node_info, node_publickey)
            except Exception as e:
                log.msg("internal error: {}".format(e))
            else:
                log.msg("Log into https://console.crossbar.io to configure your instance using the activation code: {}".format(activation_code))

                reg = None

                def activate(node_id, certificate):
                    # check if certificate was issued by Tavendo
                    # check if certificate matches node key
                    # persist node_id
                    # persist certificate
                    # restart node
                    reg.unregister()

                    self.publish('crossbar.node.onactivate', node_id)

                    log.msg("Restarting node in 5 seconds ...")
                    reactor.callLater(5, self.factory.node_controller_session.restart_node)

                reg = yield self.register(activate, 'crossbar.node.activate.{}'.format(activation_code))
        else:
            pass

        yield self.register(self.factory.node_controller_session.get_node_worker_processes, 'crossbar.node.get_node_worker_processes')

        self.publish('com.myapp.topic1', os.getpid())
