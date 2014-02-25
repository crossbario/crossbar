###############################################################################
##
##  Copyright (C) 2011-2014 Tavendo GmbH
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

__all__ = ['run']


import os, sys, json, argparse, pkg_resources, logging
from pprint import pprint

from twisted.python import log
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from crossbar.template import TEMPLATES

# from autobahn.websocket import connectWS
# from autobahn.wamp import WampClientFactory, WampCraClientProtocol

from crossbar.processproxy import ProcessProxy
from sys import argv, executable
#from twisted.internet import reactor



import datetime

#from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

from autobahn.twisted.util import sleep


from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior




def run_command_version(options):
   """
   Print local Crossbar.io software component types and versions.
   """
   from autobahn.twisted.choosereactor import install_reactor
   reactor = install_reactor(options.reactor, options.verbose)

   from twisted.python.reflect import qual

   ## Python
   ##
   py_ver = '.'.join([str(x) for x in list(sys.version_info[:3])])
   if options.verbose:
      py_ver += " [%s]" % sys.version.replace('\n', ' ')

   ## Twisted / Reactor
   ##
   tx_ver = "%s-%s" % (pkg_resources.require("Twisted")[0].version, reactor.__class__.__name__)
   if options.verbose:
      tx_ver += " [%s]" % qual(reactor.__class__)

   ## Autobahn
   ##
   import autobahn
   from autobahn.websocket.protocol import WebSocketProtocol
   ab_ver = pkg_resources.require("autobahn")[0].version
   if options.verbose:
      ab_ver += " [%s]" % qual(WebSocketProtocol)

   ## UTF8 Validator
   ##
   from autobahn.websocket.utf8validator import Utf8Validator
   s = str(Utf8Validator)
   if 'wsaccel' in s:
      utf8_ver = 'wsaccel-%s' % pkg_resources.require('wsaccel')[0].version
   elif s.startswith('autobahn'):
      utf8_ver = 'autobahn'
   else:
      raise Exception("could not detect UTF8 validator type/version")
   if options.verbose:
      utf8_ver += " [%s]" % qual(Utf8Validator)

   ## XOR Masker
   ##
   from autobahn.websocket.xormasker import XorMaskerNull
   s = str(XorMaskerNull)
   if 'wsaccel' in s:
      xor_ver = 'wsaccel-%s' % pkg_resources.require('wsaccel')[0].version
   elif s.startswith('autobahn'):
      xor_ver = 'autobahn'
   else:
      raise Exception("could not detect XOR masker type/version")
   if options.verbose:
      xor_ver += " [%s]" % qual(XorMaskerNull)

   print
   print "Crossbar.io local component versions:"
   print
   print "Python          : %s" % py_ver
   print "Twisted         : %s" % tx_ver
   print "Autobahn        : %s" % ab_ver
   print "UTF8 Validator  : %s" % utf8_ver
   print "XOR Masker      : %s" % xor_ver
   print



def run_command_init(options):
   if options.template:
      if not TEMPLATES.has_key(options.template):
         raise Exception("No such Crossbar.io node template {}".format(options.template))
      else:
         template = TEMPLATES[options.template]
         config = json.dumps(template, indent = 3, ensure_ascii = False, sort_keys = False)
   else:
      raise Exception("Missing template to instantiate Crossbar.io node")

   if os.path.exists(options.cbdata):
      raise Exception("Path '{}' for Crossbar.io data directory already exists".format(options.cbdata))

   try:
      os.mkdir(options.cbdata)
   except Exception as e:
      raise Exception("Could not create Crossbar.io data directory '{}' [{}]".format(options.cbdata, e))

   with open(os.path.join(options.cbdata, 'config.json'), 'wb') as outfile:
      outfile.write(config)



