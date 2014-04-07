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

__all__ = ['check_config_file']

import os
import json
import re
from pprint import pformat

from autobahn.websocket.protocol import parseWsUrl

from autobahn.wamp.message import _URI_PAT_LOOSE_NON_EMPTY


def check_or_raise_uri(value, message):
   if type(value) not in [str, unicode]:
      raise Exception("{}: invalid type {} for URI".format(message, type(value)))
   if not _URI_PAT_LOOSE_NON_EMPTY.match(value):
      raise Exception("{}: invalid value '{}' for URI".format(message, value))
   return value



def check_endpoint_backlog(backlog):
   if type(backlog) not in [int, long]:
      raise Exception("'backlog' attribute in endpoint must be int ({} encountered)".format(type(backlog)))
   if backlog < 1 or backlog > 65535:
      raise Exception("invalid value {} for 'backlog' attribute in endpoint (must be from [1, 65535])".format(backlog))



def check_endpoint_port(port):
   if type(port) not in [int, long]:
      raise Exception("'port' attribute in endpoint must be integer ({} encountered)".format(type(port)))
   if port < 1 or port > 65535:
      raise Exception("invalid value {} for 'port' attribute in endpoint".format(port))



def check_endpoint_listen_tls(tls):
   if type(tls) != dict:
      raise Exception("'tls' in endpoint must be dictionary ({} encountered)".format(type(tls)))

   for k in tls:
      if k not in ['key', 'certificate', 'dhparam', 'ciphers']:
         raise Exception("encountered unknown attribute '{}' in listenting endpoint TLS configuration".format(k))

   for k in [('key', True), ('certificate', True), ('dhparam', False), ('ciphers', False)]:

      if k[1] and not k[0] in tls:
         raise Exception("missing mandatory attribute '{}' in listenting endpoint TLS configuration".format(k[0]))

      if k[0] in tls:
         if type(k[0]) not in [str, unicode]:
            raise Exception("'{}' in listening endpoint TLS configuration must be string ({} encountered)".format(k[0], type(k[0])))



def check_endpoint_listen_tcp(endpoint):
   for k in endpoint:
      if k not in ['type', 'port', 'interface', 'backlog', 'tls']:
         raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

   if not 'port' in endpoint:
      raise Exception("missing mandatory attribute 'port' in listening endpoint item\n\n{}".format(pformat(endpoint)))

   check_endpoint_port(endpoint['port'])

   if 'tls' in endpoint:
      check_endpoint_listen_tls(endpoint['tls'])

   if 'interface' in endpoint:
      interface = endpoint['interface']
      if type(interface) not in [str, unicode]:
         raise Exception("'interface' attribute in endpoint must be string ({} encountered)".format(type(interface)))

   if 'backlog' in endpoint:
      check_endpoint_backlog(endpoint['backlog'])



def check_endpoint_listen_unix(endpoint):
   for k in endpoint:
      if k not in ['type', 'path', 'backlog']:
         raise Exception("encountered unknown attribute '{}' in listening endpoint".format(k))

   if not 'path' in endpoint:
      raise Exception("missing mandatory attribute 'path' in Unix domain socket endpoint item\n\n{}".format(pformat(endpoint)))

   if type['path'] not in [str, unicode]:
      raise Exception("'path' attribute in Unix domain socket endpoint must be str ({} encountered)".format(type['path']))

   if 'backlog' in endpoint:
      check_endpoint_backlog(endpoint['backlog'])



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



def check_websocket_options(options):
   if type(options) != dict:
      raise Exception("WebSocket options must be a dictionary ({} encountered)".format(type(options)))

   for k in options:
      if k not in ['external_port',
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
                   ]:
         raise Exception("encountered unknown attribute '{}' in WebSocket options".format(k))

   ## FIXME: more complete checking ..



def check_transport_web_path_service_websocket(config):
   pass


def check_transport_web_path_service_static(config):
   pass


def check_transport_web_path_service_wsgi(config):
   pass


def check_transport_web_path_service_redirect(config):
   pass


def check_transport_web_path_service_json(config):
   pass


def check_transport_web_path_service_cgi(config):
   pass


def check_transport_web_path_service_longpoll(config):
   pass



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
      if k not in ['type', 'endpoint', 'paths']:
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
      if type(p) not in [str, unicode]:
         raise Exception("keys in 'paths' in Web transport configuration must be strings ({} encountered)".format(type(p)))

      if not pat.match(p):
         raise Exception("invalid value '{}' for path in Web transport configuration".format(p))

      check_transport_web_path_service(p, paths[p])



