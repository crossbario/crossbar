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

__all__ = ['create_listening_endpoint_from_config',
           'create_listening_port_from_config']


import os

from twisted.internet.endpoints import TCP4ServerEndpoint, UNIXServerEndpoint

try:
   from twisted.internet.endpoints import SSL4ServerEndpoint
   from crossbar.twisted.tlsctx import TlsServerContextFactory
   _HAS_TLS = True
except:
   _HAS_TLS = False

from autobahn.wamp.exception import ApplicationError



def create_listening_endpoint_from_config(endpoint_config, cbdir, reactor):
   """
   """

   server_endpoint = None


   ## a TCP4 endpoint
   ##
   if endpoint_config['type'] == 'tcp':

      ## the listening port
      ##
      port = int(endpoint_config['port'])

      ## the listening interface
      ##
      interface = str(endpoint_config.get('interface', '').strip())

      ## the TCP accept queue depth
      ##
      backlog = int(endpoint_config.get('backlog', 50))

      if 'tls' in endpoint_config:
         
         if _HAS_TLS:
            key_filepath = os.path.abspath(os.path.join(cbdir, endpoint_config['tls']['key']))
            cert_filepath = os.path.abspath(os.path.join(cbdir, endpoint_config['tls']['certificate']))

            with open(key_filepath) as key_file:
               with open(cert_filepath) as cert_file:

                  if 'dhparam' in endpoint_config['tls']:
                     dhparam_filepath = os.path.abspath(os.path.join(cbdir, endpoint_config['tls']['dhparam']))
                  else:
                     dhparam_filepath = None

                  ## create a TLS context factory
                  ##
                  key = key_file.read()
                  cert = cert_file.read()
                  ciphers = endpoint_config['tls'].get('ciphers')
                  ctx = TlsServerContextFactory(key, cert, ciphers = ciphers, dhParamFilename = dhparam_filepath)

            ## create a TLS server endpoint
            ##
            server_endpoint = SSL4ServerEndpoint(reactor,
                                                 port,
                                                 ctx,
                                                 backlog = backlog,
                                                 interface = interface)
         else:
            raise ApplicationError("crossbar.error.invalid_configuration", "TLS transport requested, but TLS packages not available")
            
      else:
         ## create a non-TLS server endpoint
         ##
         server_endpoint = TCP4ServerEndpoint(reactor,
                                              port,
                                              backlog = backlog,
                                              interface = interface)

   ## a Unix Domain Socket endpoint
   ##
   elif endpoint_config['type'] == 'unix':

      ## the accept queue depth
      ##
      backlog = int(endpoint_config.get('backlog', 50))

      ## the path
      ##
      path = os.path.abspath(os.path.join(cbdir, endpoint_config['path']))

      ## create the endpoint
      ##
      server_endpoint = UNIXServerEndpoint(reactor, path, backlog = backlog)

   else:
      raise ApplicationError("crossbar.error.invalid_configuration", "invalid endpoint type '{}'".format(endpoint_config['type']))

   return server_endpoint




def create_listening_port_from_config(config, factory, cbdir, reactor):
   """
   """
   endpoint = create_listening_endpoint_from_config(config, cbdir, reactor)
   return endpoint.listen(factory)
