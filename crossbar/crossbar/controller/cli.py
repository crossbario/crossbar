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
import platform

from twisted.python import log
from twisted.python.reflect import qual
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.choosereactor import install_reactor

import crossbar
from crossbar.controller.node import Node



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

   print()
   print("Crossbar.io software versions:")
   print()
   print("Crossbar.io     : {0}".format(crossbar.__version__))
   print("Autobahn        : {0}".format(ab_ver))
   print("Twisted         : {0}".format(tx_ver))
   print("Python          : {0}".format(py_ver))
   print("UTF8 Validator  : {0}".format(utf8_ver))
   print("XOR Masker      : {0}".format(xor_ver))
   print()



def run_command_init(options):
   """
   Subcommand "crossbar init".
   """
   from crossbar.controller.template import CONFIG_TEMPLATES

   if options.template:
      if not options.template in CONFIG_TEMPLATES:
         raise Exception("No such Crossbar.io node template {}".format(options.template))
      else:
         template = CONFIG_TEMPLATES[options.template]
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

   with open(os.path.join(options.cbdir, options.config), 'wb') as outfile:
      outfile.write(config)

   print("Crossbar.io node initialized at {}".format(os.path.abspath(options.cbdir)))




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

   from crossbar.twisted.process import DefaultSystemFileLogObserver
   flo = DefaultSystemFileLogObserver(logfd, system = "{:<10} {:>6}".format("Controller", os.getpid()))
   log.startLoggingWithObserver(flo.emit)

   log.msg("=" * 30 + " Crossbar.io " + "=" * 30 + "\n")

   log.msg("Crossbar.io {} starting".format(crossbar.__version__))

   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   reactor = install_reactor(options.reactor, options.debug)

   from twisted.python.reflect import qual
   log.msg("Running on {} using {} reactor".format(platform.python_implementation(), qual(reactor.__class__).split('.')[-1]))
   log.msg("Starting from node directory {}".format(options.cbdir))


   ## create and start Crossbar.io node
   ##
   node = Node(reactor, options)
   node.start()

   reactor.run()



def run_command_check(options):
   """
   Subcommand "crossbar check".
   """
   from crossbar.controller.config import check_config_file
   configfile = os.path.join(options.cbdir, options.config)

   print("Checking local configuration file {}".format(configfile))

   try:
      check_config_file(configfile)
   except Exception as e:
      print("Error encountered:")
      print()
      print(e)
      print()
   else:
      print("Ok, configuration file looks good.")



def run():
   """
   Entry point of Crossbar.io CLI.
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
                             default = 'default',
                             help = "Template for initialization")

   parser_init.add_argument('--cbdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   parser_init.add_argument('--config',
                            type = str,
                            default = 'config.json',
                            help = "Crossbar.io configuration file (overrides default CBDIR/config.json)")


   ## "start" command
   ##
   parser_start = subparsers.add_parser('start',
                                        help = 'Start a Crossbar.io node.')

   parser_start.set_defaults(func = run_command_start)

   parser_start.add_argument('--cbdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   parser_start.add_argument('--config',
                             type = str,
                             default = 'config.json',
                             help = "Crossbar.io configuration file (overrides default CBDIR/config.json)")

   parser_start.add_argument('--logdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io log directory (default: <Crossbar Node Directory>/log)")

   parser_start.add_argument('--loglevel',
                              type = str,
                              default = 'info',
                              choices = ['trace', 'debug', 'info', 'warn', 'error', 'fatal'],
                              help = "Server log level (overrides default 'info')")


   ## "check" command
   ##
   parser_check = subparsers.add_parser('check',
                                        help = 'Check a Crossbar.io node`s local configuration file.')

   parser_check.set_defaults(func = run_command_check)

   parser_check.add_argument('--cbdir',
                             type = str,
                             default = None,
                             help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   parser_check.add_argument('--config',
                             type = str,
                             default = None,
                             help = "Crossbar.io configuration file (overrides default CBDIR/config.json)")


   ## parse cmd line args
   ##
   options = parser.parse_args()


   ## Crossbar.io node directory
   ##
   if hasattr(options, 'cbdir'):
      if not options.cbdir:
         if "CROSSBAR_DIR" in os.environ:
            options.cbdir = os.environ['CROSSBAR_DIR']
         else:
            options.cbdir = '.crossbar'
      options.cbdir = os.path.abspath(options.cbdir)


   ## Crossbar.io node configuration file
   ##
   if hasattr(options, 'config'):
      if not options.config:
         options.config = 'config.json'
      options.config = os.path.join(options.cbdir, options.config)


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
