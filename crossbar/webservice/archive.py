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
import io
import zipfile
import hashlib

from urllib.parse import urlparse

from collections.abc import Mapping, Sequence

import six
from txaio import make_logger

import treq

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.compat import intToBytes, networkString
from twisted.web import server, resource
from twisted.web.static import http, NoRangeStaticProducer, loadMimeTypes

from crossbar.webservice.base import RouterWebService
from crossbar.common.checkconfig import InvalidConfigException, check_dict_args


def _download(reactor, url, destination_filename):
    destination = open(destination_filename, 'wb')
    d = treq.get(url)
    d.addCallback(treq.collect, destination.write)
    d.addBoth(lambda _: destination.close())
    return d


def _sha256file(filename, block_size=2**20):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as file:
        while True:
            data = file.read(block_size)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


class ZipFileResource(resource.Resource):
    """
    Twisted Web resource for a single file within a ZIP archive.
    """
    log = make_logger()

    isLeaf = True

    def __init__(self, file, size, content_type):
        resource.Resource.__init__(self)
        self.file = file
        self.size = size
        self.type = content_type
        self.encoding = None
        self.log.debug('ZipFileResource(file={file}, size={size}, content_type={content_type})'.format(
            file=file, size=size, content_type=content_type))

    def render_GET(self, request):
        if self.size:
            request.setHeader(b'content-length', intToBytes(self.size))
        if self.type:
            request.setHeader(b'content-type', networkString(self.type))
        if self.encoding:
            request.setHeader(b'content-encoding', networkString(self.encoding))

        request.setResponseCode(http.OK)

        # FIXME: depending on self.size, eg when 128kB, we might want to directly return bytes
        # instead of the overhead setting up a producer etc ..

        # if we want to serve directly out of ZIP files, we cannot support HTTP
        # range requests, as the file-like object returned for a file within an archive
        # does not support seek() (it will raise "not implemented" - 2018/06 with Python 3.6.5)
        producer = NoRangeStaticProducer(request, self.file)
        producer.start()

        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET


class ZipArchiveResource(resource.Resource):
    """
    Twisted Web resource
    """
    log = make_logger()

    contentTypes = loadMimeTypes()

    # FIXME: https://github.com/crossbario/crossbar/issues/633
    contentEncodings = {'.gz': 'gzip', '.bz2': 'bzip2', '.jgz': 'gzip'}

    def __init__(self, worker, config, path, archive_file):
        resource.Resource.__init__(self)
        self._worker = worker
        self._config = config
        self._path = path
        self._archive_file = archive_file
        self._origin = config.get('origin', None)
        self._cache = config.get('cache', False)
        self._default_object = config.get('default_object', None)
        self._object_prefix = config.get('object_prefix', None)
        if 'mime_types' in config:
            self.contentTypes.update(config['mime_types'])

        # now open ZIP archive from local file ..
        if os.path.exists(self._archive_file):
            self._archive = zipfile.ZipFile(self._archive_file)
        else:
            self._archive = None

        # setup map: filename -> cached content (bytes from file)
        if self._archive:
            self._zipfiles = {key: None for key in set(self._archive.namelist())}
        else:
            self._zipfiles = {}

        # setup fallback option
        self._default_file = self._config.get('options', {}).get('default_file')
        if self._default_file:
            self._default_file = self._default_file.encode('utf-8')

        self.log.info('ZipArchiveResource: {zlen} files in ZIP archive', zlen=len(self._zipfiles))
        self.log.debug('ZipArchiveResource files: {filelist}', filelist=sorted(self._zipfiles.keys()))

    def getChild(self, path, request, retry=True):
        self.log.debug(
            'ZipFileResource.getChild(path={path}, request={request}, prepath={prepath}, postpath={postpath})',
            path=path,
            prepath=request.prepath,
            postpath=request.postpath,
            request=request)

        search_path = b'/'.join([path] + request.postpath).decode('utf8')

        if (search_path == '' or search_path.endswith('/')) and self._default_object:
            search_path += self._default_object

        if self._object_prefix:
            search_path = os.path.join(self._object_prefix, search_path)

        self.log.debug('ZipArchiveResource.getChild - effective search path: "{}"'.format(search_path))

        if search_path in self._zipfiles:
            # check cache
            data = self._zipfiles[search_path]

            # get data if not cached
            if not data:
                if self._archive:
                    # open file within ZIP archive
                    data = self._archive.open(search_path).read()
                    if self._cache:
                        self._zipfiles[search_path] = data
                        self.log.debug(
                            'contents for file {search_path} from archive {archive_file} cached in memory',
                            search_path=search_path,
                            archive_file=self._archive_file)
                    else:
                        self.log.debug(
                            'contents for file {search_path} from archive {archive_file} read from file',
                            search_path=search_path,
                            archive_file=self._archive_file)
                else:
                    self.log.debug('cache archive not loaded')
                    return resource.NoResource()
            else:
                self.log.debug(
                    'cache hit: contents for file {search_path} from archive {archive_file} cached in memory',
                    search_path=search_path,
                    archive_file=self._archive_file)
            # file size
            file_size = len(data)
            fd = io.BytesIO(data)

            # guess MIME type from file extension
            _, ext = os.path.splitext(search_path)
            content_type = self.contentTypes.get(ext, None)

            # create and return resource that returns the file contents
            res = ZipFileResource(fd, file_size, content_type)
            return res

        else:
            if self._default_file and retry:
                return self.getChild(self._default_file, request, False)
            else:
                return resource.NoResource()


