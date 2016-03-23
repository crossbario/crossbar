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

import sys
import importlib
import pkg_resources

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from twisted.python.failure import Failure

from txaio import make_logger


def _appsession_loader(config):
    """
    Load a class or a WAMPlet from C{config}.
    """
    log = make_logger()

    if config['type'] == 'class':

        try:
            klassname = config['classname']

            log.debug("Starting class '{klass}'", klass=klassname)

            c = klassname.split('.')
            module_name, klass_name = '.'.join(c[:-1]), c[-1]
            module = importlib.import_module(module_name)
            component = getattr(module, klass_name)

            if not issubclass(component, ApplicationSession):
                raise ApplicationError(
                    u"crossbar.error.class_import_failed", "session not derived of ApplicationSession"
                )

        except Exception:
            emsg = "Failed to import class '{}'\n{}".format(
                klassname, Failure().getTraceback())
            log.debug(emsg)
            log.debug("PYTHONPATH: {pythonpath}", pythonpath=sys.path)
            raise ApplicationError(
                u"crossbar.error.class_import_failed",
                emsg,
                pythonpath=sys.path
            )

    elif config['type'] == 'wamplet':

        try:
            dist = config['package']
            name = config['entrypoint']

            log.debug("Starting WAMPlet '{}/{}'".format(dist, name))

            # component is supposed to make instances of ApplicationSession
            component = pkg_resources.load_entry_point(
                dist, 'autobahn.twisted.wamplet', name)

        except Exception:
            emsg = "Failed to import wamplet '{}/{}'\n{}".format(
                dist, name, Failure().getTraceback())
            log.error(emsg)
            raise ApplicationError(u"crossbar.error.class_import_failed", emsg)

    else:
        raise ApplicationError(
            u"crossbar.error.invalid_configuration",
            "invalid component type '{}'".format(config['type'])
        )

    return component
