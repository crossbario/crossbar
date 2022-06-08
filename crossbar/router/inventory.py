#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import re
from random import randint
import os.path
import zipfile
from urllib.parse import urlparse
from collections.abc import Sequence, Mapping
from typing import Optional, Dict, List

import yaml

from txaio import use_twisted  # noqa
from txaio import make_logger

from autobahn.util import hltype
from autobahn.xbr import FbsRepository, FbsSchema

from crossbar.common.checkconfig import check_dict_args
from crossbar.interfaces import IInventory

__all__ = ('Inventory', )


class Catalog(object):
    """
    WAMP API Catalog, which can be created from:
    - Schema file
    - Archive file
    - On-chain address
    """
    CATALOG_TYPE_NONE = 0
    """
    No Catalog type.
    """

    CATALOG_TYPE_BFBS = 1
    """
    Catalog from a single binary FlatBuffers (``*.bfbs``) file.
    """

    CATALOG_TYPE_ARCHIVE = 2
    """
    Catalog from a Catalog ZIP archive (``*.zip``) file.
    """

    CATALOG_TYPE_ADDRESS = 3
    """
    Catalog addressed from an Ethereum address stored on-chain in WAMP contracts.
    """

    __slots__ = (
        '_inventory',
        '_ctype',
        '_name',
        '_bfbs',
        '_archive',
        '_address',
        '_version',
        '_title',
        '_description',
        '_schemas',
        '_author',
        '_publisher',
        '_clicense',
        '_keywords',
        '_homepage',
        '_giturl',
        '_theme',
    )

    def __init__(
        self,
        inventory: 'Inventory',
        ctype: int,
        name: str,
        bfbs: Optional[str] = None,
        archive: Optional[str] = None,
        address: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        schemas: Optional[Dict[str, FbsSchema]] = None,
        author: Optional[str] = None,
        publisher: Optional[str] = None,
        clicense: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        homepage: Optional[str] = None,
        giturl: Optional[str] = None,
        theme: Optional[Dict[str, str]] = None,
    ):
        """

        :param inventory:
        :param ctype:
        :param name:
        :param bfbs:
        :param archive:
        :param address:
        :param version:
        :param title:
        :param description:
        :param schemas:
        :param author:
        :param publisher:
        :param clicense:
        :param keywords:
        :param homepage:
        :param giturl:
        :param theme:
        """
        self._inventory = inventory

        assert ctype in [Catalog.CATALOG_TYPE_BFBS, Catalog.CATALOG_TYPE_ARCHIVE, Catalog.CATALOG_TYPE_ADDRESS]
        self._ctype = ctype
        self._name = name

        # only one of the following must be provided for a given ctype
        assert (ctype == Catalog.CATALOG_TYPE_BFBS and bfbs and not archive and not address) or \
               (ctype == Catalog.CATALOG_TYPE_ARCHIVE and not bfbs and archive and not address) or \
               (ctype == Catalog.CATALOG_TYPE_ADDRESS and not bfbs and not archive and address)
        self._bfbs = bfbs
        self._archive = archive
        self._address = address

        # map of schemas
        self._schemas = schemas or {}

        # catalog metadata
        self._version = version
        self._title = title
        self._description = description
        self._author = author
        self._publisher = publisher
        self._clicense = clicense
        self._keywords = keywords
        self._homepage = homepage
        self._giturl = giturl
        self._theme = theme

    def __len__(self) -> int:
        return len(self._schemas)

    def __getitem__(self, name: str) -> FbsSchema:
        return self._schemas[name]

    def __iter__(self):
        return iter(self._schemas)

    @property
    def inventory(self) -> 'Inventory':
        return self._inventory

    @property
    def ctype(self) -> int:
        return self._ctype

    @property
    def name(self) -> str:
        return self._name

    @property
    def bfbs(self) -> Optional[str]:
        return self._bfbs

    @property
    def archive(self) -> Optional[str]:
        return self._archive

    @property
    def address(self) -> Optional[str]:
        return self._address

    @property
    def version(self) -> Optional[str]:
        return self._version

    @property
    def title(self) -> Optional[str]:
        return self._title

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def author(self) -> Optional[str]:
        return self._author

    @property
    def publisher(self) -> Optional[str]:
        return self._publisher

    @property
    def clicense(self) -> Optional[str]:
        return self._clicense

    @property
    def keywords(self) -> Optional[List[str]]:
        return self._keywords

    @property
    def homepage(self) -> Optional[str]:
        return self._homepage

    @property
    def giturl(self) -> Optional[str]:
        return self._giturl

    @property
    def theme(self) -> Optional[Dict[str, str]]:
        return self._theme

    @staticmethod
    def from_bfbs(inventory: 'Inventory', name: str, filename: str) -> 'Catalog':
        """

        :param inventory:
        :param name:
        :param filename:
        :return:
        """
        if not os.path.isfile(filename):
            raise RuntimeError('cannot open catalog from bfbs file "{}" - not a file'.format(filename))
        catalog = Catalog(inventory=inventory, ctype=Catalog.CATALOG_TYPE_BFBS, name=name, bfbs=filename)
        return catalog

    @staticmethod
    def from_archive(inventory: 'Inventory', filename: str) -> 'Catalog':
        """

        :param inventory:
        :param filename:
        :return:
        """
        if not os.path.isfile(filename):
            raise RuntimeError('cannot open catalog from archive "{}" - path is not a file'.format(filename))
        if not zipfile.is_zipfile(filename):
            raise RuntimeError('cannot open catalog from archive "{}" - file is not a ZIP file'.format(filename))

        f = zipfile.ZipFile(filename)

        if f.testzip() is not None:
            raise RuntimeError('cannot open catalog from archive "{}" - ZIP file is corrupt'.format(filename))

        if 'catalog.yaml' not in f.namelist():
            raise RuntimeError('archive does not seem to be a catalog - missing catalog.yaml catalog index')

        # open, read and parse catalog metadata file
        data = f.open('catalog.yaml').read()
        obj = yaml.safe_load(data)

        # check metadata object
        check_dict_args(
            {
                # mandatory:
                'name': (True, [str]),
                'schemas': (True, [Sequence]),
                # optional:
                'version': (False, [str]),
                'title': (False, [str]),
                'description': (False, [str]),
                'author': (False, [str]),
                'publisher': (False, [str]),
                'license': (False, [str]),
                'keywords': (False, [Sequence]),
                'homepage': (False, [str]),
                'git': (False, [str]),
                'theme': (False, [Mapping]),
            },
            obj,
            "WAMP API Catalog {} invalid".format(filename))

        schemas = {}
        if 'schemas' in obj:
            enum_dups = 0
            obj_dups = 0
            svc_dups = 0

            for schema_path in obj['schemas']:
                assert type(schema_path) == str, 'invalid type {} for schema path'.format(type(schema_path))
                assert schema_path in f.namelist(), 'cannot find schema path "{}" in catalog archive'.format(
                    schema_path)
                with f.open(schema_path) as fd:
                    # load FlatBuffers schema object
                    _schema: FbsSchema = FbsSchema.load(inventory.repo, fd, schema_path)

                    # add enum types to repository by name
                    for _enum in _schema.enums.values():
                        if _enum.name in inventory.repo._enums:
                            # print('skipping duplicate enum type for name "{}"'.format(_enum.name))
                            enum_dups += 1
                        else:
                            inventory.repo._enums[_enum.name] = _enum

                    # add object types to repository by name
                    for _obj in _schema.objs.values():
                        if _obj.name in inventory.repo._objs:
                            # print('skipping duplicate object (table/struct) type for name "{}"'.format(_obj.name))
                            obj_dups += 1
                        else:
                            inventory.repo._objs[_obj.name] = _obj

                    # add service definitions ("APIs") to repository by name
                    for _svc in _schema.services.values():
                        if _svc.name in inventory.repo._services:
                            # print('skipping duplicate service type for name "{}"'.format(_svc.name))
                            svc_dups += 1
                        else:
                            inventory.repo._services[_svc.name] = _svc

                    # remember schema object by schema path
                    schemas[schema_path] = _schema

        clicense = None
        if 'clicense' in obj:
            # FIXME: check SPDX license ID vs
            #  https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json
            clicense = obj['clicense']

        keywords = None
        if 'keywords' in obj:
            kw_pat = re.compile(r'^[a-z]{3,20}$')
            for kw in obj['keywords']:
                assert type(kw) == str, 'invalid type {} for keyword'.format(type(kw))
                assert kw_pat.match(kw) is not None, 'invalid keyword "{}"'.format(kw)
            keywords = obj['keywords']

        homepage = None
        if 'homepage' in obj:
            assert type(obj['homepage']) == str, 'invalid type {} for homepage'.format(type(obj['homepage']))
            try:
                urlparse(obj['homepage'])
            except Exception as e:
                raise RuntimeError('invalid HTTP(S) URL "{}" for homepage ({})'.format(obj['homepage'], e))
            homepage = obj['homepage']

        giturl = None
        if 'giturl' in obj:
            assert type(obj['git']) == str, 'invalid type {} for giturl'.format(type(obj['giturl']))
            try:
                urlparse(obj['giturl'])
            except Exception as e:
                raise RuntimeError('invalid HTTP(S) URL "{}" for giturl ({})'.format(obj['giturl'], e))
            giturl = obj['giturl']

        theme = None
        if 'theme' in obj:
            assert isinstance(obj['theme'], Mapping)
            for k in obj['theme']:
                if k not in ['background', 'highlight', 'text', 'logo']:
                    raise RuntimeError('invalid theme attribute "{}"'.format(k))
                if type(obj['theme'][k]) != str:
                    raise RuntimeError('invalid type{} for attribute {} in theme'.format(type(obj['theme'][k]), k))
            if 'logo' in obj['theme']:
                logo_path = obj['theme']['logo']
                assert logo_path in f.namelist(), 'cannot find theme logo path "{}" in catalog archive'.format(
                    logo_path)
            theme = dict(obj['theme'])
            # FIXME: check other theme attributes

        publisher = None
        if 'publisher' in obj:
            # FIXME: check publisher address
            publisher = obj['publisher']

        catalog = Catalog(inventory=inventory,
                          ctype=Catalog.CATALOG_TYPE_ARCHIVE,
                          name=obj['name'],
                          archive=filename,
                          version=obj.get('version', None),
                          title=obj.get('title', None),
                          description=obj.get('description', None),
                          schemas=schemas,
                          author=obj.get('author', None),
                          publisher=publisher,
                          clicense=clicense,
                          keywords=keywords,
                          homepage=homepage,
                          giturl=giturl,
                          theme=theme)
        return catalog

    @staticmethod
    def from_address(inventory: 'Inventory', address) -> 'Catalog':
        """

        :param inventory:
        :param address:
        :return:
        """
        catalog = Catalog(inventory=inventory,
                          ctype=Catalog.CATALOG_TYPE_ADDRESS,
                          name='fixme{}'.format(randint(1, 2**31)),
                          address=address)
        return catalog


