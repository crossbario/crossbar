###############################################################################
##
##  Copyright (C) 2011-2015 Tavendo GmbH
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
import shutil
import traceback

from twisted.python import log
from twisted.python.reflect import qual
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.choosereactor import install_reactor


try:
   import psutil
   _HAS_PSUTIL = True
except ImportError:
   _HAS_PSUTIL = False


_PID_FILENAME = 'node.pid'



def check_pid_exists(pid):
   """
   Check if a process with given PID exists.

   :returns: ``True`` if a process exists.
   :rtype: bool
   """
   if sys.platform == 'win32':
      if _HAS_PSUTIL:
         # http://pythonhosted.org/psutil/#psutil.pid_exists
         return psutil.pid_exists(pid)
      else:
         # On Windows, this can only be done with native code (like via win32com, ctypes or psutil).
         # We use psutil.
         raise Exception("cannot check if process with PID exists - package psutil not installed")
   else:
      # Unix-like OS
      # http://stackoverflow.com/a/568285/884770
      try:
         os.kill(pid, 0)
      except OSError:
         return False
      else:
         return True



def check_is_running(cbdir):
   """
   Check if a Crossbar.io node is already running on a Crossbar.io node directory.

   :param cbdir: The Crossbar.io node directory to check.
   :type cbdir: str
   """
   fp = os.path.join(cbdir, _PID_FILENAME)
   if os.path.isfile(fp):
      with open(fp) as fd:
         pid_str = fd.read()
         try:
            pid = int(pid_str)
         except ValueError:
            print("Removing corrupted Crossbar.io PID file {}".format(fp))
         else:
            if sys.platform == 'win32' and not _HAS_PSUTIL:
               # when on Windows, and we can't actually determine if the PID exists,
               # just assume it exists
               return True
            else:
               pid_exists = check_pid_exists(pid)
               if pid_exists:
                  return True
               else:
                  print("Removing stale Crossbar.io PID file {} (pointing to non-existing process with PID {})".format(fp, pid))
                  return False
   return False



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
      # could not detect UTF8 validator type/version
      utf8_ver = '?'
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
      # could not detect XOR masker type/version
      xor_ver = '?'
   if options.debug:
      xor_ver += " [%s]" % qual(XorMaskerNull)

   ## JSON Serializer
   ##
   from autobahn.wamp.serializer import JsonObjectSerializer
   s = str(JsonObjectSerializer.JSON_MODULE)
   if 'ujson' in s:
      json_ver = 'ujson-%s' % pkg_resources.require('ujson')[0].version
   else:
      json_ver = 'stdlib'

   ## MsgPack Serializer
   ##
   try:
      import msgpack
      msgpack_ver = 'msgpack-python-%s' % pkg_resources.require('msgpack-python')[0].version
   except ImportError:
      msgpack_ver = '-'

   import crossbar
   import platform

   print("")
   print("Crossbar.io package versions and platform information:")
   print("")
   print("Crossbar.io                  : {0}".format(crossbar.__version__))
   print("")
   print("  Autobahn|Python            : {0}".format(ab_ver))
   print("    WebSocket UTF8 Validator : {0}".format(utf8_ver))
   print("    WebSocket XOR Masker     : {0}".format(xor_ver))
   print("    WAMP JSON Codec          : {0}".format(json_ver))
   print("    WAMP MsgPack Codec       : {0}".format(msgpack_ver))
   print("  Twisted                    : {0}".format(tx_ver))
   print("  Python                     : {0}-{1}".format(py_ver, platform.python_implementation()))
   print("")
   print("OS                           : {0}".format(platform.platform()))
   print("Machine                      : {0}".format(platform.machine()))
   print("")



def run_command_templates(options):
   """
   Subcommand "crossbar templates".
   """
   from crossbar.controller.template import Templates

   templates = Templates()
   templates.help()



def run_command_init(options):
   """
   Subcommand "crossbar init".
   """
   from crossbar.controller.template import Templates

   templates = Templates()

   if not options.template in templates:
      print("Huh, sorry. There is no template named '{}'. Try 'crossbar templates' to list the templates available.".format(options.template))
      sys.exit(1)

   if options.appdir is None:
      options.appdir = '.'
   else:
      if os.path.exists(options.appdir):
         raise Exception("app directory '{}' already exists".format(options.appdir))

      try:
         os.mkdir(options.appdir)
      except Exception as e:
         raise Exception("could not create application directory '{}' ({})".format(options.appdir, e))
      else:
         print("Crossbar.io application directory '{}' created".format(options.appdir))

   options.appdir = os.path.abspath(options.appdir)

   print("Initializing application template '{}' in directory '{}'".format(options.template, options.appdir))
   get_started_hint = templates.init(options.appdir, options.template)

   # try:
   #    templates.init(options.appdir, options.template)
   # except Exception as e:
   #    try:
   #       shutil.rmtree(options.appdir)
   #    except:
   #       pass
   #    raise e

   print("Application template initialized")
   if get_started_hint:
      print("\n{}\n".format(get_started_hint))
   else:
      print("\nTo start your node, run 'crossbar start --cbdir {}'\n".format(os.path.abspath(os.path.join(options.appdir, '.crossbar'))))



