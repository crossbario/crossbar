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

import sys
import importlib

from twisted.python.threadpool import ThreadPool
from twisted.web.wsgi import WSGIResource

from autobahn.wamp import ApplicationError
from autobahn.twisted.resource import WSGIRootResource

from crossbar.webservice.base import RouterWebService


class RouterWebServiceWsgi(RouterWebService):
    """
    WSGI application Web service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['wsgi'](personality, config)
        reactor = transport.worker.components_shared['reactor']

        if 'module' not in config:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'missing WSGI app module')

        if 'object' not in config:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'missing WSGI app object')

        # import WSGI app module and object
        mod_name = config['module']
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as e:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'WSGI app module "{}" import failed: {} - Python search path was {}'.format(mod_name, e, sys.path))

        obj_name = config['object']
        if obj_name not in mod.__dict__:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'WSGI app object "{}" not in module "{}"'.format(obj_name, mod_name))
        else:
            app = getattr(mod, obj_name)

        # Create a thread-pool for running the WSGI requests in
        pool = ThreadPool(maxthreads=config.get('maxthreads', 20),
                          minthreads=config.get('minthreads', 0),
                          name='crossbar_wsgi_threadpool')
        reactor.addSystemEventTrigger('before', 'shutdown', pool.stop)
        pool.start()

        # Create a Twisted Web WSGI resource from the user's WSGI application object
        try:
            resource = WSGIResource(reactor, pool, app)
            if path == '/':
                resource = WSGIRootResource(resource, {})
        except Exception as e:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'could not instantiate WSGI resource: {}'.format(e))
        else:
            return RouterWebServiceWsgi(transport, path, config, resource)
