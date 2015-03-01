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

from __future__ import absolute_import

import os
import json
import re
import six

from pprint import pformat

from autobahn.websocket.protocol import parseWsUrl

from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY
# from autobahn.wamp.message import _URI_PAT_LOOSE_NON_EMPTY

import yaml
from yaml import Loader, SafeLoader

__all__ = ('check_config',
           'check_config_file',
           'convert_config_file',
           'check_guest')


# Hack: force PyYAML to parse _all_ strings into Unicode (as we want for CB configs)
#
# http://stackoverflow.com/a/2967461/884770
#
def construct_yaml_str(self, node):
    return self.construct_scalar(node)

Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)


_ENV_VAR_PAT_STR = "^\$([A-Z0-9_]+)$"
_ENV_VAR_PAT = re.compile(_ENV_VAR_PAT_STR)


def _readenv(var, msg):
    match = _ENV_VAR_PAT.match(var)
    if match and match.groups():
        envvar = match.groups()[0]
        if envvar in os.environ:
            return os.environ[envvar]
        else:
            raise Exception("{} - enviroment variable '{}' not set".format(msg, var))
    else:
        raise Exception("{} - environment variable name '{}' does not match pattern '{}'".format(msg, var, _ENV_VAR_PAT_STR))


_CONFIG_ITEM_ID_PAT_STR = "^[a-z][a-z0-9_]{2,11}$"
_CONFIG_ITEM_ID_PAT = re.compile(_CONFIG_ITEM_ID_PAT_STR)


def check_id(id):
    """
    Check a configuration item ID.
    """
    if not isinstance(id, six.text_type):
        raise Exception("invalid configuration item ID '{}' - type must be string, was ".format(id, type(id)))
    if not _CONFIG_ITEM_ID_PAT.match(id):
        raise Exception("invalid configuration item ID '{}' - must match regular expression {}".format(id, _CONFIG_ITEM_ID_PAT_STR))


_REALM_NAME_PAT_STR = r"^[A-Za-z][A-Za-z0-9_\-@\.]{2,254}$"
_REALM_NAME_PAT = re.compile(_REALM_NAME_PAT_STR)


def check_realm_name(name):
    """
    Check a realm name.
    """
    if not isinstance(name, six.text_type):
        raise Exception("invalid realm name '{}' - type must be string, was ".format(name, type(name)))
    if not _REALM_NAME_PAT.match(name):
        raise Exception("invalid realm name '{}' - must match regular expression {}".format(name, _REALM_NAME_PAT_STR))


def check_dict_args(spec, config, msg):
    if not isinstance(config, dict):
        raise Exception("{} - invalid type for configuration item - expected dict, got {}".format(msg, type(config)))
    for k in config:
        if k not in spec:
            raise Exception("{} - encountered unknown attribute '{}'".format(msg, k))
        if spec[k][1] and type(config[k]) not in spec[k][1]:
            raise Exception("{} - invalid {} encountered for attribute '{}'".format(msg, type(config[k]), k))
    mandatory_keys = [k for k in spec if spec[k][0]]
    for k in mandatory_keys:
        if k not in config:
            raise Exception("{} - missing mandatory attribute '{}'".format(msg, k))


def check_or_raise_uri(value, message):
    if not isinstance(value, six.text_type):
        raise Exception("{}: invalid type {} for URI".format(message, type(value)))
    # if not _URI_PAT_LOOSE_NON_EMPTY.match(value):
    if not _URI_PAT_STRICT_NON_EMPTY.match(value):
        raise Exception("{}: invalid value '{}' for URI".format(message, value))
    return value


