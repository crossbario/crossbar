###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import txaio

txaio.use_twisted()  # noqa

import unittest
import crossbar.edge.node.docker as docker
from crossbar.edge.node.tests.dockerinspect import my_json
from unittest import mock

dummy_scandir = mock.MagicMock()
files_result = {'dirs': ['folder1', 'folder2'], 'files': ['dick', 'harry', 'tom']}
read_data = 'this is my data'
write_data = 'this is write data'


class DirEntry:
    def __init__(self, name, isFile):
        self._name = name
        self._isFile = isFile

    @property
    def name(self):
        return self._name

    def is_dir(self):
        return not self._isFile

    def is_file(self):
        return self._isFile


class TestDocker(unittest.TestCase):
    def setUp(self):

        # with open('tests/docker-inspect.json') as io:
        #     my_json = json.loads(io.read())

        class Attrs():
            attrs = my_json

        class MyEnv:
            containers = {0: Attrs()}

        def from_env():
            return MyEnv()

        self.client = docker.DockerClient(None, None)
        self.client._docker = mock.Mock()
        self.client._docker.from_env = from_env

        global dummy_scandir
        dummy_scandir().__enter__().__iter__.return_value = iter([
            DirEntry('tom', True),
            DirEntry('dick', True),
            DirEntry('harry', True),
            DirEntry('folder1', False),
            DirEntry('folder2', False),
        ])

    def test_fs_root(self):
        #
        #   We may only open files that are contained within volumes and as such are
        #   listed in 'Mounts'. By default these will be specifc RW volumes, OR, stuff
        #   we've configured to be editable using the env variable supplied in the UI.
        #
        assert self.client.fs_root(0, '/app/hello') == '/var/lib/docker/root/hello'
        assert self.client.fs_root(0, '/app/there') == '/var/lib/docker/root/there'
        #
        #   Access outside of a bind or mount point will throw an error
        #
        with self.assertRaises(Exception):
            self.client.fs_root(0, '/appx/crap')
        assert self.client.fs_root(0, '/home/hello') == '/var/lib/docker/home/hello'
        assert self.client.fs_root(0, '/home/there') == '/var/lib/docker/home/there'
        with self.assertRaises(Exception):
            self.client.fs_root(0, '/homex/crap')

    @mock.patch('os.scandir', dummy_scandir)
    def test_fs_open_app(self):
        #
        #   Check mount # 1
        #
        result = self.client.fs_open(0, '/app/myfiles')
        assert result == files_result

    @mock.patch('os.scandir', dummy_scandir)
    def test_fs_open_root(self):
        result = self.client.fs_open(0, '/')
        assert result == {'files': [], 'dirs': ['/app', '/home']}
        result = self.client.fs_open(0, '')
        assert result == {'files': [], 'dirs': ['/app', '/home']}

    @mock.patch('os.scandir', dummy_scandir)
    def test_fs_open_home(self):
        #
        #   Check mount # 2
        #
        result = self.client.fs_open(0, '/home/myfiles')
        assert result == files_result

    def test_fs_get_fail(self):
        raise unittest.SkipTest('FIXME: Fails on matterhorn, probably permissions issue.')
        with self.assertRaises(FileNotFoundError):
            self.client.fs_open(0, '/home/myfile')

    @mock.patch("builtins.open", mock.mock_open(read_data=read_data))
    def test_fs_get_ok(self):
        result = self.client.fs_get(0, '/home/myfile')
        assert result['data'] == read_data

    def test_fs_put_ok(self):
        with mock.patch("builtins.open", mock.mock_open()) as m:
            self.client.fs_put(0, '/home/myfile', write_data)
            m.assert_called_with('/var/lib/docker/home/myfile', 'w')
            m().write.assert_called_with(write_data)
