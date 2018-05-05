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


import os
import time

import pkg_resources
import importlib

from autobahn.wamp import ApplicationError
from twisted.web import http
from twisted.web.static import File

from crossbar.common.twisted.web import patchFileContentTypes
from crossbar.webservice.base import RouterWebService, Resource404, set_cross_origin_headers

DEFAULT_CACHE_TIMEOUT = 12 * 60 * 60

EXTRA_MIME_TYPES = {
    '.svg': 'image/svg+xml',
    '.jgz': 'text/javascript'
}


class StaticResource(File):
    """
    Resource for static assets from file system.
    """

    def __init__(self, *args, **kwargs):
        self._cache_timeout = kwargs.pop('cache_timeout', None)
        self._allow_cross_origin = kwargs.pop('allow_cross_origin', True)
        File.__init__(self, *args, **kwargs)

    def render_GET(self, request):
        if self._cache_timeout is not None:
            request.setHeader(b'cache-control', u'max-age={}, public'.format(self._cache_timeout).encode('utf8'))
            request.setHeader(b'expires', http.datetimeToString(time.time() + self._cache_timeout))

        # set response headers for cross-origin requests
        #
        if self._allow_cross_origin:
            set_cross_origin_headers(request)

        return File.render_GET(self, request)

    def createSimilarFile(self, *args, **kwargs):
        #
        # File.getChild uses File.createSimilarFile to make a new resource of the same class to serve actual files under
        # a directory. We need to override that to also set the cache timeout on the child.
        #

        similar_file = File.createSimilarFile(self, *args, **kwargs)

        # need to manually set this - above explicitly enumerates constructor args
        similar_file._cache_timeout = self._cache_timeout

        return similar_file


class StaticResourceNoListing(StaticResource):
    """
    A file hierarchy resource with directory listing disabled.
    """

    def directoryListing(self):
        return self.childNotFound


class RouterWebServiceStatic(RouterWebService):
    """
    Static file serving Web service.
    """

    @staticmethod
    def create(transport, path, config):

        # get source for file serving (either a directory, or a Python package)
        #
        static_options = config.get('options', {})

        if 'directory' in config:

            static_dir = os.path.abspath(os.path.join(transport.cbdir, config['directory']))

        elif 'package' in config:

            if 'resource' not in config:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "missing resource")

            try:
                importlib.import_module(config['package'])
            except ImportError as e:
                emsg = "Could not import resource {} from package {}: {}".format(config['resource'], config['package'], e)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
            else:
                try:
                    static_dir = os.path.abspath(pkg_resources.resource_filename(config['package'], config['resource']))
                except Exception as e:
                    emsg = "Could not import resource {} from package {}: {}".format(config['resource'], config['package'], e)
                    raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        else:

            raise ApplicationError(u"crossbar.error.invalid_configuration", "missing web spec")

        static_dir = static_dir.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770

        # create resource for file system hierarchy
        #
        if static_options.get('enable_directory_listing', False):
            static_resource_class = StaticResource
        else:
            static_resource_class = StaticResourceNoListing

        cache_timeout = static_options.get('cache_timeout', DEFAULT_CACHE_TIMEOUT)
        allow_cross_origin = static_options.get('allow_cross_origin', True)

        resource = static_resource_class(static_dir, cache_timeout=cache_timeout, allow_cross_origin=allow_cross_origin)

        # set extra MIME types
        #
        resource.contentTypes.update(EXTRA_MIME_TYPES)
        if 'mime_types' in static_options:
            resource.contentTypes.update(static_options['mime_types'])
        patchFileContentTypes(resource)

        # render 404 page on any concrete path not found
        #
        resource.childNotFound = Resource404(transport.templates, static_dir)

        return RouterWebServiceStatic(transport, path, config, resource)
