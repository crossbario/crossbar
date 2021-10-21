###############################################################################
#
# Crossbar.io FX Master
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

import time
from typing import Dict
from collections.abc import Mapping
from pprint import pformat

import txaio

from crossbar.common import checkconfig
from crossbar.node.node import NodeOptions

from crossbar.personality import Personality as CrossbarPersonality
from crossbar.edge.personality import Personality as CrossbarFabricPersonality

import crossbar
from crossbar.master.node.node import FabricCenterNode

from crossbar.master.webservice import RouterWebServiceRegisterMe


def check_controller_fabric_center(personality, config):
    if not isinstance(config, Mapping):
        raise checkconfig.InvalidConfigException(
            "'fabric-center' in controller configuration must be a dictionary ({} encountered)\n\n".format(
                type(config)))

    for k in config:
        if k not in ['metering', 'auto_default_mrealm']:
            raise checkconfig.InvalidConfigException(
                "encountered unknown attribute '{}' in 'fabric-center' in controller configuration".format(k))

    if 'auto_default_mrealm' in config:
        auto_default_mrealm = config['auto_default_mrealm']
        checkconfig.check_dict_args(
            {
                'enabled': (False, [bool]),
                'watch_to_pair': (False, [str]),
                'watch_to_pair_pattern': (False, [str]),
                'write_pairing_file': (False, [bool]),
            }, auto_default_mrealm, "auto_default_mrealm configuration: {}".format(pformat(auto_default_mrealm)))

    if 'metering' in config:
        # "metering": {
        #     "period": 60,
        #     "submit": {
        #         "period": 120,
        #         "url": "http://localhost:7000",
        #         "timeout": 5,
        #         "maxerrors": 10
        #     }
        # }
        #
        # also possible to read the URL from an env var:
        #
        # "url": "${crossbar_METERING_URL}"
        #
        metering = config['metering']
        checkconfig.check_dict_args({
            'period': (False, [int, float]),
            'submit': (False, [Mapping]),
        }, metering, "metering configuration: {}".format(pformat(metering)))

        if 'submit' in metering:
            checkconfig.check_dict_args(
                {
                    'period': (False, [int, float]),
                    'url': (False, [str]),
                    'timeout': (False, [int, float]),
                    'maxerrors': (False, [int]),
                }, metering['submit'], "metering submit configuration: {}".format(pformat(metering['submit'])))

            if 'url' in metering['submit']:
                # allow to set value from environment variable
                metering['submit']['url'] = checkconfig.maybe_from_env('metering.submit.url',
                                                                       metering['submit']['url'])


def check_controller(personality, controller, ignore=[]):
    res = checkconfig.check_controller(personality, controller, ['fabric-center', 'enable_docker'] + ignore)

    if 'fabric-center' in controller:
        check_controller_fabric_center(personality, controller['fabric-center'])

    return res


def check_controller_options(personality, options, ignore=[]):
    return checkconfig.check_controller_options(personality, options, ignore)


_TITLE = "Crossbar.io FX"

# sudo apt install figlet && figlet -f smslant "Crossbar FX"
_BANNER = r"""
    :::::::::::::::::
          :::::          _____                 __              _____  __
    :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/
    :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  <
    :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|
          :::::
    :::::::::::::::::   {title} v{version} [{build}]

    Copyright (c) 2013-{year} Crossbar.io Technologies GmbH. All rights reserved.
"""

_DESC = """Crossbar.io FX - decentralized data-plane."""


class Personality(CrossbarFabricPersonality):

    log = txaio.make_logger()

    NAME = 'master'

    TITLE = _TITLE

    DESC = _DESC

    BANNER = _BANNER.format(title=_TITLE,
                            version=crossbar.__version__,
                            build=crossbar.__build__,
                            year=time.strftime('%Y'))

    LEGAL = ('crossbar', 'LEGAL')
    LICENSE = ('crossbar', 'LICENSE')
    LICENSES_OSS = ('crossbar', 'LICENSES-OSS')

    TEMPLATE_DIRS = [('crossbar', 'master/webservice/templates')] + CrossbarFabricPersonality.TEMPLATE_DIRS

    WEB_SERVICE_CHECKERS: Dict[str, object] = {
        'registerme': RouterWebServiceRegisterMe.check,
        **CrossbarPersonality.WEB_SERVICE_CHECKERS
    }

    WEB_SERVICE_FACTORIES: Dict[str, object] = {
        'registerme': RouterWebServiceRegisterMe,
        **CrossbarPersonality.WEB_SERVICE_FACTORIES
    }

    check_controller = check_controller
    check_controller_options = check_controller_options

    Node = FabricCenterNode
    NodeOptions = NodeOptions
