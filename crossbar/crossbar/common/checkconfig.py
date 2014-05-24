###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

__all__ = ['check_config',
           'check_config_file',
           'check_guest']

import os
import json
import re
import six

from pprint import pformat

from autobahn.websocket.protocol import parseWsUrl

from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY, \
                                  _URI_PAT_LOOSE_NON_EMPTY



def check_dict_args(spec, config, msg):
   for k in config:
      if not k in spec:
         raise Exception("{} - encountered unknown attribute '{}'".format(msg, k))
      if spec[k][1] and type(config[k]) not in spec[k][1]:
         raise Exception("{} - invalid {} encountered for attribute '{}'".format(msg, type(config[k]), k))
   mandatory_keys = [k for k in spec if spec[k][0]]
   for k in mandatory_keys:
      if not k in config:
         raise Exception("{} - missing mandatory attribute '{}'".format(msg, k))



def check_or_raise_uri(value, message):
   if type(value) != six.text_type:
      raise Exception("{}: invalid type {} for URI".format(message, type(value)))
   #if not _URI_PAT_LOOSE_NON_EMPTY.match(value):
   if not _URI_PAT_STRICT_NON_EMPTY.match(value):
      raise Exception("{}: invalid value '{}' for URI".format(message, value))
   return value



def check_endpoint_backlog(backlog):
   if type(backlog) not in six.integer_types:
      raise Exception("'backlog' attribute in endpoint must be int ({} encountered)".format(type(backlog)))
   if backlog < 1 or backlog > 65535:
      raise Exception("invalid value {} for 'backlog' attribute in endpoint (must be from [1, 65535])".format(backlog))



def check_endpoint_port(port):
   if type(port) not in six.integer_types:
      raise Exception("'port' attribute in endpoint must be integer ({} encountered)".format(type(port)))
   if port < 1 or port > 65535:
      raise Exception("invalid value {} for 'port' attribute in endpoint".format(port))



def check_endpoint_timeout(timeout):
   if type(timeout) not in six.integer_types:
      raise Exception("'timeout' attribute in endpoint must be integer ({} encountered)".format(type(timeout)))
   if port < 0 or port > 600:
      raise Exception("invalid value {} for 'timeout' attribute in endpoint".format(timeout))



def check_endpoint_listen_tls(tls):
   if type(tls) != dict:
      raise Exception("'tls' in endpoint must be dictionary ({} encountered)".format(type(tls)))

   for k in tls:
      if k not in ['key', 'certificate', 'dhparam', 'ciphers']:
         raise Exception("encountered unknown attribute '{}' in listening endpoint TLS configuration".format(k))

   for k in [('key', True), ('certificate', True), ('dhparam', False), ('ciphers', False)]:

      if k[1] and not k[0] in tls:
         raise Exception("missing mandatory attribute '{}' in listening endpoint TLS configuration".format(k[0]))

      if k[0] in tls:
         if type(k[0]) != six.text_type:
            raise Exception("'{}' in listening endpoint TLS configuration must be string ({} encountered)".format(k[0], type(k[0])))



def check_endpoint_connect_tls(tls):
   if type(tls) != dict:
      raise Exception("'tls' in endpoint must be dictionary ({} encountered)".format(type(tls)))

   for k in tls:
      if k not in []:
         raise Exception("encountered unknown attribute '{}' in listening endpoint TLS configuration".format(k))



def check_endpoint_listen_tcp(endpoint):
   for k in endpoint:
      if k not in ['type', 'port', 'shared', 'interface', 'backlog', 'tls']:
         raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

   if not 'port' in endpoint:
      raise Exception("missing mandatory attribute 'port' in listening endpoint item\n\n{}".format(pformat(endpoint)))

   check_endpoint_port(endpoint['port'])

   if 'shared' in endpoint:
      shared = endpoint['shared']
      if type(shared) != bool:
         raise Exception("'shared' attribute in endpoint must be bool ({} encountered)".format(type(shared)))

   if 'tls' in endpoint:
      check_endpoint_listen_tls(endpoint['tls'])

   if 'interface' in endpoint:
      interface = endpoint['interface']
      if type(interface) != six.text_type:
         raise Exception("'interface' attribute in endpoint must be string ({} encountered)".format(type(interface)))

   if 'backlog' in endpoint:
      check_endpoint_backlog(endpoint['backlog'])



