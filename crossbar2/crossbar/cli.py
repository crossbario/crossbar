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

__all__ = ['run']


import sys, json, argparse, pkg_resources, logging
from pprint import pprint

from twisted.python import log
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from autobahn.websocket import connectWS
from autobahn.wamp import WampClientFactory, WampCraClientProtocol



def run_command_version(options):
   """
   Print local Crossbar.io software component types and versions.
   """
   from choosereactor import install_reactor
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
   from autobahn.websocket import WebSocketProtocol
   ab_ver = pkg_resources.require("autobahn")[0].version
   if options.verbose:
      ab_ver += " [%s]" % qual(WebSocketProtocol)

   ## UTF8 Validator
   ##
   from autobahn.utf8validator import Utf8Validator
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
   from autobahn.xormasker import XorMaskerNull
   s = str(XorMaskerNull)
   if 'wsaccel' in s:
      xor_ver = 'wsaccel-%s' % pkg_resources.require('wsaccel')[0].version
   elif s.startswith('autobahn'):
      xor_ver = 'autobahn'
   else:
      raise Exception("could not detect XOR masker type/version")
   if options.verbose:
      xor_ver += " [%s]" % qual(XorMaskerNull)

   ## JSON Processor
   ##
   s = str(autobahn.wamp.json_lib.__name__)
   if 'ujson' in s:
      json_ver = 'ujson-%s' % pkg_resources.require('ujson')[0].version
      import ujson
      if options.verbose:
         json_ver += " [%s]" % qual(ujson.dumps)
   elif s.startswith('json'):
      json_ver = 'python'
   else:
      raise Exception("could not detect JSON processor type/version")
   
   print
   print "Crossbar.io local component versions:"
   print
   print "Python          : %s" % py_ver
   print "Twisted         : %s" % tx_ver
   print "Autobahn        : %s" % ab_ver
   print "UTF8 Validator  : %s" % utf8_ver
   print "XOR Masker      : %s" % xor_ver
   print "JSON Processor  : %s" % json_ver
   print



def run_command_start(options):
   """
   Start Crossbar.io server.
   """
   from choosereactor import install_reactor
   reactor = install_reactor(options.reactor, options.verbose)

   import twisted
   from crossbar import logger

   if False:
      twisted.python.log.startLogging(sys.stdout)
   else:
      flo = logger.LevelFileLogObserver(sys.stdout, level = logging.DEBUG)
      twisted.python.log.startLoggingWithObserver(flo.emit)

   from crossbar.servicefactory import makeService

   svc = makeService(vars(options))
   svc.startService()

   installSignalHandlers = True
   reactor.run(installSignalHandlers)



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


   ## run the subcommand selected
   ##
   options.func(options)



if __name__ == '__main__':
   run()
