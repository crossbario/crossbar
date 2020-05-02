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

from datetime import datetime

from autobahn.util import utcstr
from crossbar.worker.rlink import RLinkManager


class RouterComponent(object):

    """
    A application component hosted and running inside a router worker.
    """

    def __init__(self, id, config, session):
        """

        :param id: The component ID within the router instance.
        :type id: str

        :param config: The component's configuration.
        :type config: dict

        :param session: The component application session.
        :type session: obj (instance of ApplicationSession)
        """
        self.id = id
        self.config = config
        self.session = session
        self.created = datetime.utcnow()

    def marshal(self):
        """
        Marshal object information for use with WAMP calls/events.
        """
        now = datetime.utcnow()
        return {
            'id': self.id,
            # 'started' is used by container-components; keeping it
            # for consistency in the public API
            'started': utcstr(self.created),
            'uptime': (now - self.created).total_seconds(),
            'config': self.config
        }


class RouterRealm(object):

    """
    A realm running in a router worker.
    """

    def __init__(self, controller, id, config, router=None, session=None):
        """

        :param controller: The controller this router is running under.
        :type controller: object

        :param id: The realm ID within the router worker, identifying the router.
        :type id: str

        :param config: The realm configuration.
        :type config: dict

        :param router: The router (within the router worker) serving the realm.
        :type router: :class:`crossbar.router.router.Router`

        :param session: The realm service session.
        :type session: :class:`crossbar.router.service.RouterServiceAgent`
        """
        self.controller = controller
        self.id = id
        self.config = config

        # this is filled later (after construction) when the router has been started
        self.router = router

        # this is filled later (after construction) when the router service agent session has been started
        self.session = session

        # router-realm links ("router-to-router connections")
        self.rlink_manager = RLinkManager(self, controller)

        self.created = datetime.utcnow()

        # Crossbar.io role run-time ID -> RouterRealmRole
        self.roles = {}

        # role WAMP name -> Crossbar.io role run-time ID
        self.role_to_id = {}

    def marshal(self):
        marshalled = {
            'id': self.id,
            'config': self.config,
            'created': utcstr(self.created),
            'roles': [self.roles[role].marshal() for role in self.roles if self.roles],
            'has_router': self.router is not None,
            'has_service_session': self.session is not None,
        }

        rlinks = []
        for link_id in self.rlink_manager.keys():
            rlinks.append(self.rlink_manager[link_id].marshal())

        marshalled['rlinks'] = rlinks

        return marshalled


class RouterRealmRole(object):

    """
    A role in a realm running in a router worker.
    """

    def __init__(self, id, config):
        """

        :param id: The role ID within the realm.
        :type id: str

        :param config: The role configuration.
        :type config: dict
        """
        self.id = id
        self.config = config

    def marshal(self):
        return {
            'id': self.id,
            'config': self.config,
        }
