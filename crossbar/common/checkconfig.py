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

from __future__ import absolute_import

import os
import json
import re
import yaml

from pprint import pformat

from pygments import highlight, lexers, formatters

import txaio
txaio.use_twisted()

from autobahn.websocket.util import parse_url
from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY
from autobahn.wamp.message import _URI_PAT_STRICT_LAST_EMPTY
from autobahn.wamp.uri import convert_starred_uri

from yaml import Loader, SafeLoader, Dumper, SafeDumper
from yaml.constructor import ConstructorError

from collections import OrderedDict
from collections.abc import Mapping, Sequence, Hashable

__all__ = ('check_config',
           'check_config_file',
           'convert_config_file',
           'check_guest')


LATEST_CONFIG_VERSION = 2
"""
The current configuration file version.
"""

NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED = u'shutdown_on_shutdown_requested'
"""
Shutdown the node when explicitly asked to (by calling the management
procedure 'crossbar.node.<node_id>.shutdown'). This is the default when running
in "managed mode".
"""

NODE_SHUTDOWN_ON_WORKER_EXIT = u'shutdown_on_worker_exit'
"""
Shutdown the node whenever a worker exits with success or error. This is the default
when running in "standalone mode".
"""

NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR = u'shutdown_on_worker_exit_with_error'
"""
Shutdown the node whenever a worker exits with error.
"""

NODE_SHUTDOWN_ON_LAST_WORKER_EXIT = u'shutdown_on_last_worker_exit'
"""
Shutdown the node whenever there are no more workers running.
"""

NODE_SHUTDOWN_MODES = (
    NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED,
    NODE_SHUTDOWN_ON_WORKER_EXIT,
    NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR,
    NODE_SHUTDOWN_ON_LAST_WORKER_EXIT,
)
"""
Permissible node shutdown modes.
"""


_WEB_PATH_PAT_STR = r'^([a-z0-9A-Z_\-]+|/)$'
_WEB_PATH_PATH = re.compile(_WEB_PATH_PAT_STR)

_COOKIE_NAME_PAT_STR = r'^[a-z][a-z0-9_]+$'
_COOKIE_NAME_PAT = re.compile(_COOKIE_NAME_PAT_STR)

_ENV_VAR_PAT_STR = r'^\$([a-zA-Z_][a-zA-Z0-9_]*)$'
_ENV_VAR_PAT = re.compile(_ENV_VAR_PAT_STR)

_ENVPAT_STR = r'^\$\{(.+)\}$'
_ENVPAT = re.compile(_ENVPAT_STR)

_CONFIG_ITEM_ID_PAT_STR = r'^[a-z][a-z0-9_]{2,11}$'
_CONFIG_ITEM_ID_PAT = re.compile(_CONFIG_ITEM_ID_PAT_STR)

_REALM_NAME_PAT_STR = r'^[A-Za-z][A-Za-z0-9_\-@\.]{2,254}$'
_REALM_NAME_PAT = re.compile(_REALM_NAME_PAT_STR)


log = txaio.make_logger()


class InvalidConfigException(Exception):
    pass


def color_json(json_str):
    """
    Given an already formatted JSON string, return a colored variant which will
    produce colored output on terminals.
    """
    assert(type(json_str) == str)
    return highlight(json_str, lexers.JsonLexer(), formatters.TerminalFormatter())


def color_yaml(yaml_str):
    """
    Given an already formatted YAML string, return a colored variant which will
    produce colored output on terminals.
    """
    assert(type(yaml_str) == str)
    return highlight(yaml_str, lexers.YamlLexer(), formatters.TerminalFormatter())


def pprint_json(obj, log_to=None):
    json_str = json.dumps(obj, separators=(', ', ': '), sort_keys=False, indent=3, ensure_ascii=False)
    output_str = color_json(json_str).strip()
    if log_to:
        log_to.info(output_str)
    else:
        print(output_str)


# Force PyYAML to parse _all_ strings into Unicode (as we want for CB configs)
# see: http://stackoverflow.com/a/2967461/884770
def construct_yaml_str(self, node):
    return self.construct_scalar(node)


for Klass in [Loader, SafeLoader]:
    Klass.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)


# Enable PyYAML to deserialize mappings into OrderedDicts
# see: http://pyyaml.org/attachment/ticket/161/use_ordered_dict.py
def construct_ordered_mapping(self, node, deep=False):
    if not isinstance(node, yaml.MappingNode):
        raise ConstructorError(None, None,
                               "expected a mapping node, but found %s" % node.id,
                               node.start_mark)
    mapping = OrderedDict()
    for key_node, value_node in node.value:
        key = self.construct_object(key_node, deep=deep)
        if not isinstance(key, Hashable):
            raise ConstructorError("while constructing a mapping", node.start_mark,
                                   "found unhashable key", key_node.start_mark)
        value = self.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


yaml.constructor.BaseConstructor.construct_mapping = construct_ordered_mapping


def construct_yaml_map_with_ordered_dict(self, node):
    data = OrderedDict()
    yield data
    value = self.construct_mapping(node)
    data.update(value)


for Klass in [Loader, SafeLoader]:
    Klass.add_constructor('tag:yaml.org,2002:map',
                          construct_yaml_map_with_ordered_dict)


# Enable PyYAML to serialize OrderedDict
def represent_ordered_dict(dump, tag, mapping, flow_style=None):
    # the following works like BaseRepresenter.represent_mapping,
    # but does not issue the sort().
    # see: http://pyyaml.org/browser/pyyaml/trunk/lib/yaml/representer.py#L112
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
        # mapping.sort()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


for Klass in [Dumper, SafeDumper]:
    Klass.add_representer(OrderedDict,
                          lambda dumper, value: represent_ordered_dict(dumper, u'tag:yaml.org,2002:map', value))


# Environment variable names used by the utilities in the Shell and Utilities volume
# of IEEE Std 1003.1-2001 consist solely of uppercase letters, digits, and the '_' (underscore)
# from the characters defined in Portable Character Set and do not begin with a digit. Other
# characters may be permitted by an implementation; applications shall tolerate the presence
# of such names.

# http://stackoverflow.com/a/2821183/884770


def _readenv(var, msg):
    match = _ENV_VAR_PAT.match(var)
    if match and match.groups():
        envvar = match.groups()[0]
        if envvar in os.environ:
            return os.environ[envvar]
        else:
            raise InvalidConfigException("{} - environment variable '{}' not set".format(msg, var))
    else:
        raise InvalidConfigException("{} - environment variable name '{}' does not match pattern '{}'".format(msg, var, _ENV_VAR_PAT_STR))


def maybe_from_env(config_item, value):
    log.debug("checkconfig: maybe_from_env('{value}')", value=value)
    if isinstance(value, str):
        match = _ENVPAT.match(value)
        if match and match.groups():
            var = match.groups()[0]
            if var in os.environ:
                new_value = os.environ[var]
                # for security reasons, we log only a starred version of the value read!
                log.info("Configuration '{config_item}' set from environment variable ${var}", config_item=config_item, var=var)
                return new_value
            else:
                log.warn("Environment variable ${var} not set - needed in configuration '{config_item}'", config_item=config_item, var=var)
    log.debug("literal value from config")
    return value


def get_config_value(config, item, default=None):
    """
    Get an item from a configuration dict, possibly trying to read the
    item's value from an environment variable.

    E.g., consider `{"password": "secret123"}`. The function will simply return
    the value `"secret123"`, while with `{"password": "$PASSWORD"}` will read the value
    from the enviroment variable `PASSWORD`.

    When the item is missing in the configuration, or a coonfigured enviroment
    variable isn't defined, a default value is returned.
    """
    if item in config:
        # for string valued items, check if the value actually point to
        # an enviroment variable (e.g. "$PGPASSWORD")
        if isinstance(config[item], str):
            match = _ENV_VAR_PAT.match(config[item])
            if match and match.groups():
                envvar = match.groups()[0]
                if envvar in os.environ:
                    return os.environ[envvar]
                else:
                    # item value seems to point to an enviroment variable,
                    # but the enviroment variable isn't set
                    return default
        return config[item]
    else:
        return default


def check_id(id):
    """
    Check a configuration item ID.
    """
    if not isinstance(id, str):
        raise InvalidConfigException(u'invalid configuration item ID "{}" - type must be string, was {}'.format(id, type(id)))
    if not _CONFIG_ITEM_ID_PAT.match(id):
        raise InvalidConfigException(u'invalid configuration item ID "{}" - must match regular expression {}'.format(id, _CONFIG_ITEM_ID_PAT_STR))


def check_realm_name(name):
    """
    Check a realm name.
    """
    if not isinstance(name, str):
        raise InvalidConfigException(u'invalid realm name "{}" - type must be string, was {}'.format(name, type(name)))
    if not _REALM_NAME_PAT.match(name):
        raise InvalidConfigException(u'invalid realm name "{}" - must match regular expression {}'.format(name, _REALM_NAME_PAT_STR))


def check_dict_args(spec, config, msg):
    """
    Check the arguments of C{config} according to C{spec}.

    C{spec} is a dict, with the key mapping to the config and the value being a
    2-tuple, for which the first item being whether or not it is mandatory, and
    the second being a list of types of which the config item can be.
    """
    if not isinstance(config, Mapping):
        raise InvalidConfigException("{} - invalid type for configuration item - expected dict, got {}".format(msg, type(config).__name__))

    for k in config:
        if k not in spec:
            raise InvalidConfigException("{} - encountered unknown attribute '{}'".format(msg, k))
        if spec[k][1]:
            valid_type = False
            for t in spec[k][1]:
                if isinstance(config[k], t):
                    # We're special-casing Sequence here, because in
                    # general if we say a Sequence is okay, we do NOT
                    # want strings to be allowed but Python says that
                    # "isinstance('foo', Sequence) == True"
                    if t is Sequence:
                        if not isinstance(config[k], (str, str)):
                            valid_type = True
                            break
                    else:
                        valid_type = True
                        break
            if not valid_type:
                raise InvalidConfigException("{} - invalid type {} encountered for attribute '{}', must be one of ({})".format(msg, type(config[k]).__name__, k, ', '.join([x.__name__ for x in spec[k][1]])))

    mandatory_keys = [k for k in spec if spec[k][0]]
    for k in mandatory_keys:
        if k not in config:
            raise InvalidConfigException("{} - missing mandatory attribute '{}'".format(msg, k))


def check_or_raise_uri(value, message):
    if not isinstance(value, str):
        raise InvalidConfigException("{}: invalid type {} for URI".format(message, type(value)))
    if not _URI_PAT_STRICT_NON_EMPTY.match(value):
        raise InvalidConfigException("{}: invalid value '{}' for URI".format(message, value))
    return value