def check_endpoint_listen_unix(endpoint):
   for k in endpoint:
      if k not in ['type', 'path', 'backlog']:
         raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

   if not 'path' in endpoint:
      raise Exception("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

   path = endpoint['path']
   if type(path) != six.text_type:
      raise Exception("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

   if 'backlog' in endpoint:
      check_endpoint_backlog(endpoint['backlog'])



def check_endpoint_connect_tcp(endpoint):
   for k in endpoint:
      if k not in ['type', 'host', 'port', 'timeout', 'tls']:
         raise Exception("encountered unknown attribute '{}' in connecting endpoint".format(k))

   if not 'host' in endpoint:
      raise Exception("missing mandatory attribute 'host' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

   if not 'port' in endpoint:
      raise Exception("missing mandatory attribute 'port' in connecting endpoint item\n\n{}".format(pformat(endpoint)))

   check_endpoint_port(endpoint['port'])

   if 'tls' in endpoint:
      check_endpoint_connect_tls(endpoint['tls'])

   if 'timeout' in endpoint:
      check_endpoint_timeout(endpoint['timeout'])



def check_endpoint_connect_unix(endpoint):
   for k in endpoint:
      if k not in ['type', 'path', 'timeout']:
         raise Exception("encountered unknown attribute '{}' in connecting endpoint".format(k))

   if not 'path' in endpoint:
      raise Exception("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

   path = endpoint['path']
   if type(path) != six.text_type:
      raise Exception("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type(path)))

   if 'timeout' in endpoint:
      check_endpoint_timeout(endpoint['timeout'])



def check_endpoint_listen(endpoint):
   if type(endpoint) != dict:
      raise Exception("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

   if not 'type' in endpoint:
      raise Exception("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

   etype = endpoint['type']
   if etype not in ['tcp', 'unix']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

   if etype == 'tcp':
      check_endpoint_listen_tcp(endpoint)
   elif etype == 'unix':
      check_endpoint_listen_unix(endpoint)
   else:
      raise Exception("logic error")



def check_endpoint_connect(endpoint):
   if type(endpoint) != dict:
      raise Exception("'endpoint' items must be dictionaries ({} encountered)\n\n{}".format(type(endpoint)))

   if not 'type' in endpoint:
      raise Exception("missing mandatory attribute 'type' in endpoint item\n\n{}".format(pformat(endpoint)))

   etype = endpoint['type']
   if etype not in ['tcp', 'unix']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in endpoint item\n\n{}".format(etype, pformat(endpoint)))

   if etype == 'tcp':
      check_endpoint_connect_tcp(endpoint)
   elif etype == 'unix':
      check_endpoint_connect_unix(endpoint)
   else:
      raise Exception("logic error")



def check_websocket_options(options):
   if type(options) != dict:
      raise Exception("WebSocket options must be a dictionary ({} encountered)".format(type(options)))

   for k in options:
      if k not in [
                   ## WebSocket options
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
                   'compression',

                   ## WAMP-WebSocket options
                   'serializers'
                   ]:
         raise Exception("encountered unknown attribute '{}' in WebSocket options".format(k))

   ## FIXME: more complete checking ..



def check_transport_web_path_service_websocket(config):
   if 'options' in config:
      check_websocket_options(config['options'])

   if 'debug' in config:
      debug = config['debug']
      if type(debug) != bool:
         raise Exception("'debug' in WebSocket configuration must be boolean ({} encountered)".format(type(debug)))

   if 'url' in config:
      url = config['url']
      if type(url) != six.text_type:
         raise Exception("'url' in WebSocket configuration must be str ({} encountered)".format(type(url)))
      try:
         u = parseWsUrl(url)
      except Exception as e:
         raise Exception("invalid 'url' in WebSocket configuration : {}".format(e))



def check_transport_web_path_service_static(config):
   check_dict_args({
      'type': (True, [six.text_type]),
      'directory': (False, [six.text_type]),
      'module': (False, [six.text_type]),
      'resource': (False, [six.text_type]),
      'enable_directory_listing': (False, [bool])
      }, config, "Web transport 'static' path service")

   if 'directory' in config:
      if 'module' in config or 'resource' in config:
         raise Exception("Web transport 'static' path service: either 'directory' OR 'module' + 'resource' must be given, not both")
   else:
      if not 'module' in config or not 'resource' in config:
         raise Exception("Web transport 'static' path service: either 'directory' OR 'module' + 'resource' must be given, not both")



def check_transport_web_path_service_wsgi(config):
   check_dict_args({
      'type': (True, [six.text_type]),
      'module': (True, [six.text_type]),
      'object': (True, [six.text_type])
      }, config, "Web transport 'wsgi' path service")



def check_transport_web_path_service_redirect(config):
   check_dict_args({
      'type': (True, [six.text_type]),
      'url': (True, [six.text_type])
      }, config, "Web transport 'redirect' path service")



def check_transport_web_path_service_json(config):
   check_dict_args({
      'type': (True, [six.text_type]),
      'value': (True, None)
      }, config, "Web transport 'json' path service")



def check_transport_web_path_service_cgi(config):
   check_dict_args({
      'type': (True, [six.text_type]),
      'directory': (True, [six.text_type]),
      'processor': (True, [six.text_type]),
      }, config, "Web transport 'cgi' path service")



def check_transport_web_path_service_longpoll(config):
   raise Exception("Web transport 'longpoll' path service : not yet implemented")



def check_transport_web_path_service(path, config):
   if not 'type' in config:
      raise Exception("missing mandatory attribute 'type' in Web transport path '{}' configuration\n\n{}".format(path, config))

   ptype = config['type']
   if path == '/':
      if ptype not in ['static', 'wsgi', 'redirect']:
         raise Exception("invalid type '{}' for root-path service in Web transport path '{}' configuration\n\n{}".format(ptype, path, config))
   else:
      if ptype not in ['websocket', 'static', 'wsgi', 'redirect', 'json', 'cgi', 'longpoll']:
         raise Exception("invalid type '{}' for sub-path service in Web transport path '{}' configuration\n\n{}".format(ptype, path, config))

   checkers = {
      'websocket': check_transport_web_path_service_websocket,
      'static': check_transport_web_path_service_static,
      'wsgi': check_transport_web_path_service_wsgi,
      'redirect': check_transport_web_path_service_redirect,
      'json': check_transport_web_path_service_json,
      'cgi': check_transport_web_path_service_cgi,
      'longpoll': check_transport_web_path_service_longpoll
   }

   checkers[ptype](config)



def check_transport_web(transport):
   for k in transport:
      if k not in ['type', 'endpoint', 'paths', 'options']:
         raise Exception("encountered unknown attribute '{}' in Web transport configuration".format(k))

   if not 'endpoint' in transport:
      raise Exception("missing mandatory attribute 'endpoint' in Web transport item\n\n{}".format(pformat(transport)))

   check_endpoint_listen(transport['endpoint'])

   if not 'paths' in transport:
      raise Exception("missing mandatory attribute 'paths' in Web transport item\n\n{}".format(pformat(transport)))

   paths = transport['paths']
   if type(paths) != dict:
      raise Exception("'paths' attribute in Web transport configuration must be dictionary ({} encountered)".format(type(paths)))

   if not '/' in paths:
      raise Exception("missing mandatory path '/' in 'paths' in Web transport configuration")

   pat = re.compile("^([a-z0-9A-Z]+|/)$")

   for p in paths:
      if type(p) != six.text_type:
         raise Exception("keys in 'paths' in Web transport configuration must be strings ({} encountered)".format(type(p)))

      if not pat.match(p):
         raise Exception("invalid value '{}' for path in Web transport configuration".format(p))

      check_transport_web_path_service(p, paths[p])

   if 'options' in transport:
      options = transport['options']
      if type(options) != dict:
         raise Exception("'options' in Web transport must be dictionary ({} encountered)".format(type(options)))

      if 'access_log' in options:
         access_log = options['access_log']
         if type(access_log) != bool:
            raise Exception("'access_log' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(access_log)))

      if 'hsts' in options:
         hsts = options['hsts']
         if type(hsts) != bool:
            raise Exception("'hsts' attribute in 'options' in Web transport must be bool ({} encountered)".format(type(hsts)))

      if 'hsts_max_age' in options:
         hsts_max_age = options['hsts_max_age']
         if type(hsts_max_age) not in six.integer_types:
            raise Exception("'hsts_max_age' attribute in 'options' in Web transport must be integer ({} encountered)".format(type(hsts_max_age)))
         if hsts_max_age < 0:
            raise Exception("'hsts_max_age' attribute in 'options' in Web transport must be non-negative ({} encountered)".format(hsts_max_age))



def check_transport_websocket(transport):
   for k in transport:
      if k not in ['type', 'endpoint', 'url', 'debug', 'debug_traffic', 'options']:
#      if k not in ['type', 'endpoint', 'url', 'debug', 'options']:
         raise Exception("encountered unknown attribute '{}' in WebSocket transport configuration".format(k))

   if not 'endpoint' in transport:
      raise Exception("missing mandatory attribute 'endpoint' in WebSocket transport item\n\n{}".format(pformat(transport)))

   check_endpoint_listen(transport['endpoint'])

   if 'options' in transport:
      check_websocket_options(transport[options])

   if 'debug' in transport:
      debug = transport['debug']
      if type(debug) != bool:
         raise Exception("'debug' in WebSocket transport configuration must be boolean ({} encountered)".format(type(debug)))

   if 'url' in transport:
      url = transport['url']
      if type(url) != six.text_type:
         raise Exception("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
      try:
         u = parseWsUrl(url)
      except Exception as e:
         raise Exception("invalid 'url' in WebSocket transport configuration : {}".format(e))



def check_transport_rawsocket(transport):
   for k in transport:
      if k not in ['type', 'endpoint', 'serializer', 'debug']:
         raise Exception("encountered unknown attribute '{}' in RawSocket transport configuration".format(k))

   if not 'endpoint' in transport:
      raise Exception("missing mandatory attribute 'endpoint' in RawSocket transport item\n\n{}".format(pformat(transport)))

   check_endpoint_listen(transport['endpoint'])

   if not 'serializer' in transport:
      raise Exception("missing mandatory attribute 'serializer' in RawSocket transport item\n\n{}".format(pformat(transport)))

   serializer = transport['serializer']
   if type(serializer) != six.text_type:
      raise Exception("'serializer' in RawSocket transport configuration must be a string ({} encountered)".format(type(serializer)))

   if serializer not in ['json', 'msgpack']:
      raise Exception("invalid value {} for 'serializer' in RawSocket transport configuration - must be one of ['json', 'msgpack']".format(serializer))

   if 'debug' in transport:
      debug = transport['debug']
      if type(debug) != bool:
         raise Exception("'debug' in RawSocket transport configuration must be boolean ({} encountered)".format(type(debug)))



def check_transport(transport):
   if type(transport) != dict:
      raise Exception("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

   if not 'type' in transport:
      raise Exception("missing mandatory attribute 'type' in component")

   ttype = transport['type']
   if ttype not in ['web', 'websocket', 'websocket.testee', 'rawsocket']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

   if ttype in ['websocket', 'websocket.testee']:
      check_transport_websocket(transport)
   elif ttype == 'rawsocket':
      check_transport_rawsocket(transport)
   elif ttype == 'web':
      check_transport_web(transport)
   else:
      raise Exception("logic error")



def check_component(component):
   if type(component) != dict:
      raise Exception("components must be dictionaries ({} encountered)".format(type(component)))

   if not 'type' in component:
      raise Exception("missing mandatory attribute 'type' in component")

   ctype = component['type']
   if ctype not in ['wamplet', 'class']:
      raise Exception("invalid value '{}' for component type".format(ctype))

   if ctype == 'wamplet':
      check_dict_args({
         'type': (True, [six.text_type]),
         'dist': (True, [six.text_type]),
         'entry': (True, [six.text_type]),
         'extra': (False, None),
         }, component, "invalid component configuration")

   elif ctype == 'class':
      check_dict_args({
         'type': (True, [six.text_type]),
         'name': (True, [six.text_type]),
         'extra': (False, None),
         }, component, "invalid component configuration")

   else:
      raise Exception("logic error")



def check_container_component(component):
   print("FIXME: check_container_component")



def check_realm(realm, silence = False):
   ## permissions
   ##
   if 'permissions' in realm:
      permissions = realm['permissions']
      if type(permissions) != dict:
         raise Exception("'permissions' in 'realm' must be a dictionary ({} encountered)\n\n{}".format(type(components), realm))

      for role in sorted(permissions):
         check_or_raise_uri(role, "invalid role URI '{}' in realm permissions".format(role))
         check_dict_args({
            'create': (False, [bool]),
            'join': (False, [bool]),
            'access': (False, [dict]),
            }, permissions[role], "invalid grant in realm permissions")

         if 'access' in permissions[role]:
            access = permissions[role]['access']
            if type(access) != dict:
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

   ## components
   ##
   if 'components' in realm:
      components = realm['components']
      if type(components) != list:
         raise Exception("'components' in 'realm' must be a list ({} encountered)\n\n{}".format(type(components), realm))

      i = 1
      for component in components:
         if not silence:
            print("Checking component item {} ..".format(i))
            check_component(component)
            i += 1



def check_router(router, silence = False):
   for k in router:
      if k not in ['type', 'realms', 'transports']:
         raise Exception("encountered unknown attribute '{}' in router configuration".format(k))

   ## realms
   ##
   if not 'realms' in router:
      raise Exception("missing mandatory attribute 'realms' in router item\n\n{}".format(pformat(router)))

   realms = router['realms']

   if type(realms) != dict:
      raise Exception("'realms' items must be dictionaries ({} encountered)\n\n{}".format(type(realms), pformat(router)))

   i = 1
   for r in sorted(realms.keys()):
      if not silence:
         print("Checking realm item {} ('{}') ..".format(i, r))
      check_or_raise_uri(r, "realm keys must be valid WAMP URIs")
      check_realm(realms[r], silence)
      i += 1

   ## transports
   ##
   if not 'transports' in router:
      raise Exception("missing mandatory attribute 'transports' in router item\n\n{}".format(pformat(router)))

   transports = router['transports']

   if type(transports) != list:
      raise Exception("'transports' items must be lists ({} encountered)\n\n{}".format(type(transports), pformat(router)))

   i = 1
   for transport in transports:
      if not silence:
         print("Checking transport item {} ..".format(i))
      check_transport(transport)
      i += 1



def check_container(container, silence = False):
   print("FIXME: check_container")



def check_router_options(router_options):
   print("FIXME: implement check_router_options")



def check_container_options(container_options):
   print("FIXME: implement check_container_options")



def check_module(module, silence = False):
   if type(module) != dict:
      raise Exception("'module' items must be dictionaries ({} encountered)\n\n{}".format(type(module), pformat(module)))

   if not 'type' in module:
      raise Exception("missing mandatory attribute 'type' in module item\n\n{}".format(pformat(module)))

   mtype = module['type']
   if mtype not in ['router', 'container']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in module item\n\n{}".format(mtype, pformat(module)))

   if mtype == 'router':
      check_router(module, silence)
   elif mtype == 'container':
      check_container(module, silence)
   else:
      raise Exception("logic error")



def check_manhole(manhole, silence = False):
   if type(manhole) != dict:
      raise Exception("'manhole' items must be dictionaries ({} encountered)\n\n{}".format(type(manhole), pformat(manhole)))

   for k in manhole:
      if k not in ['endpoint', 'users']:
         raise Exception("encountered unknown attribute '{}' in Manhole configuration".format(k))

   if not 'endpoint' in manhole:
      raise Exception("missing mandatory attribute 'endpoint' in Manhole item\n\n{}".format(pformat(manhole)))

   check_endpoint_listen(manhole['endpoint'])

   if not 'users' in manhole:
      raise Exception("missing mandatory attribute 'users' in Manhole item\n\n{}".format(pformat(manhole)))

   users = manhole['users']
   if type(users) != list:
      raise Exception("'manhole.users' items must be lists ({} encountered)\n\n{}".format(type(users), pformat(users)))

   for user in users:
      if type(user) != dict:
         raise Exception("'manhole.users.user' items must be dictionaries ({} encountered)\n\n{}".format(type(user), pformat(user)))

      for k in user:
         if k not in ['user', 'password']:
            raise Exception("encountered unknown attribute '{}' in manhole.users.user".format(k))

      if not 'user' in user:
         raise Exception("missing mandatory attribute 'user' in Manhole user item\n\n{}".format(pformat(user)))

      if not 'password' in user:
         raise Exception("missing mandatory attribute 'password' in Manhole user item\n\n{}".format(pformat(user)))



def check_process_env(env, silence = False):
   if type(env) != dict:
      raise Exception("'env' in 'options' in worker/guest configuration must be dict ({} encountered)".format(type(env)))

   for k in env:
      if k not in ['inherit', 'vars']:
         raise Exception("encountered unknown attribute '{}' in 'options.env' in worker/guest configuration".format(k))

   if 'inherit' in env:
      inherit = env['inherit']
      if type(inherit) == bool:
         pass
      elif type(inherit) == list:
         for v in inherit:
            if type(v) != six.text_type:
               raise Exception("invalid type for inherited env var name in 'inherit' in 'options.env' in worker/guest configuration - must be a string ({} encountered)".format(type(v)))
      else:
         raise Exception("'inherit' in 'options.env' in worker/guest configuration must be bool or list ({} encountered)".format(type(inherit)))

   if 'vars' in env:
      envvars = env['vars']
      if type(envvars) != dict:
         raise Exception("'options.env.vars' in worker/guest configuration must be dict ({} encountered)".format(type(envvars)))

      for k, v in envvars.items():
         if type(k) != six.text_type:
            raise Exception("invalid type for environment variable key '{}' in 'options.env.vars' - must be a string ({} encountered)".format(k, type(k)))
         if type(v) != six.text_type:
            raise Exception("invalid type for environment variable value '{}' in 'options.env.vars' - must be a string ({} encountered)".format(v, type(v)))



def check_worker(worker, silence = False):
   for k in worker:
      if k not in ['type', 'options', 'modules', 'manhole']:
         raise Exception("encountered unknown attribute '{}' in worker configuration".format(k))


   if 'manhole' in worker:
      check_manhole(worker['manhole'])


   if 'options' in worker:
      options = worker['options']
      if type(options) != dict:
         raise Exception("options must be dictionaries ({} encountered)\n\n{}".format(type(options), pformat(worker)))

      for k in options:
         if k not in ['pythonpath', 'cpu_affinity', 'env', 'title']:
            raise Exception("encountered unknown attribute '{}' in 'options' in worker configuration".format(k))

      if 'title' in options:
         title = options['title']
         if type(title) != six.text_type:
            raise Exception("'title' in 'options' in worker configuration must be a string ({} encountered)".format(type(title)))

      if 'pythonpath' in options:
         pythonpath = options['pythonpath']
         if type(pythonpath) != list:
            raise Exception("'pythonpath' in 'options' in worker configuration must be lists ({} encountered)".format(type(pythonpath)))
         for p in pythonpath:
            if type(p) != six.text_type:
               raise Exception("paths in 'pythonpath' in 'options' in worker configuration must be strings ({} encountered)".format(type(p)))

      if 'cpu_affinity' in options:
         cpu_affinity = options['cpu_affinity']
         if type(cpu_affinity) != list:
            raise Exception("'cpu_affinity' in 'options' in worker configuration must be lists ({} encountered)".format(type(cpu_affinity)))
         for a in cpu_affinity:
            if type(a) not in six.integer_types:
               raise Exception("CPU affinities in 'cpu_affinity' in 'options' in worker configuration must be integers ({} encountered)".format(type(a)))

      if 'env' in options:
         check_process_env(options['env'])

   if not 'modules' in worker:
      raise Exception("missing mandatory attribute 'modules' in worker item\n\n{}".format(pformat(worker)))

   modules = worker['modules']

   if type(modules) != list:
      raise Exception("'modules' attribute in worker item must be a list ({} encountered)\n\n{}".format(type(modules), pformat(worker)))

   i = 1
   for module in modules:
      if not silence:
         print("Checking module item {} ..".format(i))
      check_module(module, silence)
      i += 1



def check_guest(guest, silence = False):
   """
   Check a guest worker configuration.
   """
   for k in guest:
      if k not in ['type',
                   'executable',
                   'arguments',
                   'stdin',
                   'stdout',
                   'stderr',
                   'workdir',
                   'options']:
         raise Exception("encountered unknown attribute '{}' in guest worker configuration".format(k))

   check_dict_args({
      'type': (True, [six.text_type]),
      'executable': (True, [six.text_type]),
      'stdin': (False, [six.text_type, dict]),
      'stdout': (False, [six.text_type]),
      'stderr': (False, [six.text_type]),
      'arguments': (False, [list]),
      'workdir': (False, [six.text_type]),
      'options': (False, [dict])
      }, guest, "Guest process configuration")

   if guest['type'] != 'guest':
      raise Exception("invalid value '{}' for type in guest worker configuration".format(guest['type']))

   for s in ['stdout', 'stderr']:
      if s in guest:
         if guest[s] not in ['close', 'log', 'drop']:
            raise Exception("invalid value '{}' for '{}' in guest worker configuration".format(guest[s], s))

   if 'stdin' in guest:
      if type(guest['stdin']) == dict:
         check_dict_args({
            'type': (True, [six.text_type]),
            'value': (True, None),
            'close': (False, [bool]),
            }, guest['stdin'], "Guest process 'stdin' configuration")
      else:
         if guest['stdin'] not in ['close']:
            raise Exception("invalid value '{}' for 'stdin' in guest worker configuration".format(guest['stdin']))

   if 'arguments' in guest:
      for arg in guest['arguments']:
         if type(arg) != six.text_type:
            raise Exception("invalid type {} for argument in 'arguments' in guest worker configuration".format(type(arg)))

   if 'options' in guest:
      options = guest['options']
      if type(options) != dict:
         raise Exception("options must be dictionaries ({} encountered)\n\n{}".format(type(options), pformat(worker)))

      for k in options:
         if k not in ['env']:
            raise Exception("encountered unknown attribute '{}' in 'options' in guest worker configuration".format(k))

      if 'env' in options:
         check_process_env(options['env'])



def check_process(process, silence = False):
   if type(process) != dict:
      raise Exception("process items must be dictionaries ({} encountered)\n\n{}".format(type(process), pformat(process)))

   if not 'type' in process:
      raise Exception("missing mandatory attribute 'type' in process item\n\n{}".format(pformat(process)))

   ptype = process['type']

   if ptype not in ['worker', 'guest']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in process item\n\n{}".format(ptype, pformat(process)))

   if ptype == 'worker':
      check_worker(process, silence)
   elif ptype == 'guest':
      check_guest(process, silence)
   else:
      raise Exception("logic error")



def check_config(config, silence = False):
   if type(config) != dict:
      raise Exception("top-level configuration item must be a dictionary ({} encountered)".format(type(config)))

   for k in config:
      if k not in ['processes']:
         raise Exception("encountered unknown attribute '{}' in top-level configuration".format(k))

   if not 'processes' in config:
      raise Exception("missing 'processes' attribute in top-level configuration item")

   processes = config['processes']

   if type(processes) != list:
      raise Exception("'processes' attribute in top-level configuration must be a list ({} encountered)".format(type(processes)))

   i = 1
   for process in processes:
      if not silence:
         print("Checking process item {} ..".format(i))
      check_process(process, silence)
      i += 1



def check_config_file(configfile, silence = False):
   configfile = os.path.abspath(configfile)

   with open(configfile, 'rb') as infile:
      try:
         config = json.load(infile)
      except ValueError as e:
         raise Exception("configuration file does not seem to be proper JSON ('{}'')".format(e))

   check_config(config, silence)

   return config