class Inventory(IInventory):
    """
    Memory-backed realm inventory.
    """
    INVENTORY_TYPE = 'wamp.eth'

    log = make_logger()

    def __init__(self, personality, factory, catalogs: Optional[Dict[str, Catalog]] = None):
        """

        :param personality:
        :param factory:
        :param catalogs:
        """
        from twisted.internet import reactor

        self._reactor = reactor
        self._personality = personality
        self._factory = factory
        self._catalogs: Dict[str, Catalog] = catalogs or {}

        # inventories need to be start()'ed
        self._running = False

        # FIXME
        self._basemodule = ''

        # the consolidated schema repository with all schemas from catalogs
        self._repo = FbsRepository(basemodule=self._basemodule)

    def __len__(self) -> int:
        """

        :return:
        """
        return len(self._catalogs)

    def __getitem__(self, name: str) -> Catalog:
        """

        :param name:
        :return:
        """
        return self._catalogs[name]

    def __iter__(self):
        """

        :return:
        """
        return iter(self._catalogs)

    def add_catalog(self, catalog: Catalog):
        """

        :param catalog:
        :return:
        """
        assert catalog.name not in self._catalogs
        self._catalogs[catalog.name] = catalog
        if catalog.ctype == Catalog.CATALOG_TYPE_BFBS:
            self._repo.load(catalog.bfbs)

    @property
    def type(self) -> str:
        """
        Implements :meth:`crossbar._interfaces.IInventory.type`
        """
        return self.INVENTORY_TYPE

    def catalog(self, name: str):
        return self._catalogs.get(name, None)

    @property
    def repo(self) -> FbsRepository:
        """
        Implements :meth:`crossbar._interfaces.IInventory.type`
        """
        return self._repo

    @property
    def is_running(self) -> bool:
        """
        Implements :meth:`crossbar._interfaces.IInventory.is_running`
        """
        return self._running

    def start(self):
        """
        Implements :meth:`crossbar._interfaces.IInventory.start`
        """
        if self._running:
            raise RuntimeError('inventory is already running')
        else:
            self.log.info('{func} starting realm inventory', func=hltype(self.start))

        self._running = True
        self.log.info('{func} realm inventory ready!', func=hltype(self.start))

    def stop(self):
        """
        Implements :meth:`crossbar._interfaces.IInventory.stop`
        """
        if not self._running:
            raise RuntimeError('inventory is not running')
        else:
            self.log.info('{func} stopping realm inventory', func=hltype(self.start))

        self._running = False

    def load(self, name: str, filename: str) -> int:
        """

        :param name:
        :param filename:
        :return:
        """
        assert name not in self._catalogs
        self._repo.load(filename)
        self._catalogs[name] = Catalog(inventory=self, ctype=Catalog.CATALOG_TYPE_BFBS, name=name, bfbs=filename)
        return len(self._repo.objs) + len(self._repo.enums) + len(self._repo.services)

    @staticmethod
    def from_config(personality, factory, config):
        """

        :param personality:
        :param factory:
        :param config:
        :return:
        """
        assert 'type' in config and config['type'] == Inventory.INVENTORY_TYPE
        assert 'catalogs' in config and type(config['catalogs']) == list

        inventory = Inventory(personality, factory)
        catalogs = {}
        for idx, catalog_config in enumerate(config['catalogs']):
            if 'bfbs' in catalog_config:
                catalog = Catalog.from_bfbs(inventory=inventory,
                                            name=catalog_config.get('name', 'catalog{}'.format(idx)),
                                            filename=catalog_config['bfbs'])
            elif 'archive' in catalog_config:
                catalog = Catalog.from_archive(inventory=inventory, filename=catalog_config['archive'])
            elif 'address' in catalog_config:
                catalog = Catalog.from_address(inventory=inventory, address=catalog_config['address'])
            else:
                assert False, 'neither "bfbs", "archive" nor "address" field in catalog config'
            catalogs[catalog.name] = catalog

        inventory._catalogs = catalogs
        return inventory
