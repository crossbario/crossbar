###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
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


import sys, json, argparse, pkg_resources
from pprint import pprint

#import twisted
#import autobahn

from twisted.python import log, usage
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from autobahn.websocket import connectWS
from autobahn.wamp import WampClientFactory, WampCraClientProtocol

#import crossbar


def run_command_version(options):
   """
   Print local Crossbar.io software component types and versions.
   """

   ## Python
   ##
   py_ver = '.'.join([str(x) for x in list(sys.version_info[:3])])

   ## Twisted / Reactor
   ##
   import choosereactor
   from twisted.internet import reactor
   tx_ver = "%s-%s" % (pkg_resources.require("Twisted")[0].version, reactor.__class__.__name__)

   ## Autobahn
   ##
   import autobahn
   ab_ver = pkg_resources.require("autobahn")[0].version

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

   ## JSON Processor
   ##
   s = str(autobahn.wamp.json_lib.__name__)
   if 'ujson' in s:
      json_ver = 'ujson-%s' % pkg_resources.require('ujson')[0].version
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




class CrossbarCLIOptions(usage.Options):

   COMMANDS = ['connect',
               'config',
               'restart',
               'log',
               'status',
               'watch',
               'scratchdb',
               'scratchweb',
               'wiretap']

   optParameters = [
      ['command', 'c', None, 'Command, one of: %s [required]' % ', '.join(COMMANDS)],
      ['wsuri', 'w', None, 'Crossbar Admin WebSocket URI, i.e. "ws://192.168.1.128:9000".'],
      ['password', 'p', None, 'Crossbar Admin password.'],
      ['limit', 'l', 0, 'Limit number of log lines or records returned.'],
      ['spec', 's', None, 'Command/config spec file.'],
      ['ident', 'i', None, 'WAMP session ID, i.e. for wiretap mode.'],
   ]

   optFlags = [
      ['json', 'j', 'Output everything in JSON.'],
      ['debug', 'd', 'Enable debug output.']
   ]

   def postOptions(self):

      if not self['command']:
         raise usage.UsageError, "A command must be specified to run!"

      if not self['wsuri']:
         raise usage.UsageError, "Crossbar Admin WebSocket URI required!"
      if not self['password']:
         raise usage.UsageError, "Crossbar Admin password required!"

      if self['command'] in ['wiretap']:
         if not self['ident']:
            raise usage.UsageError, "WAMP session ID required for command '%s'." % self['command']

      if self['command'] in ['config']:
         if not self['spec']:
            raise usage.UsageError, "Command/config spec file required for command '%s'." % self['command']