def check_transport_websocket(transport):
   for k in transport:
      if k not in ['type', 'endpoint', 'url', 'debug', 'options']:
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
      if type(url) not in [str, unicode]:
         raise Exception("'url' in WebSocket transport configuration must be str ({} encountered)".format(type(url)))
      try:
         u = parseWsUrl(url)
      except Exception as e:
         raise Exception("invalid 'url' in WebSocket transport configuration : {}".format(e))



def check_transport(transport):
   if type(transport) != dict:
      raise Exception("'transport' items must be dictionaries ({} encountered)\n\n{}".format(type(transport), pformat(transport)))

   ttype = transport['type']
   if ttype not in ['web', 'websocket', 'websocket.testee']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in transport item\n\n{}".format(ttype, pformat(transport)))

   if ttype in ['websocket', 'websocket.testee']:
      check_transport_websocket(transport)
   elif ttype == 'web':
      check_transport_web(transport)
   else:
      raise Exception("logic error")



def check_realm(realm):
   pass



def check_router(router):
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
      print("Checking realm item {} ('{}') ..".format(i, r))
      check_or_raise_uri(r, "realm keys must be valid WAMP URIs")
      check_realm(realms[r])
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
      print("Checking transport item {} ..".format(i))
      check_transport(transport)
      i += 1



def check_container(container):
   pass



def check_module(module):
   if type(module) != dict:
      raise Exception("'module' items must be dictionaries ({} encountered)\n\n{}".format(type(module), pformat(module)))

   if not 'type' in module:
      raise Exception("missing mandatory attribute 'type' in module item\n\n{}".format(pformat(module)))

   mtype = module['type']
   if mtype not in ['router', 'container']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in module item\n\n{}".format(mtype, pformat(module)))

   if mtype == 'router':
      check_router(module)
   elif mtype == 'container':
      check_container(module)
   else:
      raise Exception("logic error")




def check_worker(worker):
   for k in worker:
      if k not in ['type', 'options', 'modules']:
         raise Exception("encountered unknown attribute '{}' in worker configuration".format(k))

   if 'options' in worker:
      options = worker['options']
      if type(options) != dict:
         raise Exception("options must be dictionaries ({} encountered)\n\n{}".format(type(options), pformat(worker)))

      for k in options:
         if k not in ['pythonpath', 'cpu_affinity']:
            raise Exception("encountered unknown attribute '{}' in 'options' in worker configuration".format(k))

      if 'pythonpath' in options:
         pythonpath = options['pythonpath']
         if type(pythonpath) != list:
            raise Exception("'pythonpath' in 'options' in worker configuration must be lists ({} encountered)".format(type(pythonpath)))
         for p in pythonpath:
            if type(p) not in [str, unicode]:
               raise Exception("paths in 'pythonpath' in 'options' in worker configuration must be strings ({} encountered)".format(type(p)))

      if 'cpu_affinity' in options:
         cpu_affinity = options['cpu_affinity']
         if type(cpu_affinity) != list:
            raise Exception("'cpu_affinity' in 'options' in worker configuration must be lists ({} encountered)".format(type(cpu_affinity)))
         for a in cpu_affinity:
            if type(a) not in [int, long]:
               raise Exception("CPU affinities in 'cpu_affinity' in 'options' in worker configuration must be integers ({} encountered)".format(type(a)))


   if not 'modules' in worker:
      raise Exception("missing mandatory attribute 'modules' in worker item\n\n{}".format(pformat(worker)))

   modules = worker['modules']

   if type(modules) != list:
      raise Exception("'modules' attribute in worker item must be a list ({} encountered)\n\n{}".format(type(modules), pformat(worker)))

   i = 1
   for module in modules:
      print("Checking module item {} ..".format(i))
      check_module(module)
      i += 1



def check_guest(guest):
   pass



def check_process(process):
   if type(process) != dict:
      raise Exception("process items must be dictionaries ({} encountered)\n\n{}".format(type(process), pformat(process)))

   if not 'type' in process:
      raise Exception("missing mandatory attribute 'type' in process item\n\n{}".format(pformat(process)))

   ptype = process['type']

   if ptype not in ['worker', 'guest']:
      raise Exception("invalid attribute value '{}' for attribute 'type' in process item\n\n{}".format(ptype, pformat(process)))

   if ptype == 'worker':
      check_worker(process)
   elif ptype == 'guest':
      check_guest(process)
   else:
      raise Exception("logic error")



def check_config_file(configfile):
   configfile = os.path.abspath(configfile)

   with open(configfile, 'rb') as infile:
      try:
         config = json.load(infile)
      except ValueError as e:
         raise Exception("configuration file does not seem to be proper JSON ('{}'')".format(e))

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
      print("Checking process item {} ..".format(i))
      check_process(process)
      i += 1