class RouterWebServiceArchive(RouterWebService):
    """
    Static Web from ZIP archive service.
    """

    @staticmethod
    def check(personality, config):
        """
        Checks the configuration item. When errors are found, an
        InvalidConfigException exception is raised.

        :param personality: The node personality class.
        :param config: The Web service configuration item.

        :raises: crossbar.common.checkconfig.InvalidConfigException
        """
        if 'type' not in config:
            raise InvalidConfigException("missing mandatory attribute 'type' in Web service configuration")

        if config['type'] != 'archive':
            raise InvalidConfigException('unexpected Web service type "{}"'.format(config['type']))

        check_dict_args({
            # ID of webservice (must be unique for the web transport)
            'id': (False, [str]),

            # must be equal to "archive"
            'type': (True, [six.text_type]),

            # local path to archive file (relative to node directory)
            'archive': (True, [six.text_type]),

            # download URL for achive to auto-fetch
            'origin': (False, [six.text_type]),

            # flag to control automatic downloading from origin
            'download': (False, [bool]),

            # cache archive contents in memory
            'cache': (False, [bool]),

            # default filename in archive when fetched URL is "" or "/"
            'default_object': (False, [six.text_type]),

            # archive object prefix: this is prefixed to the path before looking within the archive file
            'object_prefix': (False, [six.text_type]),

            # configure additional MIME types, sending correct HTTP response headers
            'mime_types': (False, [Mapping]),

            # list of SHA3-256 hashes (HEX string) the archive file is to be verified against
            'hashes': (False, [Sequence]),

            # FIXME
            'options': (False, [Mapping]),
        }, config, "Static Web from Archive service configuration".format(config))

    @staticmethod
    @inlineCallbacks
    def create(transport, path, config):
        """
        Factory to create a Web service instance of this class.

        :param transport: The Web transport in which this Web service is created on.
        :param path: The (absolute) URL path on which the Web service is to be attached.
        :param config: The Web service configuration item.

        :return: An instance of this class.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['archive'](personality, config)

        log = transport.worker.log

        archive_file = os.path.abspath(os.path.join(transport.worker.cbdir, config['archive']))
        if os.path.exists(archive_file):
            if os.path.isfile(archive_file):
                log.info(
                    'ZipArchiveResource: file already cached locally [{archive_file}]',
                    archive_file=archive_file)
            else:
                raise Exception(
                    'path "{archive_file}" exists but is not a file'.format(archive_file=archive_file))
        else:
            if 'origin' not in config:
                raise Exception('missing origin')

            _url = urlparse(config['origin'])
            if _url.scheme not in ['http', 'https']:
                raise Exception('invalid scheme "{}" in attribute "archive" for archive file'.format(
                    _url.scheme))

            # download the file and cache locally ..
            if config.get('download', False):
                source_url = _url.geturl()
                log.info('ZipArchiveResource: downloading from "{source_url}"', source_url=source_url)
                yield _download(transport.worker._reactor, source_url, archive_file)

                log.info(
                    'ZipArchiveResource: file downloaded and cached locally [{archive_file}]',
                    archive_file=archive_file)
            else:
                log.warn('ZipArchiveResource: file download skipped by configuration!')

        hashes = config.get('hashes', None)
        if hashes:
            h = _sha256file(archive_file)
            if h in hashes:
                log.info(
                    'ZipArchiveResource: archive file "{archive_file}" verified (fingerprint {hash}..)',
                    archive_file=archive_file,
                    hash=h[:12])
            else:
                raise Exception('archive "{}" does not match any of configured SHA256 fingerprints {}'.format(
                    archive_file, hashes))
        else:
            log.warn(
                'ZipArchiveResource: archive file "{archive_file}" is unverified', archive_file=archive_file)

        res = ZipArchiveResource(transport.worker, config, path, archive_file)
        svc = RouterWebServiceArchive(transport, path, config, res)

        returnValue(svc)
