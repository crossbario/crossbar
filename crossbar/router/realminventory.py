#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import re
import os.path
import zipfile
from urllib.parse import urlparse
from collections.abc import Sequence

import yaml

from txaio import use_twisted  # noqa
from txaio import make_logger

from autobahn.util import hltype
from autobahn.xbr import FbsRepository

from crossbar.common.checkconfig import check_dict_args
from crossbar.interfaces import IRealmInventory

__all__ = ('RealmInventory', )


class Catalog(object):
    """
    """
    __slots__ = (
        '_name',
        '_version',
        '_title',
        '_description',
        '_schemas',
        '_author',
        '_publisher',
        '_license',
        '_keywords',
        '_homepage',
        '_git',
        '_theme',
    )

    def __init__(self):
        self._name = ''

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def from_address(address) -> 'Catalog':
        """

        :param address:
        :return:
        """
        catalog = Catalog()
        return catalog

    @staticmethod
    def from_archive(filename) -> 'Catalog':
        """

        :param filename:
        :return:
        """
        if not os.path.isfile(filename):
            raise RuntimeError('cannot open catalog from archive "{}" - not a file'.format(filename))
        f = zipfile.ZipFile(filename)
        if 'catalog.yaml' not in f.namelist():
            raise RuntimeError('archive does not seem to be a catalog - missing catalog.yaml')
        data = f.open('catalog.yaml').read()
        obj = yaml.safe_load(data)

        # {'author': 'typedef int GmbH',
        #  'description': 'Write me.',
        #  'git': 'https://github.com/wamp-proto/wamp-proto.git',
        #  'homepage': 'https://wamp-proto.org/',
        #  'keywords': 'trading, defi, analytics',
        #  'license': 'MIT',
        #  'name': 'pydefi-trading',
        #  'publisher': 552618803359027592947966730519406091095802297127,
        #  'schemas': ['schema/trading.bfbs', 'schema/demo.bfbs'],
        #  'theme': {'background': '#333333',
        #            'highlight': '#00ccff',
        #            'logo': 'img/logo.png',
        #            'text': '#e0e0e0'},
        #  'title': 'PyDeFi Trading API Catalog',
        #  'version': '22.6.1'}

        check_dict_args(
            {
                'name': (True, [str]),
                'version': (False, [str]),
                'title': (False, [str]),
                'description': (False, [str]),
                'schemas': (True, [Sequence]),
                'author': (False, [str]),
                'publisher': (False, [str]),

                # SPDX license ID (https://spdx.org/licenses/)
                'license': (True, [str]),
                'keywords': (False, [Sequence]),
                'homepage': (False, [str]),
                'git': (False, [str]),
                'theme': (False, [str]),
            },
            obj,
            "WAMP API Catalog {} invalid".format(filename))

        # FIXME: check SPDX license ID vs
        #  https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json
        if 'license' in obj:
            pass

        if 'keywords' in obj:
            kw_pat = re.compile(r'^[a-z]{3,20}$')
            for kw in obj['keywords']:
                assert type(kw) == str, 'invalid type {} for keyword'.format(type(kw))
                assert kw_pat.match(kw) is not None, 'invalid keyword "{}"'.format(kw)

        if 'schemas' in obj:
            for schema_path in obj['schemas']:
                assert type(schema_path) == str, 'invalid type {} for schema path'.format(type(schema_path))
                assert schema_path in f.namelist(), 'cannot find schema path "{}" in catalog archive'.format(
                    schema_path)

        if 'homepage' in obj:
            homepage = obj['homepage']
            assert type(homepage) == str, 'invalid type {} for homepage'.format(type(homepage))
            try:
                urlparse(homepage)
            except Exception as e:
                raise RuntimeError('invalid HTTP(S) URL "{}" for homepage ({})'.format(homepage, e))

        if 'git' in obj:
            git = obj['git']
            assert type(git) == str, 'invalid type {} for git'.format(type(git))
            try:
                urlparse(git)
            except Exception as e:
                raise RuntimeError('invalid HTTP(S) URL "{}" for git ({})'.format(git, e))

        if 'theme' in obj:
            theme = obj['theme']
            assert type(theme) == dict
            for k in theme:
                if k not in ['background', 'highlight', 'text', 'logo']:
                    raise RuntimeError('invalid theme attribute "{}"'.format(k))
                if type(theme[k]) != str:
                    raise RuntimeError('invalid type{} for attribute {} in theme'.format(type(obj[k]), k))
            if 'logo' in theme:
                logo_path = theme['logo']
                assert logo_path in f.namelist(), 'cannot find theme logo path "{}" in catalog archive'.format(
                    logo_path)

            # FIXME: check other attributes

        if 'publisher' in obj:
            # FIXME: check address
            pass

        catalog = Catalog()
        return catalog


class RealmInventory(IRealmInventory):
    """
    Memory-backed realm inventory.
    """
    INVENTORY_TYPE = 'wamp.eth'

    log = make_logger()

    def __init__(self, personality, factory, config):
        from twisted.internet import reactor

        self._reactor = reactor
        self._personality = personality
        self._factory = factory
        self._config = config

        self._type = self._config.get('type', None)
        assert self._type == self.INVENTORY_TYPE

        # FIXME
        self._basemodule = ''
        self._repo = FbsRepository(basemodule=self._basemodule)

        self._catalogs = {}

        self._running = False

        self.log.debug('{func} realm inventory initialized', func=hltype(self.__init__))

    @property
    def type(self) -> str:
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.type`
        """
        return self._type

    @property
    def repo(self) -> FbsRepository:
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.type`
        """
        return self._repo

    @property
    def is_running(self) -> bool:
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.is_running`
        """
        return self._running

    def start(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.start`
        """
        if self._running:
            raise RuntimeError('inventory is already running')
        else:
            self.log.info('{func} starting realm inventory', func=hltype(self.start))

        self._running = True
        self.log.info('{func} realm inventory ready!', func=hltype(self.start))

    def stop(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.stop`
        """
        if not self._running:
            raise RuntimeError('inventory is not running')
        else:
            self.log.info('{func} stopping realm inventory', func=hltype(self.start))

        self._running = False

    def load(self, filename: str) -> int:
        self._repo.load(filename)
        return len(self._repo.objs) + len(self._repo.enums) + len(self._repo.services)

    @staticmethod
    def from_catalogs(self, personality, factory, config):
        assert 'type' in config and config['type'] == 'wamp.eth'
        assert 'catalogs' in config and type(config['catalogs']) == list

        inventory = RealmInventory(personality, factory, config)
        for catalog_config in config['catalogs']:
            if 'filename' in catalog_config:
                filename = catalog_config['filename']
                inventory.load(filename)
            elif 'archive' in catalog_config:
                catalog = Catalog.from_archive(catalog_config['archive'])
                self._catalogs[catalog.name] = catalog
        return inventory