def run_command_start(options):
   """
   Subcommand "crossbar start".
   """
   ## do not allow to run more than one Crossbar.io instance
   ## from the same Crossbar.io node directory
   ##
   if check_is_running(options.cbdir):
      print("Crossbar.io is already running from node directory {}".format(options.cbdir))
      sys.exit(1)
   else:
      fp = os.path.join(options.cbdir, _PID_FILENAME)
      with open(fp, 'w') as fd:
         fd.write("{}".format(os.getpid()))

   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   reactor = install_reactor(options.reactor, options.debug)

   ## remove node PID file when reactor exits
   ##
   def remove_pid_file():
      fp = os.path.join(options.cbdir, _PID_FILENAME)
      if os.path.isfile(fp):
         os.remove(fp)
   reactor.addSystemEventTrigger('after', 'shutdown', remove_pid_file)   

   ## start Twisted logging
   ##
   if not options.logdir:
      logfd = sys.stderr
   else:
      from twisted.python.logfile import DailyLogFile
      logfd = DailyLogFile.fromFullPath(os.path.join(options.logdir, 'node.log'))

   from crossbar.twisted.processutil import DefaultSystemFileLogObserver
   flo = DefaultSystemFileLogObserver(logfd, system = "{:<10} {:>6}".format("Controller", os.getpid()))
   log.startLoggingWithObserver(flo.emit)

   log.msg("=" * 20 + " Crossbar.io " + "=" * 20 + "\n")

   import crossbar
   log.msg("Crossbar.io {} starting".format(crossbar.__version__))

   from twisted.python.reflect import qual
   log.msg("Running on {} using {} reactor".format(platform.python_implementation(), qual(reactor.__class__).split('.')[-1]))
   log.msg("Starting from node directory {}".format(options.cbdir))

   ## create and start Crossbar.io node
   ##
   from crossbar.controller.node import Node
   node = Node(reactor, options)
   node.start()

   try:
      log.msg("Entering reactor event loop ...")
      reactor.run()
   except Exception as e:
      log.msg("Could not start reactor: {0}".format(e))



def run_command_check(options):
   """
   Subcommand "crossbar check".
   """
   from crossbar.common.checkconfig import check_config_file
   configfile = os.path.join(options.cbdir, options.config)

   print("Checking local configuration file {}".format(configfile))

   try:
     check_config_file(configfile)
   except Exception as e:
      print("\nError: {}\n".format(e))
      sys.exit(1)
   else:
      print("Ok, configuration file looks good.")
      sys.exit(0)



def run_command_convert(options):
   """
   Subcommand "crossbar convert".
   """
   from crossbar.common.checkconfig import convert_config_file
   configfile = os.path.join(options.cbdir, options.config)

   print("Converting local configuration file {}".format(configfile))

   try:
     convert_config_file(configfile)
   except Exception as e:
      print("\nError: {}\n".format(e))
      sys.exit(1)
   else:
      sys.exit(0)



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

   parser_init.add_argument('--appdir',
                             type = str,
                             default = None,
                             help = "Application base directory where to create app and node from template.")


   ## "templates" command
   ##
   parser_templates = subparsers.add_parser('templates',
                                            help = 'List templates available for initializing a new Crossbar.io node.')

   parser_templates.set_defaults(func = run_command_templates)



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
                             default = None,
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


   ## "convert" command
   ##
   parser_check = subparsers.add_parser('convert',
                                        help = 'Convert a Crossbar.io node`s local configuration file from JSON to YAML or vice versa.')

   parser_check.set_defaults(func = run_command_convert)

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
         for f in ['config.json', 'config.yaml']:
            f = os.path.join(options.cbdir, f)
            if os.path.isfile(f) and os.access(f, os.R_OK):
               options.config = f
               break
         if not options.config:
            raise Exception("No config file specified, and neither CBDIR/config.json nor CBDIR/config.yaml exists")
      else:
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
   try:
      run()
   except Exception as e:
      print("\nError: {}\n".format(e))
      traceback.print_exc()
      sys.exit(1)
   else:
      sys.exit(0)