class CrossbarCLIProtocol(WampCraClientProtocol):

   def connectionMade(self):
      if not self.factory.options['json']:
         print "connected."

      WampCraClientProtocol.connectionMade(self)


   def onSessionOpen(self):
      if not self.factory.options['json']:
         print "session opened."

      d = self.authenticate(authKey = self.factory.user,
                            authSecret = self.factory.password)
      d.addCallbacks(self.onAuthSuccess, self.onAuthError)


   def onClose(self, wasClean, code, reason):
      try:
         reactor.stop()
      except:
         pass


   def onAuthSuccess(self, permissions):
      if not self.factory.options['json']:
         print "authenticated."
         print

      self.prefix("api", "http://crossbar.io/api#");
      self.prefix("error", "http://crossbar.io/error#");
      self.prefix("event", "http://crossbar.io/event#");
      self.prefix("wiretap", "http://crossbar.io/event/wiretap#");

      CMDS = {'restart': self.cmd_restart,
              'log': self.cmd_log,
              'status': self.cmd_status,
              'watch': self.cmd_watch,
              'config': self.cmd_config,
              'scratchdb': self.cmd_scratchdb,
              'scratchweb': self.cmd_scratchweb,
              'connect': self.cmd_connect,
              'wiretap': self.cmd_wiretap}

      if CMDS.has_key(self.factory.command):
         CMDS[self.factory.command]()
      else:
         raise Exception("unknown command '%s'" % self.factory.command)


   def onAuthError(self, e):
      uri, desc, details = e.value.args
      if not self.factory.options['json']:
         print "Authentication Error!", uri, desc, details
      self.sendClose()


   ## WATCH Command
   ##

   BRIDGENAME = {'ora': 'Oracle',
                 'pg': 'PostgreSQL',
                 'hana': 'SAP HANA',
                 'rest': 'REST',
                 'extdirect': 'Ext.Direct'}

   REMOTERSTATMAP = {'oraremoterstat': 'ora',
                     'pgremoterstat': 'pg',
                     'hanaremoterstat': 'hana',
                     'restremoterstat': 'rest',
                     'extdirectremoterstat': 'extdirect'}

   PUSHERSTATMAP = {'orapusherstat': 'ora',
                    'pgpusherstat': 'pg',
                    'hanapusherstat': 'hana',
                    'restpusherstat': 'rest'}

   def _onremoterstat(self, topic, event):
      z = topic.split('-')[-1]
      for e in event:
         if e['uri'] is None:
            m = CrossbarCLIProtocol.BRIDGENAME[CrossbarCLIProtocol.REMOTERSTATMAP[z]] + " Remoter"
            print m.ljust(20), e

   def _onpusherstat(self, topic, event):
      z = topic.split('-')[-1]
      for e in event:
         if e['uri'] is None:
            m = CrossbarCLIProtocol.BRIDGENAME[CrossbarCLIProtocol.PUSHERSTATMAP[z]] + " Pusher"
            print m.ljust(20), e

   def cmd_watch(self):
      for k in CrossbarCLIProtocol.REMOTERSTATMAP:
         self.subscribe("event:on-%s" % k, self._onremoterstat)
      for k in CrossbarCLIProtocol.PUSHERSTATMAP:
         self.subscribe("event:on-%s" % k, self._onpusherstat)


   ## STATUS Command
   ##

   @inlineCallbacks
   def cmd_status(self):
      res = {}
      for t in ['remoter', 'pusher']:
         res[t] = {}
         for s in ['ora', 'pg', 'hana', 'rest']:
            res[t][s] = {}
            try:
               rr = yield self.call("api:get-%s%sstats" % (s, t))
               for r in rr:
                  if r['uri'] is None:
                     for k in r:
                        if k != 'uri':
                           res[t][s][k] = r[k]
            except Exception, e:
               pass
      if self.factory.options['json']:
         print json.dumps(res)
      else:
         print "Crossbar Pusher and Remoter Statistics"
         print "-" * 80
         print
         pprint(res)
      self.sendClose()


   ## CONNECT Command
   ##

   def cmd_connect(self):
      print "Crossbar is alive!"
      self.factory.reconnect = False
      self.sendClose()


   ## RESTART Command
   ##

   @inlineCallbacks
   def cmd_restart(self):
      if not self.factory.options['json']:
         print "restarting Crossbar .."

      res = yield self.call("api:restart")


   ## SCRATCHDB Command
   ##

   @inlineCallbacks
   def cmd_scratchdb(self, dorestart = False):
      if not self.factory.options['json']:
         if dorestart:
            print "scratching Crossbar service database and immediate restart .."
         else:
            print "scratching Crossbar service database .."

      res = yield self.call("api:scratch-database", dorestart)

      print "scratched service database"
      if not dorestart:
         self.sendClose()


   ## SCRATCHWEB Command
   ##

   @inlineCallbacks
   def cmd_scratchweb(self, doinit = True):
      if not self.factory.options['json']:
         print "scratching Crossbar Web directory .."

      res = yield self.call("api:scratch-webdir", doinit)
      if doinit:
         print "scratched Web directory and copied %d files (%d bytes)" % (res[0], res[1])
      else:
         print "scratched Web directory"

      self.sendClose()


   ## LOG Command
   ##

   def _printlog(self, logobj):
      if self.factory.options['json']:
         print json.dumps(logobj)
      else:
         lineno, timestamp, logclass, logmodule, message = logobj
         print str(lineno).zfill(6), timestamp, logclass.ljust(7), (logmodule + ": " if logmodule.strip() != "-" else "") + message


   def _onlog(self, topic, event):
      self._printlog(event)


   @inlineCallbacks
   def cmd_log(self):
      try:
         limit = int(self.factory.options['limit'])
      except:
         limit = 0
      self.subscribe("event:on-log", self._onlog)
      res = yield self.call("api:get-log", limit)
      for l in res:
         self._printlog(l)


   ## WIRETAP Command
   ##

   def _onwiretap(self, topic, event):
      print topic, event


   @inlineCallbacks
   def cmd_wiretap(self):
      sessionid = self.factory.options['ident']
      topic = "wiretap:%s" % sessionid
      self.subscribe(topic, self._onwiretap)
      r = yield self.call("api:set-wiretap-mode", sessionid, True)
      print "listening on", topic


   ## CONFIG Command
   ##

   @inlineCallbacks
   def cmd_config(self):

      if self.factory.config.has_key('settings'):
         r = yield self.call("api:modify-config", self.factory.config['settings'])
         pprint(r)

      if self.factory.config.has_key('appcreds'):
         appcreds = yield self.call("api:get-appcreds")
         for ac in appcreds:
            print "dropping application credential", ac['uri']
            r = yield self.call("api:delete-appcred", ac['uri'], True)
         for id, ac in self.factory.config['appcreds'].items():
            r = yield self.call("api:create-appcred", ac)
            self.factory.config['appcreds'][id] = r
            print "application credential created:"
            pprint(r)

      if self.factory.config.has_key('clientperms'):
         clientperms = yield self.call("api:get-clientperms")
         for cp in clientperms:
            print "dropping client permission ", cp['uri']
            r = yield self.call("api:delete-clientperm", cp['uri'])
         for id, cp in self.factory.config['clientperms'].items():
            if cp["require-appcred-uri"] is not None:
               k = cp["require-appcred-uri"]
               cp["require-appcred-uri"] = self.factory.config['appcreds'][k]['uri']
            r = yield self.call("api:create-clientperm", cp)
            self.factory.config['clientperms'][id] = r
            print "client permission created:"
            pprint(r)

      if self.factory.config.has_key('postrules'):
         postrules = yield self.call("api:get-postrules")
         for pr in postrules:
            print "dropping post rule", pr['uri']
            r = yield self.call("api:delete-postrule", pr['uri'])
         for id, pr in self.factory.config['postrules'].items():
            if pr["require-appcred-uri"] is not None:
               k = pr["require-appcred-uri"]
               pr["require-appcred-uri"] = self.factory.config['appcreds'][k]['uri']
            r = yield self.call("api:create-postrule", pr)
            self.factory.config['postrules'][id] = r
            print "post rule created:"
            pprint(r)

      if self.factory.config.has_key('extdirectremotes'):
         extdirectremotes = yield self.call("api:get-extdirectremotes")
         for er in extdirectremotes:
            print "dropping ext.direct remote", er['uri']
            r = yield self.call("api:delete-extdirectremote", er['uri'])
         for id, er in self.factory.config['extdirectremotes'].items():
            if er["require-appcred-uri"] is not None:
               k = er["require-appcred-uri"]
               er["require-appcred-uri"] = self.factory.config['appcreds'][k]['uri']
            r = yield self.call("api:create-extdirectremote", er)
            self.factory.config['extdirectremotes'][id] = r
            print "ext.direct remote created:"
            pprint(r)

      if self.factory.config.has_key('oraconnects'):
         oraconnects = yield self.call("api:get-oraconnects")
         for oc in oraconnects:
            print "dropping Oracle connect", oc['uri']
            r = yield self.call("api:delete-oraconnect", oc['uri'], True)
         for id, oc in self.factory.config['oraconnects'].items():
            r = yield self.call("api:create-oraconnect", oc)
            self.factory.config['oraconnects'][id] = r
            print "Oracle connect created:"
            pprint(r)

      if self.factory.config.has_key('orapushrules'):
         orapushrules = yield self.call("api:get-orapushrules")
         for op in orapushrules:
            print "dropping Oracle publication rule", op['uri']
            r = yield self.call("api:delete-orapushrule", op['uri'])
         for id, op in self.factory.config['orapushrules'].items():
            if op["oraconnect-uri"] is not None:
               k = op["oraconnect-uri"]
               op["oraconnect-uri"] = self.factory.config['oraconnects'][k]['uri']
            r = yield self.call("api:create-orapushrule", op)
            self.factory.config['orapushrules'][id] = r
            print "Oracle publication rule created:"
            pprint(r)

      if self.factory.config.has_key('oraremotes'):
         oraremotes = yield self.call("api:get-oraremotes")
         for om in oraremotes:
            print "dropping Oracle remote", om['uri']
            r = yield self.call("api:delete-oraremote", om['uri'])
         for id, om in self.factory.config['oraremotes'].items():
            if om["oraconnect-uri"] is not None:
               k = om["oraconnect-uri"]
               om["oraconnect-uri"] = self.factory.config['oraconnects'][k]['uri']
            if om["require-appcred-uri"] is not None:
               k = om["require-appcred-uri"]
               om["require-appcred-uri"] = self.factory.config['appcreds'][k]['uri']
            r = yield self.call("api:create-oraremote", om)
            self.factory.config['oraremotes'][id] = r
            print "Oracle remote created:"
            pprint(r)

      self.sendClose()