def run_command_start(options):

   from twisted.python import log
   log.startLogging(sys.stderr)

   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   from autobahn.twisted.choosereactor import install_reactor
   reactor = install_reactor()
   if options.debug:
      print("Running on reactor {}".format(reactor))


   ## create a WAMP router factory
   ##
   from autobahn.wamp.router import RouterFactory
   router_factory = RouterFactory()


   ## create a WAMP router session factory
   ##
   from autobahn.twisted.wamp import RouterSessionFactory
   session_factory = RouterSessionFactory(router_factory)


   ## create a WAMP-over-WebSocket transport client factory
   ##
   from autobahn.twisted.websocket import WampWebSocketClientFactory
   transport_factory = WampWebSocketClientFactory(session_factory, "ws://localhost", debug = False)
   transport_factory.setProtocolOptions(failByDrop = False)


   ## load Crossbar.io node configuration
   ##
   with open(os.path.join(options.cbdata, 'config.json'), 'rb') as infile:
      config = json.load(infile)

   if 'processes' in config:
      for process in config['processes']:
         if process['type'] == 'router':
            print "found router", process

            args = [executable, "-u", "crossbar/router/test.py"]

            print "***", os.environ['PYTHONPATH']

            ep = ProcessEndpoint(reactor,
                                 executable,
                                 args,
                                 childFDs = {0: 'w', 1: 'r', 2: 2},
                                 errFlag = StandardErrorBehavior.LOG,
                                 env = os.environ)
            d = ep.connect(transport_factory)

            def onconnect(res):
               log.msg("node component forked with PID {}".format(res.transport.pid))
               session_factory.add(ProcessProxy(res.transport.pid, process))

            def onerror(err):
               log.msg("could not fork node component: {}".format(err.value))

            d.addCallback(onconnect)
         else:
            #raise Exception("unknown process type {}".format(process['type']))
            pass

   reactor.run()



def run():
   """
   Entry point of installed Crossbar.io tool.
   """
   ## create the top-level parser
   ##
   parser = argparse.ArgumentParser(prog = 'crossbar',
                                    description = "Crossbar.io polyglot application router")

   ## top-level options
   ##
   parser.add_argument('-d',
                       '--debug',
                       action = 'store_true',
                       help = 'Debug on.')

   parser.add_argument('--reactor',
                       default = None,
                       choices = ['select', 'poll', 'epoll', 'kqueue', 'iocp'],
                       help = 'Explicit Twisted reactor selection')

   ## output format
   ##
   output_format_dummy = parser.add_argument_group(title = 'Output format control')
   output_format = output_format_dummy.add_mutually_exclusive_group(required = False)

   output_format.add_argument('-v',
                              '--verbose',
                              action = 'store_true',
                              help = 'Verbose (human) output on.')

   output_format.add_argument('-j',
                              '--json',
                              action = 'store_true',
                              help = 'Turn JSON output on.')

   ## create subcommand parser
   ##
   subparsers = parser.add_subparsers(dest = 'command',
                                      title = 'commands',
                                      help = 'Crossbar.io command to run')

   ## "version" command
   ##
   parser_version = subparsers.add_parser('version',
                                          help = 'Print software component versions.')

   parser_version.set_defaults(func = run_command_version)


   ## "init" command
   ##
   parser_init = subparsers.add_parser('init',
                                        help = 'Initialize a new Crossbar.io node.')

   parser_init.set_defaults(func = run_command_init)

   parser_init.add_argument('--template',
                             type = str,
                             default = 'router',
                             help = "Template for initialization")

   parser_init.add_argument('--cbdata',
                             type = str,
                             default = None,
                             help = "Data directory (overrides ${CROSSBAR_DATA} and default ./cbdata)")

   ## "start" command
   ##
   parser_start = subparsers.add_parser('start',
                                        help = 'Start a new server process.')

   parser_start.set_defaults(func = run_command_start)

   parser_start.add_argument('--cbdata',
                             type = str,
                             default = None,
                             help = "Data directory (overrides ${CROSSBAR_DATA} and default ./cbdata)")

   parser_start.add_argument('--cbdataweb',
                             type = str,
                             default = None,
                             help = "Web directory (overrides ${CROSSBAR_DATA_WEB} and default CBDATA/web)")

   parser_start.add_argument('--loglevel',
                              type = str,
                              default = 'info',
                              choices = ['trace', 'debug', 'info', 'warn', 'error', 'fatal'],
                              help = "Server log level (overrides default 'info')")



   ## parse cmd line args
   ##
   options = parser.parse_args()


   ## default for CBDATA
   ##
   if not options.cbdata:
      if os.environ.has_key("CBDATA"):
         options.cbdata = os.environ['CBDATA']
      else:
         options.cbdata = '.cbdata'


   ## run the subcommand selected
   ##
   options.func(options)



if __name__ == '__main__':
   run()