def check_transport_auth_ticket(config):
    """
    Check a Ticket-based authentication configuration item.
    """
    if 'type' not in config:
        raise Exception("missing mandatory attribute 'type' in Ticket-based authentication configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise Exception("invalid type '{}' for Ticket-based authentication type - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        if 'principals' not in config:
            raise Exception("missing mandatory attribute 'principals' in static Ticket-based authentication configuration")
        if not isinstance(config['principals'], dict):
            raise Exception("invalid type for attribute 'principals' in static Ticket-based authentication configuration - expected dict, got {}".format(type(config['users'])))
        for u, principal in config['principals'].items():
            check_dict_args({
                'ticket': (True, [six.text_type]),
                'role': (False, [six.text_type]),
            }, principal, "Ticket-based authentication configuration - principal '{}' configuration".format(u))

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise Exception("missing mandatory attribute 'authenticator' in dynamic Ticket-based authentication configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic Ticket-based authentication configuration".format(config['authenticator']))
    else:
        raise Exception("logic error")


def check_transport_auth_wampcra(config):
    """
    Check a WAMP-CRA configuration item.
    """
    if 'type' not in config:
        raise Exception("missing mandatory attribute 'type' in WAMP-CRA configuration")

    if config['type'] not in ['static', 'dynamic']:
        raise Exception("invalid type '{}' for WAMP-CRA authentication type - must be one of 'static', 'dynamic'".format(config['type']))

    if config['type'] == 'static':
        if 'users' not in config:
            raise Exception("missing mandatory attribute 'users' in static WAMP-CRA configuration")
        if not isinstance(config['users'], dict):
            raise Exception("invalid type for attribute 'users' in static WAMP-CRA configuration - expected dict, got {}".format(type(config['users'])))
        for u, user in config['users'].items():
            check_dict_args({
                'secret': (True, [six.text_type]),
                'role': (False, [six.text_type]),
                'salt': (False, [six.text_type]),
                'iterations': (False, six.integer_types),
                'keylen': (False, six.integer_types)
            }, user, "WAMP-CRA user '{}' configuration".format(u))

    elif config['type'] == 'dynamic':
        if 'authenticator' not in config:
            raise Exception("missing mandatory attribute 'authenticator' in dynamic WAMP-CRA configuration")
        check_or_raise_uri(config['authenticator'], "invalid authenticator URI '{}' in dynamic WAMP-CRA configuration".format(config['authenticator']))
    else:
        raise Exception("logic error")


def check_transport_auth_anonymous(config):
    """
    Check a WAMP-Anonymous configuration item.
    """
    check_dict_args({
        'role': (False, [six.text_type]),
    }, config, "WAMP-Anonymous configuration")


def check_transport_auth(auth):
    """
    Check a WAMP transport authentication configuration.
    """
    if not isinstance(auth, dict):
        raise Exception("invalid type {} for authentication configuration item (dict expected)".format(type(auth)))
    CHECKS = {
        'anonymous': check_transport_auth_anonymous,
        'ticket': check_transport_auth_ticket,
        'wampcra': check_transport_auth_wampcra,
    }
    for k in auth:
        if k not in CHECKS:
            raise Exception("invalid authentication method key '{}' - must be one of {}".format(k, CHECKS.keys()))
        CHECKS[k](auth[k])


def check_endpoint_backlog(backlog):
    """
    Check listening endpoint backlog parameter.

    :param backlog: The backlog parameter for listening endpoints to check.
    :type backlog: int
    """
    if type(backlog) not in six.integer_types:
        raise Exception("'backlog' attribute in endpoint must be int ({} encountered)".format(type(backlog)))
    if backlog < 1 or backlog > 65535:
        raise Exception("invalid value {} for 'backlog' attribute in endpoint (must be from [1, 65535])".format(backlog))


def check_endpoint_port(port, message="listening/connection endpoint"):
    """
    Check a listening/connecting endpoint TCP port.

    :param port: The port to check.
    :type port: int
    """
    if type(port) not in six.integer_types:
        raise Exception("'port' attribute in {} must be integer ({} encountered)".format(message, type(port)))
    if port < 1 or port > 65535:
        raise Exception("invalid value {} for 'port' attribute in {}".format(port, message))


def check_endpoint_ip_version(version):
    """
    Check a listening/connecting endpoint TCP version.

    :param version: The version to check.
    :type version: int
    """
    if type(version) not in six.integer_types:
        raise Exception("'version' attribute in endpoint must be integer ({} encountered)".format(type(version)))
    if version not in [4, 6]:
        raise Exception("invalid value {} for 'version' attribute in endpoint".format(version))


def check_endpoint_timeout(timeout):
    """
    Check a connecting endpoint timeout parameter.

    :param timeout: The timeout to check.
    :type timeout: int
    """
    if type(timeout) not in six.integer_types:
        raise Exception("'timeout' attribute in endpoint must be integer ({} encountered)".format(type(timeout)))
    if timeout < 0 or timeout > 600:
        raise Exception("invalid value {} for 'timeout' attribute in endpoint".format(timeout))


def check_transport_max_message_size(max_message_size):
    """
    Check maxmimum message size parameter in RawSocket and WebSocket transports.

    :param max_message_size: The maxmimum message size parameter to check.
    :type max_message_size: int
    """
    if type(max_message_size) not in six.integer_types:
        raise Exception("'max_message_size' attribute in transport must be int ({} encountered)".format(type(max_message_size)))
    if max_message_size < 1 or max_message_size > 64 * 1024 * 1024:
        raise Exception("invalid value {} for 'max_message_size' attribute in transport (must be from [1, 64MB])".format(max_message_size))


def check_listening_endpoint_tls(tls):
    """
    Check a listening endpoint TLS configuration.

    :param tls: The TLS configuration part of a listening endpoint.
    :type tls: dict
    """
    if not isinstance(tls, dict):
        raise Exception("'tls' in endpoint must be dictionary ({} encountered)".format(type(tls)))

    for k in tls:
        if k not in ['key', 'certificate', 'dhparam', 'ciphers']:
            raise Exception("encountered unknown attribute '{}' in listening endpoint TLS configuration".format(k))

    for k in [('key', True), ('certificate', True), ('dhparam', False), ('ciphers', False)]:

        if k[1] and not k[0] in tls:
            raise Exception("missing mandatory attribute '{}' in listening endpoint TLS configuration".format(k[0]))

        if k[0] in tls:
            if not isinstance(tls[k[0]], six.text_type):
                raise Exception("'{}' in listening endpoint TLS configuration must be string ({} encountered)".format(k[0], type(tls[k[0]])))


def check_connecting_endpoint_tls(tls):
    """
    Check a connecting endpoint TLS configuration.

    :param tls: The TLS configuration part of a connecting endpoint.
    :type tls: dict
    """
    if not isinstance(tls, dict):
        raise Exception("'tls' in endpoint must be dictionary ({} encountered)".format(type(tls)))

    for k in tls:
        if k not in []:
            raise Exception("encountered unknown attribute '{}' in listening endpoint TLS configuration".format(k))


def check_listening_endpoint_tcp(endpoint):
    """
    Check a TCP listening endpoint configuration.

    :param endpoint: The TCP listening endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'version', 'port', 'shared', 'interface', 'backlog', 'tls']:
            raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

    if 'port' not in endpoint:
        raise Exception("missing mandatory attribute 'port' in listening endpoint item\n\n{}".format(pformat(endpoint)))

    if type(endpoint['port']) in (str, unicode):
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
            raise Exception("'shared' attribute in endpoint must be bool ({} encountered)".format(type(shared)))

    if 'tls' in endpoint:
        check_listening_endpoint_tls(endpoint['tls'])

    if 'interface' in endpoint:
        interface = endpoint['interface']
        if not isinstance(interface, six.text_type):
            raise Exception("'interface' attribute in endpoint must be string ({} encountered)".format(type(interface)))

    if 'backlog' in endpoint:
        check_endpoint_backlog(endpoint['backlog'])


def check_listening_endpoint_unix(endpoint):
    """
    Check a Unix listening endpoint configuration.

    :param endpoint: The Unix listening endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'path', 'backlog']:
            raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

    if 'path' not in endpoint:
        raise Exception("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

    path = endpoint['path']
    if not isinstance(path, six.text_type):
        raise Exception("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

    if 'backlog' in endpoint:
        check_endpoint_backlog(endpoint['backlog'])


def check_connecting_endpoint_tcp(endpoint):
    """
    Check a TCP connecting endpoint configuration.

    :param endpoint: The TCP connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'version', 'host', 'port', 'timeout', 'tls']:
            raise Exception("encountered unknown attribute '{}' in connecting endpoint".format(k))

    if 'host' not in endpoint:
        raise Exception("missing mandatory attribute 'host' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

    if 'port' not in endpoint:
        raise Exception("missing mandatory attribute 'port' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

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

    :param endpoint: The Unix connecting endpoint to check.
    :type endpoint: dict
    """
    for k in endpoint:
        if k not in ['type', 'path', 'timeout']:
            raise Exception("encountered unknown attribute '{}' in connecting endpoint".format(k))

    if 'path' not in endpoint:
        raise Exception("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

    path = endpoint['path']
    if not isinstance(path, six.text_type):
        raise Exception("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

    if 'timeout' in endpoint:
        check_endpoint_timeout(endpoint['timeout'])


def check_listening_endpoint(endpoint):
    """
    Check a listening endpoint configuration.

    :param endpoint: The listening endpoint configuration.
    :type endpoint: dict
    """
    if not isinstance(endpoint, dict):
        raise Exception("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

    if 'type' not in endpoint:
        raise Exception("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

    etype = endpoint['type']
    if etype not in ['tcp', 'unix']:
        raise Exception("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

    if etype == 'tcp':
        check_listening_endpoint_tcp(endpoint)
    elif etype == 'unix':
        check_listening_endpoint_unix(endpoint)
    else:
        raise Exception("logic error")


def check_connecting_endpoint(endpoint):
    """
    Check a conencting endpoint configuration.

    :param endpoint: The connecting endpoint configuration.
    :type endpoint: dict
    """
    if not isinstance(endpoint, dict):
        raise Exception("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

    if 'type' not in endpoint:
        raise Exception("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

    etype = endpoint['type']
    if etype not in ['tcp', 'unix']:
        raise Exception("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

    if etype == 'tcp':
        check_connecting_endpoint_tcp(endpoint)
    elif etype == 'unix':
        check_connecting_endpoint_unix(endpoint)
    else:
        raise Exception("logic error")


def check_websocket_options(options):
    """
    Check WebSocket / WAMP-WebSocket protocol options.

    :param options: The options to check.
    :type options: dict
    """
    if not isinstance(options, dict):
        raise Exception("WebSocket options must be a dictionary ({} encountered)".format(type(options)))

    for k in options:
        if k not in [
            # WebSocket options
            'allowed_origins',
            'external_port',
            'enable_hixie76',
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
            'require_websocket_subprotocol'
        ]:
            raise Exception("encountered unknown attribute '{}' in WebSocket options".format(k))

    # FIXME: more complete checking ..


def check_web_path_service_websocket(config):
    """
    Check a "websocket" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'url': (False, [six.text_type]),
        'serializers': (False, [list]),
        'auth': (False, [dict]),
        'options': (False, [dict]),
        'debug': (False, [bool])
    }, config, "Web transport 'WebSocket' path service")

    if 'options' in config:
        check_websocket_options(config['options'])

    if 'debug' in config:
        debug = config['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in WebSocket configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in config:
        url = config['url']
        if not isinstance(url, six.text_type):
            raise Exception("'url' in WebSocket configuration must be str ({} encountered)".format(type(url)))
        try:
            parseWsUrl(url)
        except Exception as e:
            raise Exception("invalid 'url' in WebSocket configuration : {}".format(e))

    if 'auth' in config:
        check_transport_auth(config['auth'])


def check_web_path_service_static(config):
    """
    Check a "static" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'directory': (False, [six.text_type]),
        'package': (False, [six.text_type]),
        'resource': (False, [six.text_type]),
        'options': (False, [dict])
    }, config, "Web transport 'static' path service")

    if 'directory' in config:
        if 'package' in config or 'resource' in config:
            raise Exception("Web transport 'static' path service: either 'directory' OR 'package' + 'resource' must be given, not both")
    else:
        if 'package' not in config or 'resource' not in config:
            raise Exception("Web transport 'static' path service: either 'directory' OR 'package' + 'resource' must be given, not both")

    if 'options' in config:
        check_dict_args({
            'enable_directory_listing': (False, [bool]),
            'mime_types': (False, [dict]),
            'cache_timeout': (False, list(six.integer_types) + [type(None)])
        }, config['options'], "'options' in Web transport 'static' path service")


def check_web_path_service_wsgi(config):
    """
    Check a "wsgi" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'module': (True, [six.text_type]),
        'object': (True, [six.text_type])
    }, config, "Web transport 'wsgi' path service")


def check_web_path_service_redirect(config):
    """
    Check a "redirect" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'url': (True, [six.text_type])
    }, config, "Web transport 'redirect' path service")


def check_web_path_service_json(config):
    """
    Check a "json" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'value': (True, None)
    }, config, "Web transport 'json' path service")


def check_web_path_service_cgi(config):
    """
    Check a "cgi" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'directory': (True, [six.text_type]),
        'processor': (True, [six.text_type]),
    }, config, "Web transport 'cgi' path service")


def check_web_path_service_longpoll(config):
    """
    Check a "longpoll" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'options': (False, [dict]),
    }, config, "Web transport 'longpoll' path service")

    if 'options' in config:
        check_dict_args({
            'debug': (False, [bool]),
            'debug_transport_id': (False, [six.text_type]),
            'request_timeout': (False, six.integer_types),
            'session_timeout': (False, six.integer_types),
            'queue_limit_bytes': (False, six.integer_types),
            'queue_limit_messages': (False, six.integer_types),
        }, config['options'], "Web transport 'longpoll' path service")


def check_web_path_service_pusher_post_body_limit(limit):
    """
    Check a pusher web path service "post_body_limit" parameter.

    :param port: The limit to check.
    :type port: int
    """
    if type(limit) not in six.integer_types:
        raise Exception("'post_body_limit' attribute in pusher configuration must be integer ({} encountered)".format(type(limit)))
    if limit < 0 or limit > 2**20:
        raise Exception("invalid value {} for 'post_body_limit' attribute in pusher configuration".format(limit))


def check_web_path_service_pusher_timestamp_delta_limit(limit):
    """
    Check a pusher web path service "timestamp_delta_limit" parameter.

    :param port: The limit to check.
    :type port: int
    """
    if type(limit) not in six.integer_types:
        raise Exception("'timestamp_delta_limit' attribute in pusher configuration must be integer ({} encountered)".format(type(limit)))
    if limit < 0 or limit > 86400:
        raise Exception("invalid value {} for 'timestamp_delta_limit' attribute in pusher configuration".format(limit))


def check_web_path_service_pusher(config):
    """
    Check a "pusher" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'realm': (True, [six.text_type]),
        'role': (True, [six.text_type]),
        'options': (False, [dict]),
    }, config, "Web transport 'pusher' path service")

    if 'options' in config:
        check_dict_args({
            'debug': (False, [bool]),
            'key': (False, [six.text_type]),
            'secret': (False, [six.text_type]),
            'require_tls': (False, [bool]),
            'require_ip': (False, [list]),
            'post_body_limit': (False, six.integer_types),
            'timestamp_delta_limit': (False, six.integer_types),
        }, config['options'], "Web transport 'pusher' path service")

        if 'post_body_limit' in config['options']:
            check_web_path_service_pusher_post_body_limit(config['options']['post_body_limit'])

        if 'timestamp_delta_limit' in config['options']:
            check_web_path_service_pusher_timestamp_delta_limit(config['options']['timestamp_delta_limit'])


def check_web_path_service_schemadoc(config):
    # FIXME
    pass


def check_web_path_service_path(config):
    """
    Check a "path" path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    """
    check_dict_args({
        'type': (True, [six.text_type]),
        'paths': (True, [dict]),
    }, config, "Web transport 'path' path service")

    # check nested paths
    #
    check_paths(config['paths'], nested=True)


def check_web_path_service(path, config, nested):
    """
    Check a single path service on Web transport.

    :param config: The path service configuration.
    :type config: dict
    :param nested: Whether this is a nested path.
    :type nested: bool
    """
    if 'type' not in config:
        raise Exception("missing mandatory attribute 'type' in Web transport path service '{}' configuration\n\n{}".format(path, config))

    ptype = config['type']
    if path == '/' and not nested:
        if ptype not in ['static', 'wsgi', 'redirect', 'pusher']:
            raise Exception("invalid type '{}' for root-path service in Web transport path service '{}' configuration\n\n{}".format(ptype, path, config))
    else:
        if ptype not in ['websocket', 'static', 'wsgi', 'redirect', 'json', 'cgi', 'longpoll', 'pusher', 'schemadoc', 'path']:
            raise Exception("invalid type '{}' for sub-path service in Web transport path service '{}' configuration\n\n{}".format(ptype, path, config))

    checkers = {
        'websocket': check_web_path_service_websocket,
        'static': check_web_path_service_static,
        'wsgi': check_web_path_service_wsgi,
        'redirect': check_web_path_service_redirect,
        'json': check_web_path_service_json,
        'cgi': check_web_path_service_cgi,
        'longpoll': check_web_path_service_longpoll,
        'pusher': check_web_path_service_pusher,
        'schemadoc': check_web_path_service_schemadoc,
        'path': check_web_path_service_path,
    }

    checkers[ptype](config)


def check_listening_transport_web(transport):
    """
    Check a listening Web-WAMP transport configuration.

    :param transport: The Web transport configuration to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'paths', 'options']:
            raise Exception("encountered unknown attribute '{}' in Web transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in Web transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'paths' not in transport:
        raise Exception("missing mandatory attribute 'paths' in Web transport item\n\n{}".format(pformat(transport)))

    paths = transport['paths']
    if not isinstance(paths, dict):
        raise Exception("'paths' attribute in Web transport configuration must be dictionary ({} encountered)".format(type(paths)))

    if '/' not in paths:
        raise Exception("missing mandatory path '/' in 'paths' in Web transport configuration")

    check_paths(paths)

    if 'options' in transport:
        options = transport['options']
        if not isinstance(options, dict):
            raise Exception("'options' in Web transport must be dictionary ({} encountered)".format(type(options)))

        if 'access_log' in options:
            access_log = options['access_log']
            if not isinstance(access_log, bool):
                raise Exception("'access_log' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(access_log)))

        if 'display_tracebacks' in options:
            display_tracebacks = options['display_tracebacks']
            if not isinstance(display_tracebacks, bool):
                raise Exception("'display_tracebacks' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(display_tracebacks)))

        if 'hsts' in options:
            hsts = options['hsts']
            if not isinstance(hsts, bool):
                raise Exception("'hsts' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(hsts)))

        if 'hsts_max_age' in options:
            hsts_max_age = options['hsts_max_age']
            if type(hsts_max_age) not in six.integer_types:
                raise Exception("'hsts_max_age' attribute in 'options' in Web transport must be integer ({} encountered)".format(type(hsts_max_age)))
            if hsts_max_age < 0:
                raise Exception("'hsts_max_age' attribute in 'options' in Web transport must be non-negative ({} encountered)".format(hsts_max_age))

        if 'hixie76_aware' in options:
            hixie76_aware = options['hixie76_aware']
            if not isinstance(hixie76_aware, bool):
                raise Exception("'hixie76_aware' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(hixie76_aware)))


_WEB_PATH_PAT_STR = "^([a-z0-9A-Z]+|/)$"
_WEB_PATH_PATH = re.compile(_WEB_PATH_PAT_STR)


def check_paths(paths, nested=False):
    """
    Checks all configured paths.

    :param paths: Configured paths to check.
    :type paths: dict
    :param nested: Whether this is a nested path.
    :type nested: bool
    """
    for p in paths:
        if not isinstance(p, six.text_type):
            raise Exception("keys in 'paths' in Web transport configuration must be strings ({} encountered)".format(type(p)))

        if not _WEB_PATH_PATH.match(p):
            raise Exception("invalid value '{}' for path in Web transport configuration - must match regular expression {}".format(p, _WEB_PATH_PAT_STR))

        check_web_path_service(p, paths[p], nested)


def check_listening_transport_websocket(transport):
    """
    Check a listening WebSocket-WAMP transport configuration.

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
           'auth']:
            raise Exception("encountered unknown attribute '{}' in WebSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in WebSocket transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'serializers' in transport:
        serializers = transport['serializers']
        if not isinstance(serializers, list):
            raise Exception("'serializers' in WebSocket transport configuration must be list ({} encountered)".format(type(serializers)))

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in WebSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in transport:
        url = transport['url']
        if not isinstance(url, six.text_type):
            raise Exception("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
        try:
            parseWsUrl(url)
        except Exception as e:
            raise Exception("invalid 'url' in WebSocket transport configuration : {}".format(e))

    if 'auth' in transport:
        check_transport_auth(transport['auth'])


def check_listening_transport_websocket_testee(transport):
    """
    Check a listening WebSocket-Testee pseudo transport configuration.

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
            raise Exception("encountered unknown attribute '{}' in WebSocket-Testee transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in WebSocket-Testee transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in WebSocket-Testee transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'url' in transport:
        url = transport['url']
        if not isinstance(url, six.text_type):
            raise Exception("'url' in WebSocket-Testee transport configuration must be str ({} encountered)".format(type(url)))
        try:
            parseWsUrl(url)
        except Exception as e:
            raise Exception("invalid 'url' in WebSocket-Testee transport configuration : {}".format(e))


def check_listening_transport_stream_testee(transport):
    """
    Check a listening Stream-Testee pseudo transport configuration.

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in [
           'id',
           'type',
           'endpoint',
           'debug']:
            raise Exception("encountered unknown attribute '{}' in Stream-Testee transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in Stream-Testee transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in WebSocket-Stream transport configuration must be boolean ({} encountered)".format(type(debug)))


def check_listening_transport_flashpolicy(transport):
    """
    Check a Flash-policy file serving pseudo-transport.

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'allowed_domain', 'allowed_ports', 'debug']:
            raise Exception("encountered unknown attribute '{}' in Flash-policy transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in Flash-policy transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in Flash-policy transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'allowed_domain' in transport:
        allowed_domain = transport['allowed_domain']
        if not isinstance(allowed_domain, six.text_type):
            raise Exception("'allowed_domain' in Flash-policy transport configuration must be str ({} encountered)".format(type(allowed_domain)))

    if 'allowed_ports' in transport:
        allowed_ports = transport['allowed_ports']
        if not isinstance(allowed_ports, list):
            raise Exception("'allowed_ports' in Flash-policy transport configuration must be list of integers ({} encountered)".format(type(allowed_ports)))
        for port in allowed_ports:
            check_endpoint_port(port, "Flash-policy allowed_ports")


def check_listening_transport_rawsocket(transport):
    """
    Check a listening RawSocket-WAMP transport configuration.

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'serializer', 'max_message_size', 'debug', 'auth']:
            raise Exception("encountered unknown attribute '{}' in RawSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in RawSocket transport item\n\n{}".format(pformat(transport)))

    check_listening_endpoint(transport['endpoint'])

    if 'serializer' not in transport:
        raise Exception("missing mandatory attribute 'serializer' in RawSocket transport item\n\n{}".format(pformat(transport)))

    serializer = transport['serializer']
    if not isinstance(serializer, six.text_type):
        raise Exception("'serializer' in RawSocket transport configuration must be a string ({} encountered)".format(type(serializer)))

    if serializer not in ['json', 'msgpack']:
        raise Exception("invalid value {} for 'serializer' in RawSocket transport configuration - must be one of ['json', 'msgpack']".format(serializer))

    if 'max_message_size' in transport:
        check_transport_max_message_size(transport['max_message_size'])

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in RawSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'auth' in transport:
        check_transport_auth(transport['auth'])


def check_connecting_transport_websocket(transport):
    """
    Check a connecting WebSocket-WAMP transport configuration.

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'url', 'serializers', 'debug', 'debug_wamp', 'options']:
            raise Exception("encountered unknown attribute '{}' in WebSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in WebSocket transport item\n\n{}".format(pformat(transport)))

    check_connecting_endpoint(transport['endpoint'])

    if 'options' in transport:
        check_websocket_options(transport['options'])

    if 'serializers' in transport:
        serializers = transport['serializers']
        if not isinstance(serializers, list):
            raise Exception("'serializers' in WebSocket transport configuration must be list ({} encountered)".format(type(serializers)))

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in WebSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

    if 'debug_wamp' in transport:
        debug_wamp = transport['debug_wamp']
        if not isinstance(debug_wamp, bool):
            raise Exception("'debug_wamp' in WebSocket transport configuration must be boolean ({} encountered)".format(type(debug_wamp)))

    if 'url' not in transport:
        raise Exception("missing mandatory attribute 'url' in WebSocket transport item\n\n{}".format(pformat(transport)))

    url = transport['url']
    if not isinstance(url, six.text_type):
        raise Exception("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
    try:
        parseWsUrl(url)
    except Exception as e:
        raise Exception("invalid 'url' in WebSocket transport configuration : {}".format(e))


def check_connecting_transport_rawsocket(transport):
    """
    Check a connecting RawSocket-WAMP transport configuration.

    :param transport: The configuration item to check.
    :type transport: dict
    """
    for k in transport:
        if k not in ['id', 'type', 'endpoint', 'serializer', 'debug']:
            raise Exception("encountered unknown attribute '{}' in RawSocket transport configuration".format(k))

    if 'id' in transport:
        check_id(transport['id'])

    if 'endpoint' not in transport:
        raise Exception("missing mandatory attribute 'endpoint' in RawSocket transport item\n\n{}".format(pformat(transport)))

    check_connecting_endpoint(transport['endpoint'])

    if 'serializer' not in transport:
        raise Exception("missing mandatory attribute 'serializer' in RawSocket transport item\n\n{}".format(pformat(transport)))

    serializer = transport['serializer']
    if not isinstance(serializer, six.text_type):
        raise Exception("'serializer' in RawSocket transport configuration must be a string ({} encountered)".format(type(serializer)))

    if serializer not in ['json', 'msgpack']:
        raise Exception("invalid value {} for 'serializer' in RawSocket transport configuration - must be one of ['json', 'msgpack']".format(serializer))

    if 'debug' in transport:
        debug = transport['debug']
        if not isinstance(debug, bool):
            raise Exception("'debug' in RawSocket transport configuration must be boolean ({} encountered)".format(type(debug)))


def check_router_transport(transport, silence=False):
    """
    Check router transports.

    :param transport: Router transport item to check.
    :type transport: dict
    """
    if not isinstance(transport, dict):
        raise Exception("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

    if 'type' not in transport:
        raise Exception("missing mandatory attribute 'type' in component")

    ttype = transport['type']
    if ttype not in [
        'web',
        'websocket',
        'rawsocket',
        'flashpolicy',
        'websocket.testee',
        'stream.testee'
    ]:
        raise Exception("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

    if ttype == 'websocket':
        check_listening_transport_websocket(transport)

    elif ttype == 'rawsocket':
        check_listening_transport_rawsocket(transport)

    elif ttype == 'web':
        check_listening_transport_web(transport)

    elif ttype == 'flashpolicy':
        check_listening_transport_flashpolicy(transport)

    elif ttype == 'websocket.testee':
        check_listening_transport_websocket_testee(transport)

    elif ttype == 'stream.testee':
        check_listening_transport_stream_testee(transport)

    else:
        raise Exception("logic error")


def check_router_component(component, silence=False):
    """
    Check a component configuration for a component running side-by-side with router.

    :param component: The component configuration.
    :type component: dict
    """
    if not isinstance(component, dict):
        raise Exception("components must be dictionaries ({} encountered)".format(type(component)))

    if 'type' not in component:
        raise Exception("missing mandatory attribute 'type' in component")

    ctype = component['type']
    if ctype not in ['wamplet', 'class']:
        raise Exception("invalid value '{}' for component type".format(ctype))

    if ctype == 'wamplet':
        check_dict_args({
            'id': (False, [six.text_type]),
            'type': (True, [six.text_type]),
            'realm': (True, [six.text_type]),
            'role': (False, [six.text_type]),

            'package': (True, [six.text_type]),
            'entrypoint': (True, [six.text_type]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    elif ctype == 'class':
        check_dict_args({
            'id': (False, [six.text_type]),
            'type': (True, [six.text_type]),
            'realm': (True, [six.text_type]),
            'role': (False, [six.text_type]),

            'classname': (True, [six.text_type]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    else:
        raise Exception("logic error")


def check_container_transport(transport, silence=False):
    """
    Check container transports.

    :param transport: Container transport item to check.
    :type transport: dict
    """
    if not isinstance(transport, dict):
        raise Exception("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

    if 'type' not in transport:
        raise Exception("missing mandatory attribute 'type' in component")

    ttype = transport['type']
    if ttype not in ['websocket', 'rawsocket']:
        raise Exception("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

    if ttype == 'websocket':
        check_connecting_transport_websocket(transport)

    elif ttype == 'rawsocket':
        check_connecting_transport_rawsocket(transport)

    else:
        raise Exception("logic error")


def check_container_component(component, silence=False):
    """
    Check a container component configuration.

    :param component: The component configuration to check.
    :type component: dict
    """
    if not isinstance(component, dict):
        raise Exception("components must be dictionaries ({} encountered)".format(type(component)))

    if 'type' not in component:
        raise Exception("missing mandatory attribute 'type' in component")

    ctype = component['type']
    if ctype not in ['wamplet', 'class']:
        raise Exception("invalid value '{}' for component type".format(ctype))

    if ctype == 'wamplet':
        check_dict_args({
            'id': (False, [six.text_type]),
            'type': (True, [six.text_type]),
            'realm': (True, [six.text_type]),
            'transport': (True, [dict]),

            'package': (True, [six.text_type]),
            'entrypoint': (True, [six.text_type]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    elif ctype == 'class':
        check_dict_args({
            'id': (False, [six.text_type]),
            'type': (True, [six.text_type]),
            'realm': (True, [six.text_type]),
            'transport': (True, [dict]),

            'classname': (True, [six.text_type]),
            'extra': (False, None),
        }, component, "invalid component configuration")

    else:
        raise Exception("logic error")

    check_container_transport(component['transport'])


def check_router_realm(realm, silence=False):
    # FIXME
    return

    # permissions
    #
    if 'permissions' in realm:
        permissions = realm['permissions']
        if not isinstance(permissions, dict):
            raise Exception("'permissions' in 'realm' must be a dictionary ({} encountered)\n\n{}".format(type(permissions), realm))

        for role in sorted(permissions):
            check_or_raise_uri(role, "invalid role URI '{}' in realm permissions".format(role))
            check_dict_args({
                'create': (False, [bool]),
                'join': (False, [bool]),
                'access': (False, [dict]),
            }, permissions[role], "invalid grant in realm permissions")

            if 'access' in permissions[role]:
                access = permissions[role]['access']
                if not isinstance(access, dict):
                    raise Exception("'access' attribute in realm-role permissions must be a dictionary ({} encountered)".format(type(access)))

                for uri in sorted(access.keys()):
                    if len(uri) > 0 and uri[-1] == '*':
                        check_uri = uri[:-1]
                    else:
                        check_uri = uri
                    check_or_raise_uri(check_uri, "invalid role URI '{}' in realm-role access grants".format(uri))

                    grants = access[uri]

                    check_dict_args({
                        'publish': (False, [bool]),
                        'subscribe': (False, [bool]),
                        'call': (False, [bool]),
                        'register': (False, [bool]),
                    }, grants, "invalid grant in realm permissions")

    # components
    #
    if 'components' in realm:
        components = realm['components']
        if not isinstance(components, list):
            raise Exception("'components' in 'realm' must be a list ({} encountered)\n\n{}".format(type(components), realm))

        i = 1
        for component in components:
            if not silence:
                print("Checking component item {} ..".format(i))
            # FIXME
            # check_component(component)
            i += 1


def check_router(router, silence=False):
    """
    Checks a router worker configuration.

    :param router: The configuration to check.
    :type router: dict
    """
    for k in router:
        if k not in ['id', 'type', 'options', 'manhole', 'realms', 'transports', 'components', 'links']:
            raise Exception("encountered unknown attribute '{}' in router configuration".format(k))

    # check stuff common to all native workers
    #
    if 'manhole' in router:
        check_manhole(router['manhole'])

    if 'options' in router:
        check_native_worker_options(router['options'])

    # realms
    #
    realms = router.get('realms', [])

    if not isinstance(realms, list):
        raise Exception("'realms' items must be lists ({} encountered)\n\n{}".format(type(realms), pformat(router)))

    i = 1
    for realm in realms:
        if not silence:
            print("Checking realm item {} ..".format(i))
        check_router_realm(realm, silence)
        i += 1

    # components
    #
    components = router.get('components', [])

    if not isinstance(components, list):
        raise Exception("'components' items must be lists ({} encountered)\n\n{}".format(type(components), pformat(router)))

    i = 1
    for component in components:
        if not silence:
            print("Checking component item {} ..".format(i))
        check_router_component(component, silence)
        i += 1

    # transports
    #
    transports = router.get('transports', [])

    if not isinstance(transports, list):
        raise Exception("'transports' items must be lists ({} encountered)\n\n{}".format(type(transports), pformat(router)))

    i = 1
    for transport in transports:
        if not silence:
            print("Checking transport item {} ..".format(i))
        check_router_transport(transport, silence)
        i += 1


def check_container(container, silence=False):
    """
    Checks a router worker configuration.

    :param router: The configuration to check.
    :type router: dict
    """
    for k in container:
        if k not in ['id', 'type', 'options', 'manhole', 'transports', 'components']:
            raise Exception("encountered unknown attribute '{}' in container configuration".format(k))

    # check stuff common to all native workers
    #
    if 'manhole' in container:
        check_manhole(container['manhole'])

    if 'options' in container:
        check_native_worker_options(container['options'])

    # components
    #
    components = container.get('components', [])

    if not isinstance(components, list):
        raise Exception("'components' items must be lists ({} encountered)\n\n{}".format(type(components), pformat(container)))

    i = 1
    for component in components:
        if not silence:
            print("Checking component item {} ..".format(i))
        check_container_component(component, silence)
        i += 1


def check_router_options(options):
    check_native_worker_options(options)


def check_container_options(options):
    check_native_worker_options(options)


def check_manhole(manhole, silence=False):
    if not isinstance(manhole, dict):
        raise Exception("'manhole' items must be dictionaries ({} encountered)\n\n{}".format(type(manhole), pformat(manhole)))

    for k in manhole:
        if k not in ['endpoint', 'users']:
            raise Exception("encountered unknown attribute '{}' in Manhole configuration".format(k))

    if 'endpoint' not in manhole:
        raise Exception("missing mandatory attribute 'endpoint' in Manhole item\n\n{}".format(pformat(manhole)))

    check_listening_endpoint(manhole['endpoint'])

    if 'users' not in manhole:
        raise Exception("missing mandatory attribute 'users' in Manhole item\n\n{}".format(pformat(manhole)))

    users = manhole['users']
    if not isinstance(users, list):
        raise Exception("'manhole.users' items must be lists ({} encountered)\n\n{}".format(type(users), pformat(users)))

    for user in users:
        if not isinstance(user, dict):
            raise Exception("'manhole.users.user' items must be dictionaries ({} encountered)\n\n{}".format(type(user), pformat(user)))

        for k in user:
            if k not in ['user', 'password']:
                raise Exception("encountered unknown attribute '{}' in manhole.users.user".format(k))

        if 'user' not in user:
            raise Exception("missing mandatory attribute 'user' in Manhole user item\n\n{}".format(pformat(user)))

        if 'password' not in user:
            raise Exception("missing mandatory attribute 'password' in Manhole user item\n\n{}".format(pformat(user)))


def check_process_env(env, silence=False):
    """
    Check a worker process environment configuration.

    :param env: The `env` part of the worker options.
    :type env: dict
    """
    if not isinstance(env, dict):
        raise Exception("'env' in 'options' in worker/guest configuration must be dict ({} encountered)".format(type(env)))

    for k in env:
        if k not in ['inherit', 'vars']:
            raise Exception("encountered unknown attribute '{}' in 'options.env' in worker/guest configuration".format(k))

    if 'inherit' in env:
        inherit = env['inherit']
        if isinstance(inherit, bool):
            pass
        elif isinstance(inherit, list):
            for v in inherit:
                if not isinstance(v, six.text_type):
                    raise Exception("invalid type for inherited env var name in 'inherit' in 'options.env' in worker/guest configuration - must be a string ({} encountered)".format(type(v)))
        else:
            raise Exception("'inherit' in 'options.env' in worker/guest configuration must be bool or list ({} encountered)".format(type(inherit)))

    if 'vars' in env:
        envvars = env['vars']
        if not isinstance(envvars, dict):
            raise Exception("'options.env.vars' in worker/guest configuration must be dict ({} encountered)".format(type(envvars)))

        for k, v in envvars.items():
            if not isinstance(k, six.text_type):
                raise Exception("invalid type for environment variable key '{}' in 'options.env.vars' - must be a string ({} encountered)".format(k, type(k)))
            if not isinstance(v, six.text_type):
                raise Exception("invalid type for environment variable value '{}' in 'options.env.vars' - must be a string ({} encountered)".format(v, type(v)))


def check_native_worker_options(options, silence=False):
    """
    Check native worker options.

    :param options: The native worker options to check.
    :type options: dict
    """

    if not isinstance(options, dict):
        raise Exception("'options' in worker configurations must be dictionaries ({} encountered)".format(type(options)))

    for k in options:
        if k not in ['title', 'reactor', 'python', 'pythonpath', 'cpu_affinity', 'env']:
            raise Exception("encountered unknown attribute '{}' in 'options' in worker configuration".format(k))

    if 'title' in options:
        title = options['title']
        if not isinstance(title, six.text_type):
            raise Exception("'title' in 'options' in worker configuration must be a string ({} encountered)".format(type(title)))

    if 'reactor' in options:
        _reactor = options['reactor']
        if not isinstance(_reactor, dict):
            raise Exception("'reactor' in 'options' in worker configuration must be a dict ({} encountered)".format(type(_reactor)))

    if 'python' in options:
        python = options['python']
        if not isinstance(python, six.text_type):
            raise Exception("'python' in 'options' in worker configuration must be a string ({} encountered)".format(type(python)))

    if 'pythonpath' in options:
        pythonpath = options['pythonpath']
        if not isinstance(pythonpath, list):
            raise Exception("'pythonpath' in 'options' in worker configuration must be lists ({} encountered)".format(type(pythonpath)))
        for p in pythonpath:
            if not isinstance(p, six.text_type):
                raise Exception("paths in 'pythonpath' in 'options' in worker configuration must be strings ({} encountered)".format(type(p)))

    if 'cpu_affinity' in options:
        cpu_affinity = options['cpu_affinity']
        if not isinstance(cpu_affinity, list):
            raise Exception("'cpu_affinity' in 'options' in worker configuration must be lists ({} encountered)".format(type(cpu_affinity)))
        for a in cpu_affinity:
            if type(a) not in six.integer_types:
                raise Exception("CPU affinities in 'cpu_affinity' in 'options' in worker configuration must be integers ({} encountered)".format(type(a)))

    if 'env' in options:
        check_process_env(options['env'])


def check_guest(guest, silence=False):
    """
    Check a guest worker configuration.
    """
    for k in guest:
        if k not in ['id',
                     'type',
                     'executable',
                     'arguments',
                     'stdin',
                     'stdout',
                     'stderr',
                     'workdir',
                     'options',
                     'watch']:
            raise Exception("encountered unknown attribute '{}' in guest worker configuration".format(k))

    check_dict_args({
        'id': (False, [six.text_type]),
        'type': (True, [six.text_type]),
        'executable': (True, [six.text_type]),
        'arguments': (False, [list]),
        'options': (False, [dict]),
    }, guest, "Guest process configuration")

    if guest['type'] != 'guest':
        raise Exception("invalid value '{}' for type in guest worker configuration".format(guest['type']))

    if 'arguments' in guest:
        for arg in guest['arguments']:
            if not isinstance(arg, six.text_type):
                raise Exception("invalid type {} for argument in 'arguments' in guest worker configuration".format(type(arg)))

    if 'options' in guest:
        options = guest['options']

        if not isinstance(options, dict):
            raise Exception("'options' must be dictionaries ({} encountered)\n\n{}".format(type(options), pformat(guest)))

        check_dict_args({
            'env': (False, [dict]),
            'workdir': (False, [six.text_type]),
            'stdin': (False, [six.text_type, dict]),
            'stdout': (False, [six.text_type]),
            'stderr': (False, [six.text_type]),
            'watch': (False, [dict]),
        }, options, "Guest process configuration")

        for s in ['stdout', 'stderr']:
            if s in options:
                if options[s] not in ['close', 'log', 'drop']:
                    raise Exception("invalid value '{}' for '{}' in guest worker configuration".format(options[s], s))

        if 'stdin' in options:
            if isinstance(options['stdin'], dict):
                check_dict_args({
                    'type': (True, [six.text_type]),
                    'value': (True, None),
                    'close': (False, [bool]),
                }, options['stdin'], "Guest process 'stdin' configuration")
            else:
                if options['stdin'] not in ['close']:
                    raise Exception("invalid value '{}' for 'stdin' in guest worker configuration".format(options['stdin']))

        if 'env' in options:
            check_process_env(options['env'])


def check_worker(worker, silence=False):
    """
    Check a node worker configuration item.

    :param worker: The worker configuration to check.
    :type worker: dict
    """
    if not isinstance(worker, dict):
        raise Exception("worker items must be dictionaries ({} encountered)\n\n{}".format(type(worker), pformat(worker)))

    if 'type' not in worker:
        raise Exception("missing mandatory attribute 'type' in worker item\n\n{}".format(pformat(worker)))

    ptype = worker['type']

    if ptype not in ['router', 'container', 'guest']:
        raise Exception("invalid attribute value '{}' for attribute 'type' in worker item\n\n{}".format(ptype, pformat(worker)))

    if ptype == 'router':
        check_router(worker, silence)

    elif ptype == 'container':
        check_container(worker, silence)

    elif ptype == 'guest':
        check_guest(worker, silence)

    else:
        raise Exception("logic error")


def check_controller_options(options, silence=False):
    """
    Check controller options.

    :param options: The options to check.
    :type options: dict
    """

    if not isinstance(options, dict):
        raise Exception("'options' in controller configuration must be a dictionary ({} encountered)\n\n{}".format(type(options)))

    for k in options:
        if k not in ['title']:
            raise Exception("encountered unknown attribute '{}' in 'options' in controller configuration".format(k))

    if 'title' in options:
        title = options['title']
        if not isinstance(title, six.text_type):
            raise Exception("'title' in 'options' in controller configuration must be a string ({} encountered)".format(type(title)))


def check_controller(controller, silence=False):
    """
    Check a node controller configuration item.

    :param controller: The controller configuration to check.
    :type controller: dict
    """
    if not isinstance(controller, dict):
        raise Exception("controller items must be dictionaries ({} encountered)\n\n{}".format(type(controller), pformat(controller)))

    for k in controller:
        if k not in ['id', 'realm', 'options', 'transport', 'manhole']:
            raise Exception("encountered unknown attribute '{}' in controller configuration".format(k))

    if 'id' in controller:
        check_id(controller['id'])

    if 'realm' in controller:
        check_realm_name(controller['realm'])

    if 'options' in controller:
        check_controller_options(controller['options'])

    if 'manhole' in controller:
        check_manhole(controller['manhole'])

    if 'transport' in controller:
        # FIXME: for now, only allow WAMP-WebSocket here
        check_listening_transport_websocket(controller['transport'])


def check_config(config, silence=False):
    """
    Check a Crossbar.io top-level configuration.

    :param config: The configuration to check.
    :type config: dict
    """
    if not isinstance(config, dict):
        raise Exception("top-level configuration item must be a dictionary ({} encountered)".format(type(config)))

    for k in config:
        if k not in ['controller', 'workers']:
            raise Exception("encountered unknown attribute '{}' in top-level configuration".format(k))

    # check contoller config
    #
    if 'controller' in config:
        if not silence:
            print("Checking controller item ..")
        check_controller(config['controller'])

    # check workers
    #
    workers = config.get('workers', [])

    if not isinstance(workers, list):
        raise Exception("'workers' attribute in top-level configuration must be a list ({} encountered)".format(type(workers)))

    i = 1
    for worker in workers:
        if not silence:
            print("Checking worker item {} ..".format(i))
        check_worker(worker, silence)
        i += 1


def check_config_file(configfile, silence=False):
    """
    Check a Crossbar.io local configuration file.

    :param configfile: The file to check.
    :type configfile: str
    """
    configext = os.path.splitext(configfile)[1]
    configfile = os.path.abspath(configfile)

    with open(configfile, 'rb') as infile:
        if configext == '.yaml':
            try:
                config = yaml.safe_load(infile)
            except Exception as e:
                raise Exception("configuration file does not seem to be proper YAML ('{}'')".format(e))
        else:
            try:
                config = json.load(infile)
            except ValueError as e:
                raise Exception("configuration file does not seem to be proper JSON ('{}'')".format(e))

    check_config(config, silence)

    return config


def convert_config_file(configfile):
    """
    Converts a Crossbar.io configuration file from JSON to YAML or from
    YAML to JSON.

    :param configfile: The Crossbar.io node configuration file to convert.
    :type configfile: str
    """
    configbase, configext = os.path.splitext(configfile)
    configfile = os.path.abspath(configfile)

    with open(configfile, 'rb') as infile:
        if configext == '.yaml':
            print("converting YAML configuration {} to JSON ...".format(configfile))
            try:
                config = yaml.safe_load(infile)
            except Exception as e:
                raise Exception("configuration file does not seem to be proper YAML ('{}'')".format(e))
            else:
                newconfig = os.path.abspath(configbase + '.json')
                with open(newconfig, 'wb') as outfile:
                    json.dump(config, outfile, ensure_ascii=False, separators=(', ', ': '), indent=3, sort_keys=False)
                    print("ok, JSON formatted configuration written to {}".format(newconfig))
        else:
            print("converting JSON formatted configuration {} to YAML format ...".format(configfile))
            try:
                config = json.load(infile)
            except ValueError as e:
                raise Exception("configuration file does not seem to be proper JSON ('{}'')".format(e))
            else:
                newconfig = os.path.abspath(configbase + '.yaml')
                with open(newconfig, 'wb') as outfile:
                    yaml.safe_dump(config, outfile)
                    print("ok, YAML formatted configuration written to {}".format(newconfig))


def fill_config_from_env(config, keys=None, debug=False):
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
            if type(config[k]) in (str, unicode):
                match = _ENV_VAR_PAT.match(config[k])
                if match and match.groups():
                    envvar = match.groups()[0]
                    if envvar in os.environ:
                        val = os.environ[envvar]
                        config[k] = val
                        if debug:
                            print("configuration parameter '{}' set to '{}' from environment variable {}".format(k, val, envvar))
                    else:
                        if debug:
                            print("warning: configuration parameter '{}' should have been read from enviroment variable {}, but the latter is not set".format(k, envvar))