class CrossbarCLIFactory(WampClientFactory):

   protocol = CrossbarCLIProtocol

   def __init__(self, options, debug):
      self.options = options
      self.user = "admin"
      self.password = options["password"]
      self.command = options["command"]
      if self.command == 'connect':
         self.reconnect = True
      else:
         self.reconnect = False
      if options["spec"]:
         self.config = json.loads(open(options["spec"]).read())
      else:
         self.config = None
      WampClientFactory.__init__(self, options["wsuri"], debugWamp = debug)

   def startedConnecting(self, connector):
      if not self.options['json']:
         print 'connecting ..'

   #def buildProtocol(self, addr):
   #    print 'Connected.'
   #    return CrossbarCLIProtocol()

   def clientConnectionLost(self, connector, reason):
      if not self.options['json']:
         print
         print 'lost connection [%s]' % reason.value
      if self.reconnect:
         connector.connect()
      else:
         try:
            reactor.stop()
         except:
            pass

   def clientConnectionFailed(self, connector, reason):
      if not self.options['json']:
         print
         print 'connection failed [%s]' % reason.value
      if self.reconnect:
         connector.connect()
      else:
         try:
            reactor.stop()
         except:
            pass



def run_command_client():

   o = CrossbarCLIOptions()
   try:
      o.parseOptions()
   except usage.UsageError, errortext:
      print '%s %s\n' % (sys.argv[0], errortext)
      print 'Try %s --help for usage details\n' % sys.argv[0]
      print
      print "Twisted %s" % twisted.__version__
      print "AutobahnPython %s" % autobahn.version
      sys.exit(1)

   debug = o.opts['debug']
   if debug:
      log.startLogging(sys.stdout)

   if not o['json']:
      print "Using Twisted reactor class %s" % str(reactor.__class__)

   factory = CrossbarCLIFactory(o, debug)
   connectWS(factory)
   reactor.run()