def check_transport_auth_ticket(config):
    """
    Check a Ticket-based authentication configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Ticket-Authentication.md
    """
    if 'type' not in config:
        raise InvalidConfigException("missing mandatory attribute 'type' in WAMP-Ticket configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise InvalidConfigException("invalid type '{}' in WAMP-Ticket configuration - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        if 'principals' not in config:
            raise InvalidConfigException("missing mandatory attribute 'principals' in static WAMP-Ticket configuration")

        if not isinstance(config['principals'], Mapping):
            raise InvalidConfigException("invalid type for attribute 'principals' in static WAMP-Ticket configuration - expected dict, got {}".format(type(config['users'])))

        # check map of principals
        for authid, principal in config['principals'].items():
            check_dict_args({
                'ticket': (True, [str]),
                'role': (False, [str]),
            }, principal, "WAMP-Ticket - principal '{}' configuration".format(authid))

            # allow to set value from environment variable
            principal['ticket'] = maybe_from_env('auth.ticket.principals["{}"].ticket'.format(authid), principal['ticket'])

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise InvalidConfigException("missing mandatory attribute 'authenticator' in dynamic WAMP-Ticket configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-Ticket configuration".format(config['authenticator']))
    else:
        raise InvalidConfigException('logic error')


def check_transport_auth_wampcra(config):
    """
    Check a WAMP-CRA configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Challenge-Response-Authentication.md
    """
    if 'type' not in config:
        raise InvalidConfigException("missing mandatory attribute 'type' in WAMP-CRA configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise InvalidConfigException("invalid type '{}' in WAMP-CRA configuration - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        if 'users' not in config:
            raise InvalidConfigException("missing mandatory attribute 'users' in static WAMP-CRA configuration")
        if not isinstance(config['users'], Mapping):
            raise InvalidConfigException("invalid type for attribute 'users' in static WAMP-CRA configuration - expected dict, got {}".format(type(config['users'])))
        for authid, user in config['users'].items():
            check_dict_args({
                'secret': (True, [str]),
                'role': (False, [str]),
                'salt': (False, [str]),
                'iterations': (False, [int]),
                'keylen': (False, [int])
            }, user, "WAMP-CRA - user '{}' configuration".format(authid))

            # allow to set value from environment variable
            user['secret'] = maybe_from_env('auth.wampcra.users["{}"].secret'.format(authid), user['secret'])

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise InvalidConfigException("missing mandatory attribute 'authenticator' in dynamic WAMP-CRA configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-CRA configuration".format(config['authenticator']))
    else:
        raise InvalidConfigException('logic error')


def check_transport_auth_tls(config):
    """
    Check a WAMP-CRA configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Challenge-Response-Authentication.md
    """
    if 'type' not in config:
        raise InvalidConfigException("missing mandatory attribute 'type' in WAMP-TLS configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise InvalidConfigException("invalid type '{}' in WAMP-TLS configuration - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        # FIXME
        pass
    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise InvalidConfigException("missing mandatory attribute 'authenticator' in dynamic WAMP-TLS configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-TLS configuration".format(config['authenticator']))
    else:
        raise InvalidConfigException('logic error')


def check_transport_auth_cryptosign(config):
    """
    Check a WAMP-Cryptosign configuration item.
    """
    if 'type' not in config:
        raise InvalidConfigException("missing mandatory attribute 'type' in WAMP-Cryptosign configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise InvalidConfigException("invalid type '{}' in WAMP-Cryptosign configuration - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        if 'principals' not in config:
            raise InvalidConfigException("missing mandatory attribute 'principals' in static WAMP-Cryptosign configuration")
        if not isinstance(config['principals'], Mapping):
            raise InvalidConfigException("invalid type for attribute 'principals' in static WAMP-Cryptosign configuration - expected dict, got {}".format(type(config['principals'])))
        for authid, principal in config['principals'].items():
            check_dict_args({
                'authorized_keys': (True, [Sequence]),
                'role': (True, [str]),
                'realm': (False, [str]),
            }, principal, "WAMP-Cryptosign - principal '{}' configuration".format(authid))
            for pubkey in principal['authorized_keys']:
                if not isinstance(pubkey, str):
                    raise InvalidConfigException("invalid type {} for pubkey in authorized_keys of principal".format(type(pubkey)))

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise InvalidConfigException("missing mandatory attribute 'authenticator' in dynamic WAMP-Cryptosign configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-Cryptosign configuration".format(config['authenticator']))
    else:
        raise InvalidConfigException('logic error')


def check_transport_auth_scram(config):
    """
    Check a WAMP-SCRAM configuration item.
    """
    if u'type' not in config:
        raise InvalidConfigException(
            "missing mandatory attribute '{}' in WAMP-SCRAM configuration".format(u'type')
        )
    if config[u'type'] == u'static':
        if u'principals' not in config:
            raise InvalidConfigException(
                "missing mandatory attribute '{}' in WAMP-SCRAM configuration".format(u'principals')
            )

        # check map of principals
        for authid, principal in config['principals'].items():
            check_dict_args({
                'kdf': (True, [str]),
                'iterations': (True, [int]),
                'memory': (True, [int]),
                'salt': (True, [str]),
                'stored-key': (True, [str]),
                'server-key': (True, [str]),
                'role': (False, [str]),
            }, principal, "WAMP-SCRAM - principal '{}' configuration".format(authid))
            available_kdfs = (u'argon2id-13', u'pbkdf2')
            kdf = principal[u'kdf']
            if kdf not in available_kdfs:
                raise ValueError(
                    "WAMP-SCRAM illegal KDF '{}' not one of {}".format(
                        kdf,
                        ', '.join(available_kdfs),
                    )
                )


def check_transport_auth_cookie(config):
    """
    Check a WAMP-Cookie configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Cookie-Authentication.md
    """
    pass


def check_transport_auth_anonymous(config):
    """
    Check a WAMP-Anonymous configuration item.

    http://crossbar.io/docs/Anonymous-Authentication
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Anonymous-Authentication.md
    """
    if 'type' not in config:
        raise InvalidConfigException("missing mandatory attribute 'type' in WAMP-Anonymous configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise InvalidConfigException("invalid type '{}' in WAMP-Anonymous configuration - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        check_dict_args({
            'type': (True, [str]),
            'role': (False, [str]),
        }, config, "WAMP-Anonymous configuration")

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise InvalidConfigException("missing mandatory attribute 'authenticator' in dynamic WAMP-Anonymous configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-Anonymous configuration".format(config['authenticator']))

    else:
        raise InvalidConfigException('logic error')


def check_transport_auth(personality, auth, ignore=[], checks=None):
    """
    Check a WAMP transport authentication configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/auth/Authentication.md
    """
    if not isinstance(auth, Mapping):
        raise InvalidConfigException("invalid type {} for authentication configuration item (dict expected)".format(type(auth)))
    CHECKS = checks or {
        'anonymous': check_transport_auth_anonymous,
        'ticket': check_transport_auth_ticket,
        'wampcra': check_transport_auth_wampcra,
        'tls': check_transport_auth_tls,
        'cookie': check_transport_auth_cookie,
        'cryptosign': check_transport_auth_cryptosign,
        'scram': check_transport_auth_scram,
    }
    for k in auth:
        if k in CHECKS:
            CHECKS[k](auth[k])
        elif k in ignore:
            pass
        else:
            raise InvalidConfigException(
                "invalid authentication method key '{}' - must be one of {}".format(
                    k,
                    list(CHECKS.keys()) + ignore,
                )
            )


def check_cookie_store_memory(store):
    """
    Checking memory-backed cookie store configuration.
    """
    check_dict_args({
        'type': (True, [str]),
    }, store, "WebSocket file-backed cookie store configuration")


def check_cookie_store_file(store):
    """
    Checking file-backed cookie store configuration.
    """
    check_dict_args({
        'type': (True, [str]),
        'filename': (False, [str]),
        'purge_on_startup': (False, [bool])
    }, store, "WebSocket memory-backed cookie store configuration")


def check_transport_cookie(personality, cookie, ignore=[]):
    """
    Check a WAMP-WebSocket transport cookie configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Cookie-Tracking.md
    """
    check_dict_args({
        'name': (False, [str]),
        'length': (False, [int]),
        'max_age': (False, [int]),
        'store': (False, [Mapping])
    }, cookie, "WebSocket cookie configuration")

    if 'name' in cookie:
        match = _COOKIE_NAME_PAT.match(cookie['name'])
        if not match:
            raise InvalidConfigException("invalid cookie name '{}' - must match regular expression {}".format(cookie['name'], _COOKIE_NAME_PAT_STR))

    if 'max_age' in cookie:
        max_age = cookie['max_age']
        if not (max_age > 0 and max_age <= 86400 * 360 * 10):
            raise InvalidConfigException("invalid cookie max_age {} - must be >0 seconds, and <= 10 years", format(max_age))

    if 'length' in cookie:
        length = cookie['length']
        if not (length >= 6 and length <= 64):
            raise InvalidConfigException("invalid cookie length {} - must be >=6 and <= 64", format(length))

    if 'store' in cookie:
        store = cookie['store']

        if 'type' not in store:
            raise InvalidConfigException("missing mandatory attribute 'type' in cookie store configuration\n\n{}".format(pformat(cookie)))

        store_type = store['type']
        if store_type not in ['memory', 'file'] + ignore:
            raise InvalidConfigException("invalid attribute value '{}' for attribute 'type' in cookie store item\n\n{}".format(store_type, pformat(cookie)))

        if store_type == 'memory':
            check_cookie_store_memory(store)
        elif store_type == 'file':
            check_cookie_store_file(store)
        elif store_type in ignore:
            pass
        else:
            raise InvalidConfigException('logic error')


def check_endpoint_backlog(backlog):
    """
    Check listening endpoint backlog parameter.

    :param backlog: The backlog parameter for listening endpoints to check.
    :type backlog: int
    """
    if not isinstance(backlog, int):
        raise InvalidConfigException("'backlog' attribute in endpoint must be int ({} encountered)".format(type(backlog)))
    if backlog < 1 or backlog > 65535:
        raise InvalidConfigException("invalid value {} for 'backlog' attribute in endpoint (must be from [1, 65535])".format(backlog))


def check_endpoint_port(port, message="listening/connection endpoint"):
    """
    Check a listening/connecting endpoint TCP port.

    :param port: The port to check.
    :type port: int
    """
    if not isinstance(port, int):
        raise InvalidConfigException("'port' attribute in {} must be integer ({} encountered)".format(message, type(port)))
    if port < 1 or port > 65535:
        raise InvalidConfigException("invalid value {} for 'port' attribute in {}".format(port, message))


def check_endpoint_ip_version(version):
    """
    Check a listening/connecting endpoint TCP version.

    :param version: The version to check.
    :type version: int
    """
    if not isinstance(version, int):
        raise InvalidConfigException("'version' attribute in endpoint must be integer ({} encountered)".format(type(version)))
    if version not in [4, 6]:
        raise InvalidConfigException("invalid value {} for 'version' attribute in endpoint".format(version))


def check_endpoint_timeout(timeout):
    """
    Check a connecting endpoint timeout parameter.

    :param timeout: The timeout (seconds) to check.
    :type timeout: int
    """
    if not isinstance(timeout, int):
        raise InvalidConfigException("'timeout' attribute in endpoint must be integer ({} encountered)".format(type(timeout)))
    if timeout < 0 or timeout > 600:
        raise InvalidConfigException("invalid value {} for 'timeout' attribute in endpoint".format(timeout))


def check_transport_max_message_size(max_message_size):
    """
    Check maxmimum message size parameter in RawSocket and WebSocket transports.

    :param max_message_size: The maxmimum message size parameter to check.
    :type max_message_size: int
    """
    if not isinstance(max_message_size, int):
        raise InvalidConfigException("'max_message_size' attribute in transport must be int ({} encountered)".format(type(max_message_size)))
    if max_message_size < 1 or max_message_size > 64 * 1024 * 1024:
        raise InvalidConfigException("invalid value {} for 'max_message_size' attribute in transport (must be from [1, 64MB])".format(max_message_size))


def check_listening_endpoint_tls(tls):
    """
    Check a listening endpoint TLS configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param tls: The TLS configuration part of a listening endpoint.
    :type tls: dict
    """
    check_dict_args({
        'key': (True, [str]),
        'certificate': (True, [str]),
        'chain_certificates': (False, [Sequence]),
        'dhparam': (False, [str]),
        'ciphers': (False, [str]),
        'ca_certificates': (False, [Sequence]),
    }, tls, "TLS listening endpoint")

    return


def check_connecting_endpoint_tls(tls):
    """
    Check a connecting endpoint TLS configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param tls: The TLS configuration part of a connecting endpoint.
    :type tls: dict
    """
    if not isinstance(tls, Mapping):
        raise InvalidConfigException("'tls' in connecting endpoint must be dictionary ({} encountered)".format(type(tls)))

    for k in tls:
        if k not in ['ca_certificates', 'hostname', 'certificate', 'key']:
            raise InvalidConfigException("encountered unknown attribute '{}' in connecting endpoint TLS configuration".format(k))

    if 'ca_certificates' in tls:
        if not isinstance(tls['ca_certificates'], Sequence):
            raise InvalidConfigException("'ca_certificates' must be a list")

    for req_k in ['hostname']:
        if req_k not in tls:
            raise InvalidConfigException("connecting endpoint TLS configuration requires '{}'".format(req_k))


def check_listening_endpoint_tcp(endpoint):
    """
    Check a TCP listening endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The TCP listening endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'version', 'port', 'shared', 'interface', 'backlog', 'tls']:
            raise InvalidConfigException("encountered unknown attribute '{}' in listening endpoint".format(k))

    if 'port' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'port' in listening endpoint item\n\n{}".format(pformat(endpoint)))

    if isinstance(endpoint['port'], str):
        port = _readenv(endpoint['port'], "listening endpoint configuration")
        try:
            port = int(port)
        except:
            pass  # we handle this in check_endpoint_port()
    else:
        port = endpoint['port']
    check_endpoint_port(port)

    if 'version' in endpoint:
        check_endpoint_ip_version(endpoint['version'])

    if 'shared' in endpoint:
        shared = endpoint['shared']
        if not isinstance(shared, bool):
            raise InvalidConfigException("'shared' attribute in endpoint must be bool ({} encountered)".format(type(shared)))

    if 'tls' in endpoint:
        check_listening_endpoint_tls(endpoint['tls'])

    if 'interface' in endpoint:
        interface = endpoint['interface']
        if not isinstance(interface, str):
            raise InvalidConfigException("'interface' attribute in endpoint must be string ({} encountered)".format(type(interface)))

    if 'backlog' in endpoint:
        check_endpoint_backlog(endpoint['backlog'])


def check_listening_endpoint_unix(endpoint):
    """
    Check a Unix listening endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The Unix listening endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'path', 'backlog']:
            raise InvalidConfigException("encountered unknown attribute '{}' in listening endpoint".format(k))

    if 'path' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

    path = endpoint['path']
    if not isinstance(path, str):
        raise InvalidConfigException("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

    if 'backlog' in endpoint:
        check_endpoint_backlog(endpoint['backlog'])


def check_listening_endpoint_twisted(endpoint):
    """
    :param endpoint: The Twisted endpoint to check
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'server_string']:
            raise InvalidConfigException(
                "encountered unknown attribute '{}' in listening endpoint".format(k)
            )

    if 'server_string' not in endpoint:
        raise InvalidConfigException(
            "missing mandatory attribute 'server_string' in Twisted"
            " endpoint item\n\n{}".format(pformat(endpoint))
        )

    server = endpoint['server_string']
    if not isinstance(server, str):
        raise InvalidConfigException(
            "'server_string' attribute in Twisted endpoint must be str"
            " ({} encountered)".format(type(server))
        )
    # should/can we ask Twisted to parse it easily?


def check_listening_endpoint_onion(personality, endpoint):
    """
    :param endpoint: The onion endpoint
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'port', 'private_key_file', 'tor_control_endpoint', 'version']:
            raise InvalidConfigException(
                "encountered unknown attribute '{}' in onion endpoint".format(k)
            )

    check_dict_args(
        {
            u"type": (True, [str]),
            u"port": (True, [int]),
            u"version": (False, [int]),
            u"private_key_file": (True, [str]),
            u"tor_control_endpoint": (True, [Mapping])
        },
        endpoint,
        "onion endpoint config",
    )

    if "version" in endpoint:
        if endpoint["version"] not in (2, 3):
            raise InvalidConfigException(
                "Onion endpoint version must be 2 or 3"
            )

    check_endpoint_port(endpoint[u"port"])
    personality.check_connecting_endpoint(personality, endpoint[u"tor_control_endpoint"])


def check_connecting_endpoint_tcp(endpoint):
    """
    Check a TCP connecting endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The TCP connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'version', 'host', 'port', 'timeout', 'tls']:
            raise InvalidConfigException("encountered unknown attribute '{}' in connecting endpoint".format(k))

    if 'host' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'host' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    if 'port' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'port' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    check_endpoint_port(endpoint['port'])

    if 'version' in endpoint:
        check_endpoint_ip_version(endpoint['version'])

    if 'tls' in endpoint:
        check_connecting_endpoint_tls(endpoint['tls'])

    if 'timeout' in endpoint:
        check_endpoint_timeout(endpoint['timeout'])


def check_connecting_endpoint_unix(endpoint):
    """
    Check a Unix connecting endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The Unix connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'path', 'timeout']:
            raise InvalidConfigException("encountered unknown attribute '{}' in connecting endpoint".format(k))

    if 'path' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

    path = endpoint['path']
    if not isinstance(path, str):
        raise InvalidConfigException("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

    if 'timeout' in endpoint:
        check_endpoint_timeout(endpoint['timeout'])


def check_connecting_endpoint_twisted(endpoint):
    """
    :param endpoint: The Twisted connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'client_string', 'timeout']:
            raise InvalidConfigException(
                "encountered unknown attribute '{}' in connecting endpoint".format(k)
            )

    if 'client_string' not in endpoint:
        raise InvalidConfigException(
            "missing mandatory attribute 'client_string' in Twisted endpoint "
            "item\n\n{}".format(pformat(endpoint))
        )

    client_string = endpoint['client_string']
    if not isinstance(client_string, str):
        raise InvalidConfigException(
            "'client_string' attribute in Twisted endpoint must be "
            "str ({} encountered)".format(type(client_string)))
    # can we make Twisted tell us if client_string parses? or just
    # save it until we actually run clientFromString()?

    if 'timeout' in endpoint:
        check_endpoint_timeout(endpoint['timeout'])


def check_connecting_endpoint_tor(personality, endpoint):
    """
    :param endpoint: The Tor connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'host', 'port', 'tor_socks_port', 'tls']:
            raise InvalidConfigException(
                "encountered unknown attribute '{}' in connecting endpoint".format(k)
            )

    if 'host' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'host' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    if 'port' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'port' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    if 'tor_socks_port' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'tor_socks_port' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    check_endpoint_port(endpoint['port'])
    check_endpoint_port(endpoint['tor_socks_port'])

    if 'tls' in endpoint:
        check_connecting_endpoint_tls(personality, endpoint['tls'])


def check_listening_endpoint(personality, endpoint, ignore=[]):
    """
    Check a listening endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The listening endpoint configuration.
    :type endpoint: dict
    """
    if not isinstance(endpoint, Mapping):
        raise InvalidConfigException("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

    if 'type' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

    etype = endpoint['type']
    if etype not in ['tcp', 'unix', 'twisted', 'onion'] + ignore:
        raise InvalidConfigException("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

    if etype == 'tcp':
        check_listening_endpoint_tcp(endpoint)
    elif etype == 'unix':
        check_listening_endpoint_unix(endpoint)
    elif etype == 'twisted':
        check_listening_endpoint_twisted(endpoint)
    elif etype == 'onion':
        check_listening_endpoint_onion(personality, endpoint)
    elif etype in ignore:
        pass
    else:
        raise InvalidConfigException('logic error')


def check_connecting_endpoint(personality, endpoint, ignore=[]):
    """
    Check a conencting endpoint configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param endpoint: The connecting endpoint configuration.
    :type endpoint: dict
    """
    if not isinstance(endpoint, Mapping):
        raise InvalidConfigException("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

    if 'type' not in endpoint:
        raise InvalidConfigException("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

    etype = endpoint['type']
    if etype not in ['tcp', 'unix', 'twisted', 'tor'] + ignore:
        raise InvalidConfigException("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

    if etype == 'tcp':
        check_connecting_endpoint_tcp(endpoint)
    elif etype == 'unix':
        check_connecting_endpoint_unix(endpoint)
    elif etype == 'twisted':
        check_connecting_endpoint_twisted(endpoint)
    elif etype == 'tor':
        check_connecting_endpoint_tor(personality, endpoint)
    elif etype in ignore:
        pass
    else:
        raise InvalidConfigException('logic error')


def _check_milliseconds(name, value):
    try:
        value = int(value)
    except ValueError:
        raise InvalidConfigException(
            "'{}' should be an integer (in milliseconds)".format(name)
        )
    if value < 0:
        raise InvalidConfigException(
            "'{}' must be positive integer".format(name)
        )
    if value != 0 and value < 1000:
        raise InvalidConfigException(
            "'{}' is in milliseconds; {} is too small".format(name, value)
        )
    return True


def check_websocket_options(options):
    """
    Check WebSocket / WAMP-WebSocket protocol options.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/WebSocket-Options.md

    :param options: The options to check.
    :type options: dict
    """
    if not isinstance(options, Mapping):
        raise InvalidConfigException("WebSocket options must be a dictionary ({} encountered)".format(type(options)))

    for k in options:
        if k not in [
            # WebSocket options
            'allowed_origins',
            'allow_null_origin',
            'external_port',
            'enable_hybi10',
            'enable_rfc6455',
            'open_handshake_timeout',
            'close_handshake_timeout',
            'enable_webstatus',
            'validate_utf8',
            'mask_server_frames',
            'require_masked_client_frames',
            'apply_mask',
            'max_frame_size',
            'max_message_size',
            'auto_fragment_size',
            'fail_by_drop',
            'echo_close_codereason',
            'tcp_nodelay',
            'auto_ping_interval',
            'auto_ping_timeout',
            'auto_ping_size',
            'enable_flash_policy',
            'flash_policy',
            'compression',
            'require_websocket_subprotocol',
            'show_server_version',
        ]:
            raise InvalidConfigException("encountered unknown attribute '{}' in WebSocket options".format(k))

    millisecond_intervals = [
        'open_handshake_timeout',
        'close_handshake_timeout',
        'auto_ping_interval',
        'auto_ping_timeout',
    ]
    for k in millisecond_intervals:
        if k in options:
            _check_milliseconds(k, options[k])

    if 'compression' in options:
        check_websocket_compression(options['compression'])


def check_websocket_compression(options):
    """
    Check options for WebSocket compression.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/WebSocket-Compression.md
    """
    # FIXME


def check_web_path_service_websocket_reverseproxy(personality, config):
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'url': (False, [str]),
        'options': (False, [Mapping]),
        'backend': (True, [Mapping])
    }, config, "Web transport 'Reverse WebSocket Proxy' path service")

    if 'url' in config:
        url = config['url']
        if not isinstance(url, str):
            raise InvalidConfigException("'url' in WebSocket configuration must be str ({} encountered)".format(type(url)))
        try:
            parse_url(url)
        except InvalidConfigException as e:
            raise InvalidConfigException("invalid 'url' in WebSocket configuration : {}".format(e))

    if 'options' in config:
        check_websocket_options(config['options'])

    check_connecting_transport_websocket(personality, config['backend'])


def check_web_path_service_websocket(personality, config):
    """
    Check a "websocket" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/WebSocket-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'url': (False, [str]),
        'serializers': (False, [Sequence]),
        'cookie': (False, [Mapping]),
        'auth': (False, [Mapping]),
        'options': (False, [Mapping]),
        'debug': (False, [bool])
    }, config, "Web transport 'WebSocket' path service")

    if 'options' in config:
        check_websocket_options(config['options'])

    if 'debug' in config:
        debug = config['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in WebSocket configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in config:
        url = config['url']
        if not isinstance(url, str):
            raise InvalidConfigException("'url' in WebSocket configuration must be str ({} encountered)".format(type(url)))
        try:
            parse_url(url)
        except InvalidConfigException as e:
            raise InvalidConfigException("invalid 'url' in WebSocket configuration : {}".format(e))

    if 'auth' in config:
        personality.check_transport_auth(personality, config['auth'])

    if 'cookie' in config:
        personality.check_transport_cookie(personality, config['cookie'])


def check_web_path_service_static(personality, config):
    """
    Check a "static" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Static-Web-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'directory': (False, [str]),
        'package': (False, [str]),
        'resource': (False, [str]),
        'options': (False, [Mapping])
    }, config, "Web transport 'static' path service")

    if 'directory' in config:
        if 'package' in config or 'resource' in config:
            raise InvalidConfigException("Web transport 'static' path service: either 'directory' OR 'package' + 'resource' must be given, not both")
    else:
        if 'package' not in config or 'resource' not in config:
            raise InvalidConfigException("Web transport 'static' path service: either 'directory' OR 'package' + 'resource' must be given, not both")

    if 'options' in config:
        check_dict_args({
            'enable_directory_listing': (False, [bool]),
            'mime_types': (False, [Mapping]),
            'cache_timeout': (False, [int, type(None)]),
            'default_file': (False, [str]),
        }, config['options'], "'options' in Web transport 'static' path service")


def check_web_path_service_wsgi(personality, config):
    """
    Check a "wsgi" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/WSGI-Host-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'module': (True, [str]),
        'object': (True, [str]),
        'minthreads': (False, [int]),
        'maxthreads': (False, [int]),
    }, config, "Web transport 'wsgi' path service")


def check_web_path_service_resource(personality, config):
    """
    Check a "resource" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Resource-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'classname': (True, [str]),
        'extra': (False, None)
    }, config, "Web transport 'resource' path service")


def check_web_path_service_redirect(personality, config):
    """
    Check a "redirect" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Web-Redirection-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'url': (True, [str])
    }, config, "Web transport 'redirect' path service")


def check_web_path_service_nodeinfo(personality, config):
    """
    Check a "nodeinfo" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
    }, config, "Web transport 'nodeinfo' path service")


