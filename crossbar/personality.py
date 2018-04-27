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

from crossbar.common import checkconfig
from crossbar.controller.processtypes import RouterWorkerProcess, ContainerWorkerProcess, WebSocketTesteeWorkerProcess

from crossbar.worker.transport.factory import create_transport_from_config
from crossbar.worker.transport.resource import create_web_service, add_web_services, remove_web_services

#
# Warning: one or more imports below will trigger a Twisted reactor
# import on Windows!
#
from crossbar.controller.node import Node
from crossbar.worker.router import RouterWorkerSession
from crossbar.worker.container import ContainerWorkerSession
from crossbar.worker.testee import WebSocketTesteeWorkerSession


def default_native_workers():
    factory = dict()
    factory['router'] = {
        'class': RouterWorkerProcess,
        'worker_class': RouterWorkerSession,

        # check a whole router worker configuration item (including realms, transports, ..)
        'checkconfig_item': checkconfig.check_router,

        # only check router worker options
        'checkconfig_options': checkconfig.check_router_options,

        'logname': 'Router',
        'topics': {
            'starting': u'crossbar.node.on_router_starting',
            'started': u'crossbar.node.on_router_started',
        }
    }
    factory['container'] = {
        'class': ContainerWorkerProcess,
        'worker_class': ContainerWorkerSession,

        # check a whole container worker configuration item (including components, ..)
        'checkconfig_item': checkconfig.check_container,

        # only check container worker options
        'checkconfig_options': checkconfig.check_container_options,

        'logname': 'Container',
        'topics': {
            'starting': u'crossbar.node.on_container_starting',
            'started': u'crossbar.node.on_container_started',
        }
    }
    factory['websocket-testee'] = {
        'class': WebSocketTesteeWorkerProcess,
        'worker_class': WebSocketTesteeWorkerSession,

        # check a whole websocket testee worker configuration item
        'checkconfig_item': checkconfig.check_websocket_testee_options,

        # only check websocket testee worker worker options
        'checkconfig_options': checkconfig.check_websocket_testee_options,

        'logname': 'WebSocketTestee',
        'topics': {
            'starting': u'crossbar.node.on_websocket_testee_starting',
            'started': u'crossbar.node.on_websocket_testee_started',
        }
    }
    return factory


class Personality(object):

    NAME = 'community'

    # a list of directories to serach Jinja2 templates for
    # rendering various web resources. this must be a list
    # of _pairs_ to be used with pkg_resources.resource_filename()!
    TEMPLATE_DIRS = [('crossbar', 'web/templates')]

    NodeKlass = Node

    WorkerKlasses = [RouterWorkerSession, ContainerWorkerSession, WebSocketTesteeWorkerSession]

    native_workers = default_native_workers()

    """
    Node policy class.
    """

    create_router_transport = create_transport_from_config
    """
    Create a router (listening) transport from a (complete) router transport configuration:

        (reactor, name, config, cbdir, log, node,
         _router_session_factory=None, _web_templates=None, add_paths=False) -> None
    """

    create_web_service = create_web_service
    """
    Create a (single) Web service to be added to a Web service tree:

        (reactor, path_config, templates, log, cbdir, _router_session_factory, node, nested=True) -> None
    """

    add_web_services = add_web_services
    """
    Add Web service(s) to a Web service tree:

        (reactor, resource, paths, templates, log, cbdir, _router_session_factory, node) -> None
    """

    remove_web_services = remove_web_services
    """
    Remove web service(s) from a Web service tree:

        (reactor, resource, paths) -> None
    """