import logging

#from autobahn.utf8validator import Utf8Validator
#from twisted.python.reflect import qual
#qual(Utf8Validator)

def run_command_server(options):
   """
   Start Crossbar.io server.
   """
   ## install reactor
   import choosereactor
   from twisted.internet import reactor

   import twisted
   from crossbar import logger

   if False:
      twisted.python.log.startLogging(sys.stdout)
   else:
      flo = logger.LevelFileLogObserver(sys.stdout, level = logging.DEBUG)
      twisted.python.log.startLoggingWithObserver(flo.emit)

   #log.msg("HELLO")
   #log.msg("HELLO INFO", level = logging.INFO)
   #log.msg("HELLO ERROR", level = logging.ERROR)
   #log.msg("HELLO DEBUG", level = logging.DEBUG)
   logger.debug("HELLO DEBUG 2")
   try:
      x = 1/0
   except:
      logger.error()
      #twisted.python.log.err()
#   except Exception, e:
#      logger.error(e)

   from crossbar.servicefactory import makeService

   svc = makeService(vars(options))
   svc.startService()

   installSignalHandlers = True
   reactor.run(installSignalHandlers)

   #from crossbar.main import runDirect
   #runDirect(True, False)

   # import twisted

   # ## set background thread pool suggested size
   # from twisted.internet import reactor
   # reactor.suggestThreadPoolSize(30)

   # from crossbar.main import CrossbarService
   # from crossbar.logger import Logger

   # ## install our log observer before anything else is done
   # logger = Logger()
   # twisted.python.log.addObserver(logger)

   # ## now actually create our top service and set the logger
   # svc = CrossbarService()
   # svc.logger = logger

   # ## store user options set
   # svc.cbdata = options['cbdata']
   # svc.webdata = options['webdata']
   # svc.debug = True if options['debug'] else False
   # svc.licenseserver = options['licenseserver']
   # svc.isExe = False # will be set to true iff Crossbar is running from self-contained EXE

   # svc.startService()
   # reactor.run(True)



