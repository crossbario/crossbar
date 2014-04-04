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

import os
import sys
import json
import argparse
import pkg_resources

from twisted.python import log
from twisted.python.reflect import qual

from autobahn.twisted.choosereactor import install_reactor

from crossbar.node import Node



def run_command_version(options):
   """
   Subcommand "crossbar version".
   """
   reactor = install_reactor(options.reactor, options.debug)

   ## Python
   ##
   py_ver = '.'.join([str(x) for x in list(sys.version_info[:3])])
   if options.debug:
      py_ver += " [%s]" % sys.version.replace('\n', ' ')

   ## Twisted / Reactor
   ##
   tx_ver = "%s-%s" % (pkg_resources.require("Twisted")[0].version, reactor.__class__.__name__)
   if options.debug:
      tx_ver += " [%s]" % qual(reactor.__class__)

   ## Autobahn
   ##
   import autobahn
   from autobahn.websocket.protocol import WebSocketProtocol
   ab_ver = pkg_resources.require("autobahn")[0].version
   if options.debug:
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
   if options.debug:
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
   if options.debug:
      xor_ver += " [%s]" % qual(XorMaskerNull)

   import crossbar

   print
   print "Crossbar.io software versions:"
   print
   print "Crossbar.io     : %s" % crossbar.__version__
   print "Autobahn        : %s" % ab_ver
   print "Twisted         : %s" % tx_ver
   print "Python          : %s" % py_ver
   print "UTF8 Validator  : %s" % utf8_ver
   print "XOR Masker      : %s" % xor_ver
   print



def run_command_init(options):
   """
   Subcommand "crossbar init".
   """
   from crossbar.template import TEMPLATES
   
   if options.template:
      if not TEMPLATES.has_key(options.template):
         raise Exception("No such Crossbar.io node template {}".format(options.template))
      else:
         template = TEMPLATES[options.template]
         #config = json.dumps(template, indent = 3, ensure_ascii = False, sort_keys = False)
         config = template
   else:
      raise Exception("Missing template to instantiate Crossbar.io node")

   if os.path.exists(options.cbdir):
      raise Exception("Path '{}' for Crossbar.io node directory already exists".format(options.cbdir))

   try:
      os.mkdir(options.cbdir)
   except Exception as e:
      raise Exception("Could not create Crossbar.io node directory '{}' [{}]".format(options.cbdir, e))

   with open(os.path.join(options.cbdir, 'config.json'), 'wb') as outfile:
      outfile.write(config)

   print("Crossbar.io node initialized at {}".format(os.path.abspath(options.cbdir)))



import crossbar

def run_command_start(options):
   """
   Subcommand "crossbar start".
   """
   ## start Twisted logging
   ##
   if not options.logdir:
      logfd = sys.stderr
   else:
      from twisted.python.logfile import DailyLogFile
      logfd = DailyLogFile.fromFullPath(os.path.join(options.logdir, 'node.log'))

   from crossbar.process import DefaultSystemFileLogObserver
   flo = DefaultSystemFileLogObserver(logfd, system = "{:<10} {:>6}".format("Controller", os.getpid()))
   log.startLoggingWithObserver(flo.emit)

   log.msg("=" * 30 + " Crossbar.io " + "=" * 30 + "\n")

   log.msg("Crossbar.io {} node starting".format(crossbar.__version__))

   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   reactor = install_reactor(options.reactor, options.debug)

   #if options.debug:
   #   print("Running on reactor {}".format(reactor))

   ## create and start Crossbar.io node
   ##
   node = Node(reactor, options)
   node.start()

   ## enter event loop
   ##
   reactor.run()



def run():
   """
   Entry point of Crossbar.io.
   """
   ## create the top-level parser
   ##
   parser = argparse.ArgumentParser(prog = 'crossbar',
                                    description = "Crossbar.io - Polyglot application router - http://crossbar.io")

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
                                          help = 'Print software versions.')

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

   parser_init.add_argument('--cbdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   ## "start" command
   ##
   parser_start = subparsers.add_parser('start',
                                        help = 'Start a Crossbar.io node.')

   parser_start.set_defaults(func = run_command_start)

   parser_start.add_argument('--cbdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   parser_start.add_argument('--logdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io log directory (default: <Crossbar Node Directory>/log)")

   parser_start.add_argument('--loglevel',
                              type = str,
                              default = 'info',
                              choices = ['trace', 'debug', 'info', 'warn', 'error', 'fatal'],
                              help = "Server log level (overrides default 'info')")


   ## parse cmd line args
   ##
   options = parser.parse_args()


   ## Crossbar.io node directory
   ##
   if hasattr(options, 'cbdir'):
      if not options.cbdir:
         if os.environ.has_key("CROSSBAR_DIR"):
            options.cbdir = os.environ['CROSSBAR_DIR']
         else:
            options.cbdir = '.crossbar'
      options.cbdir = os.path.abspath(options.cbdir)


   ## Log directory
   ##
   if hasattr(options, 'logdir'):
      if options.logdir:
         options.logdir = os.path.abspath(os.path.join(options.cbdir, options.logdir))
         if not os.path.isdir(options.logdir):
            try:
               os.mkdir(options.logdir)
            except Exception as e:
               print("Could not create log directory: {}".format(e))
               sys.exit(1)


   ## run the subcommand selected
   ##
   options.func(options)



if __name__ == '__main__':
   run()