def check_web_path_service_reverseproxy(personality, config):
    """
    Check a "reverseproxy" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Web-ReverseProxy-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'host': (True, [str]),
        'port': (False, [int]),
        'path': (False, [str])
    }, config, "Web transport 'reverseproxy' path service")


def check_web_path_service_json(personality, config):
    """
    Check a "json" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/JSON-Value-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'value': (True, None),
        'options': (False, [Mapping]),
    }, config, "Web transport 'json' path service")

    if 'options' in config:
        check_dict_args({
            'prettify': (False, [bool]),
            'allow_cross_origin': (False, [bool]),
            'discourage_caching': (False, [bool]),
        }, config['options'], "Web transport 'json' path service")


def check_web_path_service_cgi(personality, config):
    """
    Check a "cgi" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/CGI-Script-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'directory': (True, [str]),
        'processor': (True, [str]),
    }, config, "Web transport 'cgi' path service")


def check_web_path_service_longpoll(personality, config):
    """
    Check a "longpoll" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Long-Poll-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'options': (False, [Mapping]),
    }, config, "Web transport 'longpoll' path service")

    if 'options' in config:
        check_dict_args({
            'debug': (False, [bool]),
            'debug_transport_id': (False, [str]),
            'request_timeout': (False, [int]),
            'session_timeout': (False, [int]),
            'queue_limit_bytes': (False, [int]),
            'queue_limit_messages': (False, [int]),
        }, config['options'], "Web transport 'longpoll' path service")