def parse_args():
   """
   Parse command line args to Crossbar.io tool.
   """
   parser = argparse.ArgumentParser(prog = "crossbar",
                                    description = 'Crossbar.io multi-protocol application router')

   group1dummy = parser.add_argument_group(title = 'Command, one of the following')
   group1 = group1dummy.add_mutually_exclusive_group(required = True)

   group1.add_argument("--server",
                       help = "Start Crossbar.io server.",
                       action = "store_true")

   group1.add_argument("--monitor",
                       help = "Monitor a Crossbar.io server.",
                       action = "store_true")

   group1.add_argument("--version",
                       help = "Show versions of Crossbar.io software components.",
                       action = "store_true")

   # parser.add_argument('--wsuri', dest = 'wsuri', type = str, default = 'ws://localhost:9000', help = 'The WebSocket URI the server is listening on, e.g. ws://localhost:9000.')
   # parser.add_argument('--port', dest = 'port', type = int, default = 8080, help = 'Port to listen on for embedded Web server. Set to 0 to disable.')
   # parser.add_argument('--workers', dest = 'workers', type = int, default = 3, help = 'Number of workers to spawn - should fit the number of (phyisical) CPU cores.')
   # parser.add_argument('--noaffinity', dest = 'noaffinity', action = "store_true", default = False, help = 'Do not set worker/CPU affinity.')
   # parser.add_argument('--backlog', dest = 'backlog', type = int, default = 8192, help = 'TCP accept queue depth. You must tune your OS also as this is just advisory!')
   # parser.add_argument('--silence', dest = 'silence', action = "store_true", default = False, help = 'Silence log output.')
   # parser.add_argument('--debug', dest = 'debug', action = "store_true", default = False, help = 'Enable WebSocket debug output.')
   # parser.add_argument('--interval', dest = 'interval', type = int, default = 5, help = 'Worker stats update interval.')
   # parser.add_argument('--profile', dest = 'profile', action = "store_true", default = False, help = 'Enable profiling.')

   # parser.add_argument('--fd', dest = 'fd', type = int, default = None, help = 'If given, this is a worker which will use provided FD and all other options are ignored.')
   # parser.add_argument('--cpuid', dest = 'cpuid', type = int, default = None, help = 'If given, this is a worker which will use provided CPU core to set its affinity.')

   options = parser.parse_args()

   return options



def run():
   """
   Entry point of installed Crossbar.io tool.
   """
   options = parse_args()

   if options.version:
      run_command_version(options)

   elif options.server:
      run_command_server(run_command_server)

   elif options.monitor:
      raise Exception("not implemented")

   else:
      raise Exception("logic error")



if __name__ == '__main__':
   run()


import argparse

# http://bugs.python.org/issue13879
# https://gist.github.com/sampsyo/471779

