#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import sys
import importlib

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from twisted.python.failure import Failure

from txaio import make_logger

#
# the imports here are important (though not used in CB unless configured),
# because of single-exe packaging and pyinstaller otherwise missing deps
#

from crossbar.worker.sample import LogTester  # noqa


def _appsession_loader(config):
    """
    Load a class from C{config}.
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
                raise ApplicationError("crossbar.error.class_import_failed",
                                       "session not derived of ApplicationSession")

        except Exception:
            emsg = "Failed to import class '{}'\n{}".format(klassname, Failure().getTraceback())
            log.debug(emsg)
            log.debug("PYTHONPATH: {pythonpath}", pythonpath=sys.path)
            raise ApplicationError("crossbar.error.class_import_failed", emsg, pythonpath=sys.path)

    elif config['type'] == 'function':
        callbacks = {}
        for name, funcref in config.get('callbacks', {}).items():
            if '.' not in funcref:
                raise ApplicationError(
                    "crossbar.error",
                    "no '.' in callback reference '{}'".format(funcref),
                )

            try:
                package, func = funcref.rsplit('.', 1)

                module = importlib.import_module(package)
                callbacks[name] = getattr(module, func)

            except Exception:
                emsg = "Failed to import package '{}' (for '{}')\n{}".format(package, funcref,
                                                                             Failure().getTraceback())
                log.error('{msg}', msg=emsg)
                raise ApplicationError("crossbar.error.class_import_failed", emsg)

        # while the "component" callback is usually an
        # ApplicationSession class, it can be anything that takes a
        # "config" arg (must return an ApplicationSession instance)
        def component(cfg):
            session = _AnonymousRoleSession(cfg)
            session.role = config.get('role', 'anonymous')
            for name, fn in callbacks.items():
                session.on(name, fn)
            return session

    else:
        raise ApplicationError("crossbar.error.invalid_configuration",
                               "invalid component type '{}'".format(config['type']))

    return component


class _AnonymousRoleSession(ApplicationSession):

    role = None

    def onConnect(self):
        self.join(self.config.realm, authrole=self.role)