def check_web_path_service_rest_post_body_limit(limit):
    """
    Check a publisher/caller web path service "post_body_limit" parameter.

    :param port: The limit to check.
    :type port: int
    """
    if not isinstance(limit, int):
        raise InvalidConfigException("'post_body_limit' attribute in publisher/caller configuration must be integer ({} encountered)".format(type(limit)))
    if limit < 0 or limit > 2 ** 20:
        raise InvalidConfigException("invalid value {} for 'post_body_limit' attribute in publisher/caller configuration".format(limit))


def check_web_path_service_rest_timestamp_delta_limit(limit):
    """
    Check a publisher/caller web path service "timestamp_delta_limit" parameter.

    :param port: The limit to check.
    :type port: int
    """
    if not isinstance(limit, int):
        raise InvalidConfigException("'timestamp_delta_limit' attribute in publisher/caller configuration must be integer ({} encountered)".format(type(limit)))
    if limit < 0 or limit > 86400:
        raise InvalidConfigException("invalid value {} for 'timestamp_delta_limit' attribute in publisher/caller configuration".format(limit))


def check_web_path_service_publisher(personality, config):
    """
    Check a "publisher" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/http-bridge/HTTP-Bridge-Publisher.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'realm': (True, [str]),
        'role': (True, [str]),
        'options': (False, [Mapping]),
    }, config, "Web transport 'publisher' path service")

    if 'options' in config:
        check_dict_args({
            'debug': (False, [bool]),
            'key': (False, [str]),
            'secret': (False, [str]),
            'require_tls': (False, [bool]),
            'require_ip': (False, [Sequence]),
            'post_body_limit': (False, [int]),
            'timestamp_delta_limit': (False, [int]),
        }, config['options'], "Web transport 'publisher' path service")

        if 'post_body_limit' in config['options']:
            check_web_path_service_rest_post_body_limit(config['options']['post_body_limit'])

        if 'timestamp_delta_limit' in config['options']:
            check_web_path_service_rest_timestamp_delta_limit(config['options']['timestamp_delta_limit'])


def check_web_path_service_webhook(personality, config):
    """
    Check a "webhook" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/http-bridge/HTTP-Bridge-Webhook.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'realm': (True, [str]),
        'role': (True, [str]),
        'options': (True, [Mapping]),
    }, config, "Web transport 'webhook' path service")

    check_dict_args({
        'debug': (False, [bool]),
        'post_body_limit': (False, [int]),
        'topic': (False, [str]),
        'success_response': (False, [str]),
        'error_response': (False, [str]),
        'github_secret': (False, [str]),
    }, config['options'], "Web transport 'webhook' path service")

    if 'post_body_limit' in config['options']:
        check_web_path_service_rest_post_body_limit(config['options']['post_body_limit'])


def check_web_path_service_caller(personality, config):
    """
    Check a "caller" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/http-bridge/HTTP-Bridge-Caller.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'realm': (True, [str]),
        'role': (True, [str]),
        'options': (False, [Mapping]),
    }, config, "Web transport 'caller' path service")

    if 'options' in config:
        check_dict_args({
            'debug': (False, [bool]),
            'key': (False, [str]),
            'secret': (False, [str]),
            'require_tls': (False, [bool]),
            'require_ip': (False, [Sequence]),
            'post_body_limit': (False, [int]),
            'timestamp_delta_limit': (False, [int]),
        }, config['options'], "Web transport 'caller' path service")

        if 'post_body_limit' in config['options']:
            check_web_path_service_rest_post_body_limit(config['options']['post_body_limit'])

        if 'timestamp_delta_limit' in config['options']:
            check_web_path_service_rest_timestamp_delta_limit(config['options']['timestamp_delta_limit'])


def check_web_path_service_path(personality, config):
    """
    Check a "path" path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Path-Service.md

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'paths': (True, [Mapping]),
    }, config, "Web transport 'path' path service")

    # check nested paths
    #
    check_paths(personality, config['paths'], nested=True)


def check_web_path_service_max_file_size(limit):
    """
    Check maximum "max_file_size" parameter.

    :param limit: The limit to check.
    :type limit: int
    """
    if not isinstance(limit, int):
        raise InvalidConfigException("'max_file_size' attribute must be integer ({} encountered)".format(type(limit)))
    if limit < 0:
        raise InvalidConfigException("invalid value {} for 'max_file_size' attribute - must be non-negative".format(limit))


def check_web_path_service_upload(personality, config):
    """
    Check a file upload path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/File-Upload-Service.md

    :param config: The path service configuration.
    :type config: dict
    """

    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'realm': (True, [str]),
        'role': (True, [str]),
        'directory': (True, [str]),
        'temp_directory': (False, [str]),
        'form_fields': (True, [Mapping]),
        'options': (False, [Mapping])
    }, config, "Web transport 'upload' path service")

    check_dict_args({
        'file_name': (True, [str]),
        'mime_type': (True, [str]),
        'total_size': (True, [str]),
        'chunk_number': (True, [str]),
        'chunk_size': (True, [str]),
        'total_chunks': (True, [str]),
        'content': (True, [str]),
        'on_progress': (False, [str]),
        'session': (False, [str]),
        'chunk_extra': (False, [str]),
        'finish_extra': (False, [str])
    }, config['form_fields'], "File upload form field settings")

    if 'on_progress' in config['form_fields']:
        check_or_raise_uri(config['form_fields']['on_progress'], "invalid File Progress URI '{}' in File Upload configuration. ".format(config['form_fields']['on_progress']))

    if 'options' in config:
        check_dict_args({
            'max_file_size': (False, [int]),
            'file_types': (False, [Sequence]),
            'file_permissions': (False, [str])
        }, config['options'], "Web transport 'upload' path service")

        if 'max_file_size' in config['options']:
            check_web_path_service_max_file_size(config['options']['max_file_size'])


def check_web_path_service(personality, path, config, nested, ignore=[]):
    """
    Check a single path service on Web transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/web-service/Web-Services.md

    :param personality: The node personality class.
    :type personality: crossbar.personality.Personality

    :param config: The path service configuration.
    :type config: dict

    :param nested: Whether this is a nested path.
    :type nested: bool
    """
    if 'id' in config:
        check_id(config['id'])

    if 'type' not in config:
        raise InvalidConfigException('missing mandatory attribute "type" in Web service configuration item\n\n{}'.format(path, config))

    ptype = config['type']
    if ptype in personality.WEB_SERVICE_CHECKERS:
        if path == '/' and not nested:
            # FIXME: check if Web service can run on root path
            if False:
                raise InvalidConfigException('invalid Web service type "{}" on root URL path "{}" - service cannot run on root path'.format(ptype, path))
        personality.WEB_SERVICE_CHECKERS[ptype](personality, config)
    elif ptype in ignore:
        pass
    else:
        raise InvalidConfigException('invalid Web service type "{}" on URL path "{}"'.format(ptype, path))