class AliasedSubParsersAction(argparse._SubParsersAction):

    class _AliasedPseudoAction(argparse.Action):
        def __init__(self, name, aliases, help):
            dest = name
            if aliases:
                dest += ' (%s)' % ','.join(aliases)
            sup = super(AliasedSubParsersAction._AliasedPseudoAction, self)
            sup.__init__(option_strings=[], dest=dest, help=help) 

    def add_parser(self, name, **kwargs):
        if 'aliases' in kwargs:
            aliases = kwargs['aliases']
            del kwargs['aliases']
        else:
            aliases = []

        parser = super(AliasedSubParsersAction, self).add_parser(name, **kwargs)

        # Make the aliases work.
        for alias in aliases:
            self._name_parser_map[alias] = parser
        # Make the help text reflect them, first removing old help entry.
        if 'help' in kwargs:
            help = kwargs.pop('help')
            self._choices_actions.pop()
            pseudo_action = self._AliasedPseudoAction(name, aliases, help)
            self._choices_actions.append(pseudo_action)

        return parser


# create the top-level parser
parser = argparse.ArgumentParser(prog = 'crossbar', description = "Crossbar.io multi-protocol application router")
#parser.register('action', 'parsers', AliasedSubParsersAction)
parser.add_argument('-d', '--debug', action = 'store_true', help = 'Debug on.')

subparsers = parser.add_subparsers(title = 'commands',
                                   help = 'Crossbar.io command to run')

# create the parser for the "a" command
parser_a = subparsers.add_parser('startserver',
                                 #aliases = ['ss'],
                                 help = 'Start a new server process.')
parser_a.add_argument('--cbdata', type = str, default = None, help = "Data directory (overrides ${CROSSBAR_DATA} and default ./cbdata)")
parser_a.add_argument('--cbdataweb', type = str, default = None, help = "Web directory (overrides ${CROSSBAR_DATA_WEB} and default CBDATA/web)")
parser_a.add_argument('--loglevel', type = str, default = 'info', choices = ['trace', 'debug', 'info', 'warn', 'error', 'fatal'], help = "Server log level (overrides default 'info')")

# create the parser for the "b" command
parser_b = subparsers.add_parser('monitorserver',
                                  #aliases = ['ms'],
                                  help = 'Connect to and monitor a server.')
parser_b.add_argument('-a', '--uri', type = str, default = 'ws://localhost/ws', help = 'Administration endpoint WebSocket URI.')
parser_b.add_argument('-u', '--user', type = str, default = 'admin', help = 'User name.')
parser_b.add_argument('-p', '--password', type = str, help = 'Password.')

# parse some argument lists
print parser.parse_args()

# http://docs.jboss.org/process-guide/en/html/logging.html
# FATAL - Use the FATAL level priority for events that indicate a critical service failure. If a service issues a FATAL error it is completely unable to service requests of any kind.
# ERROR - Use the ERROR level priority for events that indicate a disruption in a request or the ability to service a request. A service should have some capacity to continue to service requests in the presence of ERRORs.
# WARN - Use the WARN level priority for events that may indicate a non-critical service error. Resumable errors, or minor breaches in request expectations fall into this category. The distinction between WARN and ERROR may be hard to discern and so its up to the developer to judge. The simplest criterion is would this failure result in a user support call. If it would use ERROR. If it would not use WARN.
# INFO - Use the INFO level priority for service life-cycle events and other crucial related information. Looking at the INFO messages for a given service category should tell you exactly what state the service is in.
# DEBUG - Use the DEBUG level priority for log messages that convey extra information regarding life-cycle events. Developer or in depth information required for support is the basis for this priority. The important point is that when the DEBUG level priority is enabled, the JBoss server log should not grow proportionally with the number of server requests. Looking at the DEBUG and INFO messages for a given service category should tell you exactly what state the service is in, as well as what server resources it is using: ports, interfaces, log files, etc.
# TRACE - Use TRACE the level priority for log messages that are directly associated with activity that corresponds requests. Further, such messages should not be submitted to a Logger unless the Logger category priority threshold indicates that the message will be rendered. Use the Logger.isTraceEnabled() method to determine if the category priority threshold is enabled. The point of the TRACE priority is to allow for deep probing of the JBoss server behavior when necessary. When the TRACE level priority is enabled, you can expect the number of messages in the JBoss server log to grow at least a x N, where N is the number of requests received by the server, a some constant. The server log may well grow as power of N depending on the request-handling layer being traced. 