def check_listening_transport_web(personality, transport, with_endpoint=True, ignore=[]):
    """
    Check a listening Web-WAMP transport configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Web-Transport-and-Services.md

    :param transport: The Web transport configuration to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'paths', 'options']:
            raise InvalidConfigException("encountered unknown attribute '{}' in Web transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if with_endpoint:
        if 'endpoint' not in transport:
            raise InvalidConfigException("missing mandatory attribute 'endpoint' in Web transport item\n\n{}".format(pformat(transport)))
        personality.check_listening_endpoint(personality, transport['endpoint'])
    else:
        if 'endpoint' in transport:
            raise InvalidConfigException("illegal attribute 'endpoint' in Universal transport Web transport subitem\n\n{}".format(pformat(transport)))

    if 'paths' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'paths' in Web transport item\n\n{}".format(pformat(transport)))

    paths = transport['paths']
    if not isinstance(paths, Mapping):
        raise InvalidConfigException("'paths' attribute in Web transport configuration must be dictionary ({} encountered)".format(type(paths)))

    personality.check_paths(personality, paths)

    if 'options' in transport:
        options = transport['options']
        if not isinstance(options, Mapping):
            raise InvalidConfigException("'options' in Web transport must be dictionary ({} encountered)".format(type(options)))

        valid_options = [
            'access_log',
            'display_tracebacks',
            'hsts',
            'hsts_max_age',
            'client_timeout',
        ] + ignore
        for k in options.keys():
            if k not in valid_options:
                raise InvalidConfigException(
                    "'{}' unknown in Web transport 'options'".format(k)
                )

        if 'access_log' in options:
            access_log = options['access_log']
            if not isinstance(access_log, bool):
                raise InvalidConfigException("'access_log' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(access_log)))

        if 'display_tracebacks' in options:
            display_tracebacks = options['display_tracebacks']
            if not isinstance(display_tracebacks, bool):
                raise InvalidConfigException("'display_tracebacks' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(display_tracebacks)))

        if 'hsts' in options:
            hsts = options['hsts']
            if not isinstance(hsts, bool):
                raise InvalidConfigException("'hsts' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(hsts)))

        if 'hsts_max_age' in options:
            hsts_max_age = options['hsts_max_age']
            if not isinstance(hsts_max_age, int):
                raise InvalidConfigException("'hsts_max_age' attribute in 'options' in Web transport must be integer ({} encountered)".format(type(hsts_max_age)))
            if hsts_max_age < 0:
                raise InvalidConfigException("'hsts_max_age' attribute in 'options' in Web transport must be non-negative ({} encountered)".format(hsts_max_age))

        if 'client_timeout' in options:
            timeout = options['client_timeout']
            if timeout is None:
                pass
            elif not isinstance(timeout, int):
                raise InvalidConfigException(
                    "'client_time' attribute in 'options' in Web transport must be integer ({} encountered)".format(
                        type(timeout)
                    )
                )
            elif timeout < 1 or timeout > 60 * 60 * 24:
                raise InvalidConfigException(
                    "unreasonable value for 'client_timeout' in Web transport 'options': {}".format(
                        timeout
                    )
                )


def check_listening_transport_mqtt(personality, transport, with_endpoint=True):
    """
    Check a listening MQTT-WAMP transport configuration.

    http://crossbar.io/docs/MQTT-Broker/

    :param transport: The MQTT transport configuration to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'options']:
            raise InvalidConfigException("encountered unknown attribute '{}' in MQTT transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if with_endpoint:
        if 'endpoint' not in transport:
            raise InvalidConfigException("missing mandatory attribute 'endpoint' in MQTT transport item\n\n{}".format(pformat(transport)))
        personality.check_listening_endpoint(personality, transport['endpoint'])

    # Check MQTT options...
    options = transport.get('options', {})
    check_dict_args({
        'realm': (True, [str]),
        'role': (False, [str]),
        'payload_mapping': (False, [Mapping]),
    }, options, "invalid MQTT options")

    check_realm_name(options['realm'])

    if 'payload_mapping' in options:
        for k, v in options['payload_mapping'].items():
            if not isinstance(k, str):
                raise InvalidConfigException('invalid MQTT payload mapping key {}'.format(type(k)))
            if not isinstance(v, Mapping):
                raise InvalidConfigException('invalid MQTT payload mapping value {}'.format(type(v)))
            if 'type' not in v:
                raise InvalidConfigException('missing "type" in MQTT payload mapping {}'.format(v))
            if v['type'] not in [u'passthrough', u'native', u'dynamic']:
                raise InvalidConfigException('invalid "type" in MQTT payload mapping: {}'.format(v['type']))
            if v['type'] == u'passthrough':
                pass
            elif v['type'] == u'native':
                serializer = v.get(u'serializer', None)
                if serializer not in [u'cbor', u'json', u'msgpack', u'ubjson']:
                    raise InvalidConfigException('invalid serializer "{}" in MQTT payload mapping'.format(serializer))
            elif v['type'] == u'dynamic':
                encoder = v.get(u'encoder', None)
                if not isinstance(encoder, str):
                    raise InvalidConfigException('invalid encoder "{}" in MQTT payload mapping'.format(encoder))
                decoder = v.get(u'decoder', None)
                if not isinstance(decoder, str):
                    raise InvalidConfigException('invalid decoder "{}" in MQTT payload mapping'.format(decoder))
            else:
                raise Exception('logic error')


def check_paths(personality, paths, nested=False, ignore=[]):
    """
    Checks all configured paths.

    :param paths: Configured paths to check.
    :type paths: dict
    :param nested: Whether this is a nested path.
    :type nested: bool
    """
    for p in paths:
        if not isinstance(p, str):
            raise InvalidConfigException("keys in 'paths' in Web transport / WebSocket subitems in Universal transport configuration must be strings ({} encountered)".format(type(p)))

        if not _WEB_PATH_PATH.match(p):
            raise InvalidConfigException("invalid value '{}' for path in Web transport / WebSocket subitem in Universal transport configuration - must match regular expression {}".format(p, _WEB_PATH_PAT_STR))

        personality.check_web_path_service(personality, p, paths[p], nested, ignore)


def check_listening_transport_universal(personality, transport):

    for k in transport:
        if k not in [
            'id',
            'type',
            'endpoint',
            'rawsocket',
            'websocket',
            'mqtt',
            'web',
        ]:
            raise InvalidConfigException("encountered unknown attribute '{}' in Universal transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in Universal transport item\n\n{}".format(pformat(transport)))

    personality.check_listening_endpoint(personality, transport['endpoint'])

    if 'rawsocket' in transport:
        personality.check_listening_transport_rawsocket(personality, transport['rawsocket'], with_endpoint=False)

    if 'websocket' in transport:
        paths = transport['websocket']

        if not isinstance(paths, Mapping):
            raise InvalidConfigException("'websocket' attribute in Universal transport configuration must be dictionary ({} encountered)".format(type(paths)))

        personality.check_paths(personality, paths)

        for path in paths:
            personality.check_listening_transport_websocket(personality, transport['websocket'][path], with_endpoint=False)

    if 'mqtt' in transport:
        personality.check_listening_transport_mqtt(personality, transport['mqtt'], with_endpoint=False)

    if 'web' in transport:
        personality.check_listening_transport_web(personality, transport['web'], with_endpoint=False)


def check_listening_transport_websocket(personality, transport, with_endpoint=True):
    """
    Check a listening WebSocket-WAMP transport configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/WebSocket-Transport.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in [
           'id',
           'type',
           'endpoint',
           'url',
           'serializers',
           'debug',
           'options',
           'auth',
           'cookie']:
            raise InvalidConfigException("encountered unknown attribute '{}' in WebSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if with_endpoint:
        if 'endpoint' not in transport:
            raise InvalidConfigException("missing mandatory attribute 'endpoint' in WebSocket transport item\n\n{}".format(pformat(transport)))
        personality.check_listening_endpoint(personality, transport['endpoint'])
    else:
        if 'endpoint' in transport:
            raise InvalidConfigException("illegal attribute 'endpoint' in Universal transport WebSocket transport subitem\n\n{}".format(pformat(transport)))

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'serializers' in transport:
        serializers = transport['serializers']
        if not isinstance(serializers, Sequence):
            raise InvalidConfigException("'serializers' in WebSocket transport configuration must be list ({} encountered)".format(type(serializers)))

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in WebSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in transport:
        url = transport['url']
        if not isinstance(url, str):
            raise InvalidConfigException("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
        try:
            parse_url(url)
        except InvalidConfigException as e:
            raise InvalidConfigException("invalid 'url' in WebSocket transport configuration : {}".format(e))

    if 'auth' in transport:
        personality.check_transport_auth(personality, transport['auth'])

    if 'cookie' in transport:
        personality.check_transport_cookie(personality, transport['cookie'])


def check_listening_transport_websocket_testee(personality, transport):
    """
    Check a listening WebSocket-Testee pseudo transport configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/production/WebSocket-Compliance-Testing.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in [
           'id',
           'type',
           'endpoint',
           'url',
           'debug',
           'options']:
            raise InvalidConfigException("encountered unknown attribute '{}' in WebSocket-Testee transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in WebSocket-Testee transport item\n\n{}".format(pformat(transport)))

    personality.check_listening_endpoint(personality, transport['endpoint'])

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in WebSocket-Testee transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in transport:
        url = transport['url']
        if not isinstance(url, str):
            raise InvalidConfigException("'url' in WebSocket-Testee transport configuration must be str ({} encountered)".format(type(url)))
        try:
            parse_url(url)
        except InvalidConfigException as e:
            raise InvalidConfigException("invalid 'url' in WebSocket-Testee transport configuration : {}".format(e))


def check_listening_transport_stream_testee(personality, transport):
    """
    Check a listening Stream-Testee pseudo transport configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/production/Stream-Testee.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in [
           'id',
           'type',
           'endpoint',
           'debug']:
            raise InvalidConfigException("encountered unknown attribute '{}' in Stream-Testee transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in Stream-Testee transport item\n\n{}".format(pformat(transport)))

    personality.check_listening_endpoint(personality, transport['endpoint'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in WebSocket-Stream transport configuration must be boolean ({} encountered)".format(type(debug)))


def check_listening_transport_flashpolicy(personality, transport):
    """
    Check a Flash-policy file serving pseudo-transport.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Flash-Policy-Transport.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'allowed_domain', 'allowed_ports', 'debug']:
            raise InvalidConfigException("encountered unknown attribute '{}' in Flash-policy transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in Flash-policy transport item\n\n{}".format(pformat(transport)))

    personality.check_listening_endpoint(personality, transport['endpoint'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in Flash-policy transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'allowed_domain' in transport:
        allowed_domain = transport['allowed_domain']
        if not isinstance(allowed_domain, str):
            raise InvalidConfigException("'allowed_domain' in Flash-policy transport configuration must be str ({} encountered)".format(type(allowed_domain)))

    if 'allowed_ports' in transport:
        allowed_ports = transport['allowed_ports']
        if not isinstance(allowed_ports, Sequence):
            raise InvalidConfigException("'allowed_ports' in Flash-policy transport configuration must be list of integers ({} encountered)".format(type(allowed_ports)))
        for port in allowed_ports:
            check_endpoint_port(port, "Flash-policy allowed_ports")


def check_listening_transport_rawsocket(personality, transport, with_endpoint=True):
    """
    Check a listening RawSocket-WAMP transport configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/RawSocket-Transport.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in [
            'id',
            'type',
            'endpoint',
            'serializers',
            'max_message_size',
            'debug',
            'auth',
        ]:
            raise InvalidConfigException("encountered unknown attribute '{}' in RawSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if with_endpoint:
        if 'endpoint' not in transport:
            raise InvalidConfigException("missing mandatory attribute 'endpoint' in RawSocket transport item\n\n{}".format(pformat(transport)))
        personality.check_listening_endpoint(personality, transport['endpoint'])
    else:
        if 'endpoint' in transport:
            raise InvalidConfigException("illegal attribute 'endpoint' in Universal transport RawSocket transport subitem\n\n{}".format(pformat(transport)))

    if 'serializers' in transport:
        serializers = transport['serializers']
        if not isinstance(serializers, Sequence):
            raise InvalidConfigException("'serializers' in RawSocket transport configuration must be list ({} encountered)".format(type(serializers)))
        for serializer in serializers:
            if serializer not in [u'json', u'msgpack', u'cbor', u'ubjson']:
                raise InvalidConfigException("invalid value {} for 'serializer' in RawSocket transport configuration - must be one of ['json', 'msgpack', 'cbor', 'ubjson']".format(serializer))

    if 'max_message_size' in transport:
        check_transport_max_message_size(transport['max_message_size'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in RawSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'auth' in transport:
        personality.check_transport_auth(personality, transport['auth'])


def check_connecting_transport_websocket(personality, transport):
    """
    Check a connecting WebSocket-WAMP transport configuration.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/WebSocket-Transport.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'url', 'serializers', 'options']:
            raise InvalidConfigException("encountered unknown attribute '{}' in WebSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in WebSocket transport item\n\n{}".format(pformat(transport)))

    personality.check_connecting_endpoint(personality, transport['endpoint'])

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'serializers' in transport:
        serializers = transport['serializers']
        if not isinstance(serializers, Sequence):
            raise InvalidConfigException("'serializers' in WebSocket transport configuration must be list ({} encountered)".format(type(serializers)))

    if 'url' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'url' in WebSocket transport item\n\n{}".format(pformat(transport)))

    url = transport['url']
    if not isinstance(url, str):
        raise InvalidConfigException("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
    try:
        parse_url(url)
    except InvalidConfigException as e:
        raise InvalidConfigException("invalid 'url' in WebSocket transport configuration : {}".format(e))


def check_connecting_transport_rawsocket(personality, transport):
    """
    Check a connecting RawSocket-WAMP transport configuration.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/RawSocket-Transport.md

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'serializer', 'url', 'debug']:
            raise InvalidConfigException("encountered unknown attribute '{}' in RawSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in RawSocket transport item\n\n{}".format(pformat(transport)))

    personality.check_connecting_endpoint(personality, transport['endpoint'])

    if 'serializer' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'serializer' in RawSocket transport item\n\n{}".format(pformat(transport)))

    serializer = transport['serializer']
    if not isinstance(serializer, str):
        raise InvalidConfigException("'serializer' in RawSocket transport configuration must be a string ({} encountered)".format(type(serializer)))

    if serializer not in ['json', 'msgpack', 'cbor', 'ubjson']:
        raise InvalidConfigException("invalid value {} for 'serializer' in RawSocket transport configuration - must be one of ['json', 'msgpack', 'cbor', 'ubjson']".format(serializer))

    url = transport.get('url', None)
    if url:
        if not isinstance(url, str):
            raise InvalidConfigException("'url' in RawSocket transport configuration must be str ({} encountered)".format(type(url)))
        try:
            from autobahn.rawsocket.util import parse_url as parse_rawsocket_url
            parse_rawsocket_url(url)
        except InvalidConfigException as e:
            raise InvalidConfigException("invalid 'url' in RawSocket transport configuration : {}".format(e))

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise InvalidConfigException("'debug' in RawSocket transport configuration must be boolean ({} encountered)".format(type(debug)))


def check_router_transport(personality, transport, ignore=[]):
    """
    Check router transports.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/Router-Transports.md

    :param transport: Router transport item to check.
    :type transport: dict
    """
    if not isinstance(transport, Mapping):
        raise InvalidConfigException("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

    if 'type' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'type' in component")

    ttype = transport['type']
    if ttype not in [
        'web',
        'websocket',
        'rawsocket',
        'universal',
        'mqtt',
        'flashpolicy',
        'websocket.testee',
        'stream.testee'
    ] + ignore:
        raise InvalidConfigException("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

    if ttype == 'websocket':
        check_listening_transport_websocket(personality, transport)

    elif ttype == 'rawsocket':
        check_listening_transport_rawsocket(personality, transport)

    elif ttype == 'universal':
        check_listening_transport_universal(personality, transport)

    elif ttype == 'web':
        check_listening_transport_web(personality, transport)

    elif ttype == 'mqtt':
        check_listening_transport_mqtt(personality, transport)

    elif ttype == 'flashpolicy':
        check_listening_transport_flashpolicy(personality, transport)

    elif ttype == 'websocket.testee':
        check_listening_transport_websocket_testee(personality, transport)

    elif ttype == 'stream.testee':
        check_listening_transport_stream_testee(personality, transport)

    elif ttype in ignore:
        pass

    else:
        raise InvalidConfigException('logic error')


def check_router_component(personality, component, ignore=[]):
    """
    Check a component configuration for a component running side-by-side with
    a router.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Router-Configuration.md

    :param component: The component configuration.
    :type component: dict
    """
    if not isinstance(component, Mapping):
        raise InvalidConfigException("components must be dictionaries ({} encountered)".format(type(component)))

    if 'type' not in component:
        raise InvalidConfigException("missing mandatory attribute 'type' in component")

    ctype = component['type']
    if ctype not in ['class', 'function'] + ignore:
        raise InvalidConfigException("invalid value '{}' for component type".format(ctype))

    if ctype == 'class':
        check_dict_args({
            'id': (False, [str]),
            'type': (True, [str]),
            'realm': (True, [str]),
            'role': (False, [str]),
            'references': (False, [Sequence]),

            'classname': (True, [str]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    elif ctype == 'function':
        check_dict_args({
            'id': (False, [str]),
            'type': (True, [str]),
            'realm': (True, [str]),
            'role': (False, [str]),

            'callbacks': (False, [dict]),
        }, component, "invalid component configuration")
        if 'callbacks' in component:
            valid_callbacks = ['join', 'leave', 'connect', 'disconnect']
            for name in component['callbacks'].keys():
                if name not in valid_callbacks:
                    raise InvalidConfigException(
                        "Invalid callback name '{}' (valid are: {})".format(
                            name, valid_callbacks
                        )
                    )

    elif ctype in ignore:
        pass

    else:
        raise InvalidConfigException('logic error')


def check_connecting_transport(personality, transport):
    """
    Check container transports.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/router/transport/Transport-Endpoints.md

    :param transport: Container transport item to check.
    :type transport: dict
    """
    if not isinstance(transport, Mapping):
        raise InvalidConfigException("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

    if 'type' not in transport:
        raise InvalidConfigException("missing mandatory attribute 'type' in component")

    ttype = transport['type']
    if ttype not in ['websocket', 'rawsocket']:
        raise InvalidConfigException("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

    if ttype == 'websocket':
        check_connecting_transport_websocket(personality, transport)

    elif ttype == 'rawsocket':
        check_connecting_transport_rawsocket(personality, transport)

    else:
        raise InvalidConfigException('logic error')


def check_container_component(personality, component, ignore=[]):
    """
    Check a container component configuration.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Container-Configuration.md

    :param component: The component configuration to check.
    :type component: dict
    """
    if not isinstance(component, Mapping):
        raise InvalidConfigException("components must be dictionaries ({} encountered)".format(type(component)))

    if 'type' not in component:
        raise InvalidConfigException("missing mandatory attribute 'type' in component")

    ctype = component['type']
    if ctype not in ['class', 'function'] + ignore:
        raise InvalidConfigException("invalid value '{}' for component type".format(ctype))

    if ctype == 'class':
        check_dict_args({
            'id': (False, [str]),
            'type': (True, [str]),
            'realm': (True, [str]),
            'transport': (True, [Mapping]),

            'classname': (True, [str]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    elif ctype == 'function':
        check_dict_args({
            'id': (False, [str]),
            'type': (True, [str]),
            'realm': (True, [str]),
            'transport': (True, [Mapping]),
            'auth': (True, [Mapping]),

            'role': (False, [str]),

            'callbacks': (False, [dict]),
        }, component, "invalid component configuration")
        if 'callbacks' in component:
            valid_callbacks = ['join', 'leave', 'connect', 'disconnect']
            for name in component['callbacks'].keys():
                if name not in valid_callbacks:
                    raise InvalidConfigException(
                        "Invalid callback name '{}' (valid are: {})".format(
                            name, valid_callbacks
                        )
                    )

    elif ctype in ignore:
        pass

    else:
        raise InvalidConfigException('logic error')

    personality.check_connecting_transport(personality, component['transport'])


def check_container_components(personality, components):
    """
    Check components inside a container.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Container-Configuration.md
    """
    if not isinstance(components, Sequence):
        raise InvalidConfigException("'components' items must be lists ({} encountered)".format(type(components)))

    for i, component in enumerate(components):
        log.debug("Checking container component item {item} ..", item=i)
        check_container_component(personality, component)


def check_router_realm(personality, realm, ignore=[]):
    """
    Checks the configuration for a router realm entry, which can be
    *either* a dynamic authorizer or static permissions.
    """
    # router/router.py and router/role.py

    for role in realm.get('roles', []):
        personality.check_router_realm_role(personality, role)

    options = realm.get('options', {})
    if not isinstance(options, Mapping):
        raise InvalidConfigException(
            "Realm 'options' must be a dict"
        )
    for arg, val in options.items():
        if arg not in ['event_dispatching_chunk_size', 'uri_check', 'enable_meta_api', 'bridge_meta_api'] + ignore:
            raise InvalidConfigException(
                "Unknown realm option '{}'".format(arg)
            )
    if 'event_dispatching_chunk_size' in options:
        try:
            edcs = int(options['event_dispatching_chunk_size'])
            if edcs <= 0:
                raise ValueError("too small")
        except ValueError:
            raise InvalidConfigException(
                "Realm option 'event_dispatching_chunk_size' must be a positive int"
            )

    if 'enable_meta_api' in options:
        if not isinstance(options['enable_meta_api'], bool):
            raise InvalidConfigException("Invalid type {} for enable_meta_api in realm options".format(type(options['enable_meta_api'])))

    if 'bridge_meta_api' in options:
        if not isinstance(options['bridge_meta_api'], bool):
            raise InvalidConfigException("Invalid type {} for bridge_meta_api in realm options".format(type(options['bridge_meta_api'])))


def check_router_realm_role(personality, role):
    """
    Checks a single role from a router realm 'roles' list
    """
    if 'authorizer' in role and 'permissions' in role:
        raise InvalidConfigException(
            "Can't specify both 'authorizer' and 'permissions' at once"
        )

    # dynamic authorization
    if 'authorizer' in role:
        auth_uri = role['authorizer']
        check_or_raise_uri(
            auth_uri,
            "invalid dynamic authorizer URI '{}' in role permissions".format(auth_uri),
        )

    # 'static' permissions
    if 'permissions' in role:
        permissions = role['permissions']
        if not isinstance(permissions, Sequence):
            raise InvalidConfigException(
                "'permissions' in 'role' must be a list "
                "({} encountered)".format(type(permissions))
            )

        for role in permissions:
            if not isinstance(role, Mapping):
                raise InvalidConfigException(
                    "each role in 'permissions' must be a dict ({} encountered)".format(type(role))
                )
            for k in ['uri']:
                if k not in role:
                    raise InvalidConfigException(
                        "each role must have '{}' key".format(k)
                    )

            role_uri = role['uri']
            if not isinstance(role_uri, str):
                raise InvalidConfigException("'uri' must be a string")

            if role_uri.endswith('*'):
                role_uri = role_uri[:-1]

            check_dict_args({
                'uri': (True, [str]),
                'match': (False, [str]),
                'allow': (False, [Mapping]),
                'disclose': (False, [Mapping]),
                'cache': (False, [bool]),
            }, role, "invalid grant in role permissions")

            if 'match' in role:
                if role['match'] not in [u'exact', u'prefix', u'wildcard']:
                    raise InvalidConfigException("invalid value '{}' for 'match' attribute in role permissions".format(role['match']))

            if not _URI_PAT_STRICT_LAST_EMPTY.match(role_uri):
                if role.get('match', None) != 'wildcard':
                    raise InvalidConfigException(
                        "invalid role URI '{}' in role permissions".format(role['uri']),
                    )

            if 'allow' in role:
                check_dict_args({
                    'call': (False, [bool]),
                    'register': (False, [bool]),
                    'publish': (False, [bool]),
                    'subscribe': (False, [bool]),
                }, role['allow'], "invalid allow in role permissions")

            if 'disclose' in role:
                check_dict_args({
                    'caller': (False, [bool]),
                    'publisher': (False, [bool]),
                }, role['disclose'], "invalid disclose in role permissions")


def check_router_components(personality, components):
    """
    Check the components that go inside a router.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Router-Configuration.md
    """
    if not isinstance(components, Sequence):
        raise InvalidConfigException("'components' items must be lists ({} encountered)".format(type(components)))

    for i, component in enumerate(components):
        log.debug("Checking router component item {item} ..", item=i)
        personality.check_router_component(personality, component)


def check_transports(personality, transports):
    """
    Transports can only be present in router workers.
    """


def check_router(personality, router, ignore=[]):
    """
    Checks a router worker configuration.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Router-Configuration.md

    :param router: The configuration to check.
    :type router: dict
    """
    for k in router:
        if k not in ['id', 'type', 'options', 'manhole', 'realms', 'transports', 'components', 'connections'] + ignore:
            raise InvalidConfigException("encountered unknown attribute '{}' in router configuration".format(k))

    if 'id' in router:
        check_id(router['id'])

    # check stuff common to all native workers
    #
    if 'manhole' in router:
        personality.check_manhole(personality, router['manhole'])

    if 'options' in router:
        personality.check_router_options(personality, router['options'])

    # realms
    #
    realms = router.get('realms', [])

    if not isinstance(realms, Sequence):
        raise InvalidConfigException("'realms' items must be lists ({} encountered)\n\n{}".format(type(realms), pformat(router)))

    for i, realm in enumerate(realms):
        log.debug("Checking realm item {item} ..", item=i)
        personality.check_router_realm(personality, realm)

    # transports
    #
    transports = router.get('transports', [])
    if not isinstance(transports, Sequence):
        raise InvalidConfigException("'transports' items must be lists ({} encountered)\n\n{}".format(type(transports), pformat(router)))

    for i, transport in enumerate(transports):
        log.debug("Checking transport item {item} ..", item=i)
        personality.check_router_transport(personality, transport)

    # components
    #
    components = router.get('components', [])
    check_router_components(personality, components)


def check_router_options(personality, options):
    check_native_worker_options(personality, options)


def check_container_options(personality, options):
    check_native_worker_options(personality, options, ignore=['shutdown'])
    valid_modes = [u'shutdown-manual', u'shutdown-on-last-component-stopped']
    if 'shutdown' in options:
        if options['shutdown'] not in valid_modes:
            raise InvalidConfigException(
                "'shutdown' must be one of: {}".format(
                    ', '.join(valid_modes)
                )
            )


def check_websocket_testee_options(personality, options):
    check_native_worker_options(personality, options)


def check_manhole(personality, manhole):
    """
    Check a process manhole configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Manhole.md

    :param manhole: The manhole configuration to check.
    :type manhole: dict
    """
    if not isinstance(manhole, Mapping):
        raise InvalidConfigException("'manhole' items must be dictionaries ({} encountered)\n\n{}".format(type(manhole), pformat(manhole)))

    for k in manhole:
        if k not in ['endpoint', 'users']:
            raise InvalidConfigException("encountered unknown attribute '{}' in Manhole configuration".format(k))

    if 'endpoint' not in manhole:
        raise InvalidConfigException("missing mandatory attribute 'endpoint' in Manhole item\n\n{}".format(pformat(manhole)))

    personality.check_listening_endpoint(personality, manhole['endpoint'])

    if 'users' not in manhole:
        raise InvalidConfigException("missing mandatory attribute 'users' in Manhole item\n\n{}".format(pformat(manhole)))

    users = manhole['users']
    if not isinstance(users, Sequence):
        raise InvalidConfigException("'manhole.users' items must be lists ({} encountered)\n\n{}".format(type(users), pformat(users)))

    for user in users:
        if not isinstance(user, Mapping):
            raise InvalidConfigException("'manhole.users.user' items must be dictionaries ({} encountered)\n\n{}".format(type(user), pformat(user)))

        for k in user:
            if k not in ['user', 'password']:
                raise InvalidConfigException("encountered unknown attribute '{}' in manhole.users.user".format(k))

        if 'user' not in user:
            raise InvalidConfigException("missing mandatory attribute 'user' in Manhole user item\n\n{}".format(pformat(user)))

        if 'password' not in user:
            raise InvalidConfigException("missing mandatory attribute 'password' in Manhole user item\n\n{}".format(pformat(user)))


def check_process_env(env):
    """
    Check a worker process environment configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Process-Environments.md

    :param env: The `env` part of the worker options.
    :type env: dict
    """
    if not isinstance(env, Mapping):
        raise InvalidConfigException("'env' in 'options' in worker/guest configuration must be dict ({} encountered)".format(type(env)))

    for k in env:
        if k not in ['inherit', 'vars']:
            raise InvalidConfigException("encountered unknown attribute '{}' in 'options.env' in worker/guest configuration".format(k))

    if 'inherit' in env:
        inherit = env['inherit']
        if isinstance(inherit, bool):
            pass
        elif isinstance(inherit, Sequence):
            for v in inherit:
                if not isinstance(v, str):
                    raise InvalidConfigException("invalid type for inherited env var name in 'inherit' in 'options.env' in worker/guest configuration - must be a string ({} encountered)".format(type(v)))
        else:
            raise InvalidConfigException("'inherit' in 'options.env' in worker/guest configuration must be bool or list ({} encountered)".format(type(inherit)))

    if 'vars' in env:
        envvars = env['vars']
        if not isinstance(envvars, Mapping):
            raise InvalidConfigException("'options.env.vars' in worker/guest configuration must be dict ({} encountered)".format(type(envvars)))

        for k, v in envvars.items():
            if not isinstance(k, str):
                raise InvalidConfigException("invalid type for environment variable key '{}' in 'options.env.vars' - must be a string ({} encountered)".format(k, type(k)))
            if not isinstance(v, str):
                raise InvalidConfigException("invalid type for environment variable value '{}' in 'options.env.vars' - must be a string ({} encountered)".format(v, type(v)))


def check_native_worker_options(personality, options, ignore=[]):
    """
    Check native worker options.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Native-Worker-Options.md

    :param options: The native worker options to check.
    :type options: dict
    """

    if not isinstance(options, Mapping):
        raise InvalidConfigException("'options' in worker configurations must be dictionaries ({} encountered)".format(type(options)))

    for k in options:
        if k not in ['title', 'python', 'pythonpath', 'cpu_affinity',
                     'env', 'expose_controller', 'expose_shared'] + ignore:
            raise InvalidConfigException(
                "encountered unknown attribute '{}' in 'options' in worker"
                " configuration".format(k)
            )

    if 'title' in options:
        title = options['title']
        if not isinstance(title, str):
            raise InvalidConfigException("'title' in 'options' in worker configuration must be a string ({} encountered)".format(type(title)))

    if 'python' in options:
        python = options['python']
        if not isinstance(python, str):
            raise InvalidConfigException("'python' in 'options' in worker configuration must be a string ({} encountered)".format(type(python)))

    if 'pythonpath' in options:
        pythonpath = options['pythonpath']
        if not isinstance(pythonpath, Sequence):
            raise InvalidConfigException("'pythonpath' in 'options' in worker configuration must be lists ({} encountered)".format(type(pythonpath)))
        for p in pythonpath:
            if not isinstance(p, str):
                raise InvalidConfigException("paths in 'pythonpath' in 'options' in worker configuration must be strings ({} encountered)".format(type(p)))

    if 'cpu_affinity' in options:
        cpu_affinity = options['cpu_affinity']
        if not isinstance(cpu_affinity, Sequence):
            raise InvalidConfigException("'cpu_affinity' in 'options' in worker configuration must be lists ({} encountered)".format(type(cpu_affinity)))
        for a in cpu_affinity:
            if not isinstance(a, int):
                raise InvalidConfigException("CPU affinities in 'cpu_affinity' in 'options' in worker configuration must be integers ({} encountered)".format(type(a)))

    if 'env' in options:
        check_process_env(options['env'])

    # this feature requires crossbarfx
    if 'expose_controller' in options:
        expose_controller = options['expose_controller']
        if not isinstance(expose_controller, bool):
            raise InvalidConfigException("'expose_controller' in 'options' in worker configuration must be a boolean ({} encountered)".format(type(expose_controller)))

    # this feature requires crossbarfx
    if 'expose_shared' in options:
        expose_shared = options['expose_shared']
        if not isinstance(expose_shared, bool):
            raise InvalidConfigException("'expose_shared' in 'options' in worker configuration must be a boolean ({} encountered)".format(type(expose_shared)))


def check_websocket_testee(personality, worker):
    """
    Checks a WebSocket testee worker configuration.

    :param worker: The configuration to check.
    :type worker: dict
    """
    for k in worker:
        if k not in ['id', 'type', 'options', 'transport']:
            raise InvalidConfigException("encountered unknown attribute '{}' in WebSocket testee configuration".format(k))

    if 'options' in worker:
        check_websocket_testee_options(personality, worker['options'])

    if 'transport' not in worker:
        raise InvalidConfigException("missing mandatory attribute 'transport' in WebSocket testee configuration")

    check_listening_transport_websocket(personality, worker['transport'])


def check_container(personality, container, ignore=[]):
    """
    Checks a container worker configuration.

    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Container-Configuration.md

    :param router: The configuration to check.
    :type router: dict
    """
    for k in container:
        if k not in ['id', 'type', 'options', 'manhole', 'components', 'connections'] + ignore:
            raise InvalidConfigException("encountered unknown attribute '{}' in container configuration".format(k))

    # check stuff common to all native workers
    #
    if 'manhole' in container:
        personality.check_manhole(personality, container['manhole'])

    if 'options' in container:
        personality.check_container_options(personality, container['options'])

    # components
    #
    components = container.get('components', [])
    check_container_components(personality, components)


def check_guest(personality, guest):
    """
    Check a guest worker configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Guest-Configuration.md
    """
    for k in guest:
        if k not in ['id',
                     'type',
                     'executable',
                     'arguments',
                     'options']:
            raise InvalidConfigException("encountered unknown attribute '{}' in guest worker configuration".format(k))

    check_dict_args({
        'id': (False, [str]),
        'type': (True, [str]),
        'executable': (True, [str]),
        'arguments': (False, [Sequence]),
        'options': (False, [Mapping]),
    }, guest, "Guest process configuration")

    if guest['type'] != 'guest':
        raise InvalidConfigException("invalid value '{}' for type in guest worker configuration".format(guest['type']))

    if 'arguments' in guest:
        for arg in guest['arguments']:
            if not isinstance(arg, str):
                raise InvalidConfigException("invalid type {} for argument in 'arguments' in guest worker configuration".format(type(arg)))

    if 'options' in guest:
        options = guest['options']

        if not isinstance(options, Mapping):
            raise InvalidConfigException("'options' must be dictionaries ({} encountered)\n\n{}".format(type(options), pformat(guest)))

        check_dict_args({
            'env': (False, [Mapping]),
            'workdir': (False, [str]),
            'stdin': (False, [str, Mapping]),
            'stdout': (False, [str]),
            'stderr': (False, [str]),
            'watch': (False, [Mapping]),
        }, options, "Guest process configuration")

        for s in ['stdout', 'stderr']:
            if s in options:
                if options[s] not in ['close', 'log', 'drop']:
                    raise InvalidConfigException("invalid value '{}' for '{}' in guest worker configuration".format(options[s], s))

        if 'stdin' in options:
            if isinstance(options['stdin'], Mapping):
                check_dict_args({
                    'type': (True, [str]),
                    'value': (True, None),
                    'close': (False, [bool]),
                }, options['stdin'], "Guest process 'stdin' configuration")

                # the following configures in which format the value is to be serialized and forwarded
                # to the spawned worker on stdin
                _type = options['stdin']['type']
                _permissible_types = [u'json']

                if options['stdin']['type'] not in _permissible_types:
                    raise InvalidConfigException("invalid value '{}' for 'type' in 'stdin' guest worker configuration - must be one of: {}".format(_type, _permissible_types))
            else:
                if options['stdin'] not in ['close']:
                    raise InvalidConfigException("invalid value '{}' for 'stdin' in guest worker configuration".format(options['stdin']))

        if 'env' in options:
            check_process_env(options['env'])


def check_worker(personality, worker):
    """
    Check a node worker configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/Node-Configuration.md

    :param worker: The worker configuration to check.
    :type worker: dict
    """
    if not isinstance(worker, Mapping):
        raise InvalidConfigException("worker items must be dictionaries ({} encountered)\n\n{}".format(type(worker), pformat(worker)))

    if 'type' not in worker:
        raise InvalidConfigException("missing mandatory attribute 'type' in worker item\n\n{}".format(pformat(worker)))

    worker_type = worker['type']

    valid_worker_types = ['guest'] + list(personality.native_workers.keys())

    if worker_type not in valid_worker_types:
        raise InvalidConfigException('invalid worker type "{}" in worker configuration item (valid types are: {})'.format(worker_type, valid_worker_types))

    # handle all non-native worker types (currently only "guest")
    if worker_type == 'guest':
        personality.check_guest(personality, worker)
    else:
        # all native worker types:
        # default: router, container, websocket-testee
        # but also (crossbarfx): proxy, hostmonitor, xbr, ..
        worker_plugin = personality.native_workers[worker_type]
        check_worker = worker_plugin['checkconfig_item']
        check_worker(personality, worker)


def check_controller_options(personality, options, ignore=[]):
    """
    Check controller options.

    :param options: The options to check.
    :type options: dict
    """
    if not isinstance(options, Mapping):
        raise InvalidConfigException("'options' in controller configuration must be a dictionary ({} encountered)\n\n{}".format(type(options)))

    for k in options:
        if k not in ['title', 'shutdown', 'enable_parallel_worker_start'] + ignore:
            raise InvalidConfigException("encountered unknown attribute '{}' in 'options' in controller configuration".format(k))

    if 'title' in options:
        title = options['title']
        if not isinstance(title, str):
            raise InvalidConfigException("'title' in 'options' in controller configuration must be a string ({} encountered)".format(type(title)))

    if 'shutdown' in options:
        if not isinstance(options['shutdown'], Sequence) or isinstance(options['shutdown'], str):
            raise InvalidConfigException("invalid type {} for 'shutdown' in node controller options (must be a list)".format(type(options['shutdown'])))
        for shutdown_mode in options['shutdown']:
            if shutdown_mode not in NODE_SHUTDOWN_MODES:
                raise InvalidConfigException("invalid value '{}' for shutdown mode in controller options (permissible values: {})".format(shutdown_mode, ', '.join("'{}'".format(x) for x in NODE_SHUTDOWN_MODES)))

    if 'enable_parallel_worker_start' in options:
        enable_parallel_worker_start = options['enable_parallel_worker_start']
        if type(enable_parallel_worker_start) != bool:
            raise InvalidConfigException(
                "'enable_parallel_worker_start' in 'options' in controller configuration must be a bool ({} encountered)".format(
                    type(enable_parallel_worker_start)))


def check_controller(personality, controller, ignore=[]):
    """
    Check a node controller configuration item.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/worker/Controller-Configuration.md

    :param controller: The controller configuration to check.
    :type controller: dict
    """
    if not isinstance(controller, Mapping):
        raise InvalidConfigException("controller items must be dictionaries ({} encountered)\n\n{}".format(type(controller), pformat(controller)))

    for k in controller:
        if k not in ['id', 'options', 'manhole', 'connections'] + ignore:
            raise InvalidConfigException("encountered unknown attribute '{}' in controller configuration".format(k))

    if 'id' in controller:
        check_id(controller['id'])

    if 'options' in controller:
        personality.check_controller_options(personality, controller['options'])

    if 'manhole' in controller:
        personality.check_manhole(personality, controller['manhole'])


def check_config(personality, config):
    """
    Check a Crossbar.io top-level configuration.

    http://crossbar.io/docs/
    https://github.com/crossbario/crossbar/blob/master/docs/pages/administration/Node-Configuration.md

    :param config: The configuration to check.
    :type config: dict
    """
    if not isinstance(config, Mapping):
        raise InvalidConfigException("top-level configuration item must be a dictionary ({} encountered)".format(type(config)))

    for k in config:
        if k not in ['$schema', 'version', 'controller', 'workers']:
            raise InvalidConfigException("encountered unknown attribute '{}' in top-level configuration".format(k))

    version = config.get(u'version', 1)
    if version not in range(1, LATEST_CONFIG_VERSION + 1):
        raise InvalidConfigException("Invalid configuration version '{}' - must be 1..{}".format(version, LATEST_CONFIG_VERSION))

    if version < LATEST_CONFIG_VERSION:
        raise InvalidConfigException("Configuration too old: version {}, while current is {} - please upgrade using 'crossbar upgrade'".format(version, LATEST_CONFIG_VERSION))

    # check controller config
    #
    if 'controller' in config:
        log.debug("Checking controller item ..")
        personality.check_controller(personality, config['controller'])

    # check worker configs
    #
    workers = config.get('workers', [])
    if not isinstance(workers, Sequence):
        raise InvalidConfigException("'workers' attribute in top-level configuration must be a list ({} encountered)".format(type(workers)))

    for i, worker in enumerate(workers):
        log.debug("Checking worker item {item} ..", item=i)
        personality.check_worker(personality, worker)


def check_config_file(personality, configfile):
    """
    Check a Crossbar.io local configuration file.

    :param configfile: The file to check.
    :type configfile: str
    """
    configext = os.path.splitext(configfile)[1]
    configfile = os.path.abspath(configfile)

    if configext not in ['.json', '.yaml']:
        raise Exception("invalid configuration file extension '{}'".format(configext))

    with open(configfile, 'r') as infile:
        if configext == '.json':
            try:
                config = json.load(infile, object_pairs_hook=OrderedDict)
            except ValueError as e:
                raise InvalidConfigException("configuration file does not seem to be proper JSON ('{}')".format(e))
        elif configext == '.yaml':
            try:
                config = yaml.safe_load(infile)
            except InvalidConfigException as e:
                raise InvalidConfigException("configuration file does not seem to be proper YAML ('{}')".format(e))
        else:
            raise Exception('logic error')

    personality.check_config(personality, config)

    return config


def convert_config_file(personality, configfile):
    """
    Converts a Crossbar.io configuration file from JSON to YAML or from
    YAML to JSON.

    :param configfile: The Crossbar.io node configuration file to convert.
    :type configfile: str
    """
    # deny conversion of an invalid configuration
    personality.check_config_file(personality, configfile)

    configbase, configext = os.path.splitext(configfile)
    configfile = os.path.abspath(configfile)

    with open(configfile, 'r') as infile:
        if configext == '.yaml':
            log.info("converting YAML configuration {cfg} to JSON ...", cfg=configfile)
            try:
                config = yaml.safe_load(infile)
            except Exception as e:
                raise InvalidConfigException("configuration file does not seem to be proper YAML ('{}')".format(e))
            else:
                newconfig = os.path.abspath(configbase + '.json')
                with open(newconfig, 'w') as outfile:
                    json.dump(config, outfile, ensure_ascii=False, separators=(',', ': '), indent=3, sort_keys=True)
                    log.info("ok, JSON formatted configuration written to {cfg}", cfg=newconfig)
        elif configext == ".json":
            log.info("converting JSON formatted configuration {cfg} to YAML format ...", cfg=configfile)
            try:
                config = json.load(infile, object_pairs_hook=OrderedDict)
            except ValueError as e:
                raise InvalidConfigException("configuration file does not seem to be proper JSON ('{}')".format(e))
            else:
                newconfig = os.path.abspath(configbase + '.yaml')
                with open(newconfig, 'w') as outfile:
                    yaml.safe_dump(config, outfile, default_flow_style=False)
                    log.info("ok, YAML formatted configuration written to {cfg}", cfg=newconfig)
        else:
            raise InvalidConfigException("configuration file needs to be '.json' or '.yaml'.")


def _fill_config_from_env(config, keys=None):
    """
    Fill in configuration values in a configuration dictionary from
    environment variables.

    :param config: The configuration item within which to replace values.
    :type config: dict
    :param keys: A list of keys for which to try to replace values or `None`
       to replace values for all keys in the configuration item.
    :type keys: list of str or None
    """
    if keys is None:
        keys = config.keys()

    for k in keys:
        if k in config:
            if isinstance(config[k], str):
                match = _ENV_VAR_PAT.match(config[k])
                if match and match.groups():
                    envvar = match.groups()[0]
                    if envvar in os.environ:
                        val = os.environ[envvar]
                        config[k] = val
                        log.debug("configuration parameter '{key}' set to '{val}' from environment variable {envvar}", key=k, val=val, envvar=envvar)
                    else:
                        log.debug("warning: configuration parameter '{key}' should have been read from enviroment variable {envvar}, but the latter is not set", key=k, envvar=envvar)


def upgrade_config_file(personality, configfile):
    """
    Upgrade a local node configuration file.

    :param configfile: Path to the node config file to upgrade.
    :type configfile: unicode
    """
    configext = os.path.splitext(configfile)[1]
    configfile = os.path.abspath(configfile)

    if configext not in ['.json', '.yaml']:
        raise Exception("invalid configuration file extension '{}'".format(configext))

    # read and parse existing config file
    with open(configfile, 'r') as infile:
        # existing config has JSON format
        if configext == '.json':
            try:
                config = json.load(infile, object_pairs_hook=OrderedDict)
            except ValueError as e:
                raise InvalidConfigException("configuration file does not seem to be proper JSON: {}".format(e))

        # existing config has YAML format
        elif configext == '.yaml':
            try:
                config = yaml.safe_load(infile)
            except ValueError as e:
                raise InvalidConfigException("configuration file does not seem to be proper YAML: {}".format(e))

        # should not arrive here
        else:
            raise Exception('logic error')

    if not isinstance(config, Mapping):
        raise InvalidConfigException("configuration top-level item must be a dict/mapping (was type {})".format(type(config), config))

    if u'version' in config:
        version = config[u'version']
    else:
        version = 1

    LATEST_CONFIG_VERSION = 2

    if version >= LATEST_CONFIG_VERSION:
        print("Configuration already is at latest version {} - nothing to upgrade".format(LATEST_CONFIG_VERSION))
        return

    # stepwise upgrade from version to version up to current ..
    while version < LATEST_CONFIG_VERSION:
        print("Upgrading configuration from version {} to version {}".format(version, version + 1))

        # upgrade from version 1 -> 2
        if version == 1:
            for worker in config.get(u'workers', []):
                if worker[u'type'] == u'router':
                    for realm in worker.get(u'realms', []):
                        for role in realm.get(u'roles', []):
                            # upgrade "permissions" subitem (if there is any)
                            if u'permissions' in role:
                                permissions = []
                                for p in role[u'permissions']:
                                    uri, match = convert_starred_uri(p[u'uri'])
                                    pp = OrderedDict([
                                        (u'uri', uri),
                                        (u'match', match),
                                        (u'allow', OrderedDict([
                                            (u'call', p.get(u'call', False)),
                                            (u'register', p.get(u'register', False)),
                                            (u'publish', p.get(u'publish', False)),
                                            (u'subscribe', p.get(u'subscribe', False))
                                        ])),
                                        (u'disclose', OrderedDict([
                                            (u'caller', False),
                                            (u'publisher', False),
                                        ])),
                                        (u'cache', True)
                                    ])
                                    permissions.append(pp)
                                role[u'permissions'] = permissions
        else:
            raise Exception('logic error')

        version += 1

    # make sure the config version is there, and at top of config
    config = OrderedDict([(u'version', version)] + list(config.items()))

    # write out updated configuration ..
    with open(configfile, 'wb') as outfile:
        # write config in JSON format
        if configext == '.json':
            data = json.dumps(
                config,
                skipkeys=False,
                sort_keys=False,
                ensure_ascii=False,
                separators=(',', ': '),
                indent=4,
            )
            # ensure newline at end of file
            data += u'\n'
            outfile.write(data.encode('utf8'))

        # write config in YAML format
        elif configext == '.yaml':
            yaml.safe_dump(config, outfile, default_flow_style=False)

        # should not arrive here
        else:
            raise Exception('logic error')
