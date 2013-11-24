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

__all__ = ['run']


import sys, json, argparse, pkg_resources, logging
from pprint import pprint

from twisted.python import log
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from autobahn.websocket import connectWS
from autobahn.wamp import WampClientFactory, WampCraClientProtocol



def tabify(fields, formats, truncate = 120, filler = ['-', '+']):
   """
   Tabified output formatting.
   """

   ## compute total length of all fields
   ##
   totalLen = 0
   flexIndicators = 0
   flexIndicatorIndex = None
   for i in xrange(len(formats)):
      ffmt = formats[i][1:]
      if ffmt != "*":
         totalLen += int(ffmt)
      else:
         flexIndicators += 1
         flexIndicatorIndex = i

   if flexIndicators > 1:
      raise Exception("more than 1 flex field indicator")

   ## reserve space for column separators (" | " or " + ")
   ##
   totalLen += 3 * (len(formats) - 1)

   if totalLen > truncate:
      raise Exception("cannot fit content in truncate length %d" % truncate)

   r = []
   for i in xrange(len(formats)):

      if i == flexIndicatorIndex:
         N = truncate - totalLen
      else:
         N = int(formats[i][1:]) 

      if fields:
         s = str(fields[i])
         if len(s) > N:
            s = s[:N-2] + ".."
         l = N - len(s)
         m = formats[i][0]
      else:
         s = ''
         l = N
         m = '+'

      if m == 'l':
         r.append(s + ' ' * l)
      elif m == 'r':
         r.append(' ' * l + s)
      elif m == 'c':
         c1 = l / 2
         c2 = l - c1
         r.append(' ' * c1 + s + ' ' * c2)
      elif m == '+':
         r.append(filler[0] * l)
      else:
         raise Exception("invalid field format")

   if m == '+':
      return (filler[0] + filler[1] + filler[0]).join(r)
   else:
      return ' | '.join(r)



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



class CrossbarCLIProtocol(WampCraClientProtocol):

   def connectionMade(self):
      if self.factory.options.verbose:
         sys.stdout.write(" .. (1) connected ..")

      WampCraClientProtocol.connectionMade(self)


   def onSessionOpen(self):
      if self.factory.options.verbose:
         sys.stdout.write(" (2) session opened ..")

      d = self.authenticate(authKey = self.factory.options.user,
                            authSecret = self.factory.options.password)
      d.addCallbacks(self.onAuthSuccess, self.onAuthError)


   def onClose(self, wasClean, code, reason):
      try:
         self.factory.reactor.stop()
      except:
         pass


   def onAuthSuccess(self, permissions):
      if self.factory.options.verbose:
         sys.stdout.write(" (3) authenticated. Ok.\n\n")

      self.prefix("api", "http://crossbar.io/api#");
      self.prefix("error", "http://crossbar.io/error#");
      self.prefix("event", "http://crossbar.io/event#");
      self.prefix("wiretap", "http://crossbar.io/event/wiretap#");

      CMDS = {'restart': self.cmd_restart,
              'log': self.cmd_log,
              'status': self.cmd_status,
              'watch': self.cmd_watch,
              'config': self.cmd_config,
              'modify': self.cmd_modify,
              'scratchdb': self.cmd_scratchdb,
              'scratchweb': self.cmd_scratchweb,
              'connect': self.cmd_connect,
              'wiretap': self.cmd_wiretap}

      if CMDS.has_key(self.factory.options.command):
         CMDS[self.factory.options.command]()
      else:
         self.factory.done = True
         raise Exception("unknown command '%s'" % self.factory.options.command)


   def onAuthError(self, e):
      uri, desc, details = e.value.args
      if not self.factory.options.json:
         print
         print "Error: authentication failed [%s]" % desc
      self.factory.done = True
      self.sendClose()


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


   @inlineCallbacks
   def cmd_status(self):
      """
      'status' command.
      """
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
      if self.factory.options.json:
         print json.dumps(res)
      else:

         LINELENGTH = 118

         print
         print tabify(['Crossbar.io Status'], ['c97'], LINELENGTH)
         print

         cnames = {'ora': 'Oracle', 'rest': 'REST', 'pg': 'PostgreSQL', 'hana': 'SAP HANA'}

         LINEFORMAT = ['l15', 'c41', 'c41']
         print tabify(None, LINEFORMAT, LINELENGTH)
         print tabify(['',
                       'PubSub',
                       'RPC',
                       ], LINEFORMAT, LINELENGTH)

         LINEFORMAT = ['l15', 'c19', 'c19', 'c19', 'c19']
         print tabify(None, LINEFORMAT, LINELENGTH)

         print tabify(['',
                       'Publish',
                       'Dispatch',
                       'Call',
                       'Forward',
                       ], LINEFORMAT, LINELENGTH)

         LINEFORMAT = ['l15']
         for i in xrange(8):
            LINEFORMAT.append('c8')
         print tabify(None, LINEFORMAT, LINELENGTH)

         print tabify(['',
                       'allowed',
                       'denied',
                       'success',
                       'failed',
                       'allowed',
                       'denied',
                       'success',
                       'failed',
                       ], LINEFORMAT, LINELENGTH)
         print tabify(None, LINEFORMAT, LINELENGTH)

         LINEFORMAT = ['l15']
         for i in xrange(8):
            LINEFORMAT.append('r8')

         for s in ['rest', 'ora', 'pg']:
#         for s in ['rest', 'pg', 'ora', 'hana']:
            dp = res['pusher'][s]
            dr = res['remoter'][s]
            print tabify([cnames[s],
                         dp['publish-allowed'],
                         dp['publish-denied'],
                         dp['dispatch-success'],
                         dp['dispatch-failed'],
                         dr['call-allowed'],
                         dr['call-denied'],
                         dr['forward-success'],
                         dr['forward-failed'],
                         ], LINEFORMAT, LINELENGTH)
         print tabify(None, LINEFORMAT, LINELENGTH)
         print

      self.factory.done = True
      self.sendClose()


   def cmd_connect(self):
      """
      'connect' command.
      """
      print "Crossbar is alive!"
      self.factory.done = True
      self.sendClose()


   @inlineCallbacks
   def cmd_restart(self):
      """
      'restart' command.
      """
      if not self.factory.options.json:
         print "Restarting Crossbar.io .."

      res = yield self.call("api:restart")


   @inlineCallbacks
   def cmd_scratchdb(self):
      """
      'scratchdb' command.
      """
      restart = self.factory.options.restart
      if not self.factory.options.json:
         if restart:
            print "Scratching service database and immediate restarting .."
         else:
            print "Scratching service database .."

      res = yield self.call("api:scratch-database", restart)

      if not self.factory.options.json:
         print "Service database initialized to factory default."
         if not restart:
            print "You must restart Crossbar.io for settings to become effective."
      else:
         print json.dumps(res)

      if not restart:
         self.factory.done = True
         self.sendClose()


   @inlineCallbacks
   def cmd_scratchweb(self):
      """
      'scratchweb' command.
      """
      demoinit = self.factory.options.demoinit

      if not self.factory.options.json:
         print "Scratching Web directory .."

      res = yield self.call("api:scratch-webdir", demoinit)

      if not self.factory.options.json:
         if demoinit:
            print "Scratched Web directory and copied %d files (%d bytes)." % (res[0], res[1])
         else:
            print "Scratched Web directory."
      else:
         print json.dumps(res)

      self.factory.done = True
      self.sendClose()


   @inlineCallbacks
   def cmd_log(self):
      """
      'log' command.
      """
      def _printlog(self, logobj):
         if self.factory.options['json']:
            print json.dumps(logobj)
         else:
            lineno, timestamp, logclass, logmodule, message = logobj
            print str(lineno).zfill(6), timestamp, logclass.ljust(7), (logmodule + ": " if logmodule.strip() != "-" else "") + message

      def _onlog(self, topic, event):
         _printlog(event)

      try:
         limit = int(self.factory.options['limit'])
      except:
         limit = 0
      self.subscribe("event:on-log", _onlog)
      res = yield self.call("api:get-log", limit)
      for l in res:
         _printlog(l)


   @inlineCallbacks
   def cmd_wiretap(self):
      """
      'wiretap' command.

      session.call("http://api.wamp.ws/procedure#echo", "hello").then(ab.log, ab.log);
      """

      def _onwiretap(topic, event):
         print topic, event

      sessionid = self.factory.options.sessionid
      topic = "wiretap:%s" % sessionid
      self.subscribe(topic, _onwiretap)
      r = yield self.call("api:set-wiretap-mode", sessionid, True)
      print "listening on", topic


   @inlineCallbacks
   def cmd_config(self):
      """
      'config' command
      """
      ctype = self.factory.options.type

      if ctype == 'settings':
         res = yield self.call("api:get-config")

      elif ctype == 'appcreds':
         res = yield self.call("api:get-appcreds")

      elif ctype == 'clientperms':
         res = yield self.call("api:get-clientperms")

      elif ctype == 'postrules':
         res = yield self.call("api:get-postrules")

      elif ctype == 'extdirectremotes':
         res = yield self.call("api:get-extdirectremotes")

      elif ctype == 'oraconnects':
         res = yield self.call("api:get-oraconnects")

      elif ctype == 'orapushrules':
         res = yield self.call("api:get-orapushrules")

      elif ctype == 'oraremotes':
         res = yield self.call("api:get-oraremotes")

      else:
         raise Exception("logic error")

      pprint(res)

      self.factory.done = True
      self.sendClose()


   @inlineCallbacks
   def cmd_modify(self):
      """
      'modify' command
      """
      config = json.loads(open(self.factory.options.config).read())
      restart = self.factory.options.restart

      if config.has_key('settings'):
         r = yield self.call("api:modify-config", config['settings'])
         pprint(r)

      if config.has_key('appcreds'):
         appcreds = yield self.call("api:get-appcreds")
         for ac in appcreds:
            print "dropping application credential", ac['uri']
            r = yield self.call("api:delete-appcred", ac['uri'], True)
         for id, ac in config['appcreds'].items():
            r = yield self.call("api:create-appcred", ac)
            config['appcreds'][id] = r
            print "application credential created:"
            pprint(r)

      if config.has_key('clientperms'):
         clientperms = yield self.call("api:get-clientperms")
         for cp in clientperms:
            print "dropping client permission ", cp['uri']
            r = yield self.call("api:delete-clientperm", cp['uri'])
         for id, cp in config['clientperms'].items():
            if cp["require-appcred-uri"] is not None:
               k = cp["require-appcred-uri"]
               cp["require-appcred-uri"] = config['appcreds'][k]['uri']
            r = yield self.call("api:create-clientperm", cp)
            config['clientperms'][id] = r
            print "client permission created:"
            pprint(r)

      if config.has_key('postrules'):
         postrules = yield self.call("api:get-postrules")
         for pr in postrules:
            print "dropping post rule", pr['uri']
            r = yield self.call("api:delete-postrule", pr['uri'])
         for id, pr in config['postrules'].items():
            if pr["require-appcred-uri"] is not None:
               k = pr["require-appcred-uri"]
               pr["require-appcred-uri"] = config['appcreds'][k]['uri']
            r = yield self.call("api:create-postrule", pr)
            config['postrules'][id] = r
            print "post rule created:"
            pprint(r)

      if config.has_key('extdirectremotes'):
         extdirectremotes = yield self.call("api:get-extdirectremotes")
         for er in extdirectremotes:
            print "dropping ext.direct remote", er['uri']
            r = yield self.call("api:delete-extdirectremote", er['uri'])
         for id, er in config['extdirectremotes'].items():
            if er["require-appcred-uri"] is not None:
               k = er["require-appcred-uri"]
               er["require-appcred-uri"] = config['appcreds'][k]['uri']
            r = yield self.call("api:create-extdirectremote", er)
            config['extdirectremotes'][id] = r
            print "ext.direct remote created:"
            pprint(r)

      if config.has_key('oraconnects'):
         oraconnects = yield self.call("api:get-oraconnects")
         for oc in oraconnects:
            print "dropping Oracle connect", oc['uri']
            r = yield self.call("api:delete-oraconnect", oc['uri'], True)
         for id, oc in config['oraconnects'].items():
            r = yield self.call("api:create-oraconnect", oc)
            config['oraconnects'][id] = r
            print "Oracle connect created:"
            pprint(r)

      if config.has_key('orapushrules'):
         orapushrules = yield self.call("api:get-orapushrules")
         for op in orapushrules:
            print "dropping Oracle publication rule", op['uri']
            r = yield self.call("api:delete-orapushrule", op['uri'])
         for id, op in self.factory.config['orapushrules'].items():
            if op["oraconnect-uri"] is not None:
               k = op["oraconnect-uri"]
               op["oraconnect-uri"] = config['oraconnects'][k]['uri']
            r = yield self.call("api:create-orapushrule", op)
            config['orapushrules'][id] = r
            print "Oracle publication rule created:"
            pprint(r)

      if config.has_key('oraremotes'):
         oraremotes = yield self.call("api:get-oraremotes")
         for om in oraremotes:
            print "dropping Oracle remote", om['uri']
            r = yield self.call("api:delete-oraremote", om['uri'])
         for id, om in config['oraremotes'].items():
            if om["oraconnect-uri"] is not None:
               k = om["oraconnect-uri"]
               om["oraconnect-uri"] = config['oraconnects'][k]['uri']
            if om["require-appcred-uri"] is not None:
               k = om["require-appcred-uri"]
               om["require-appcred-uri"] = config['appcreds'][k]['uri']
            r = yield self.call("api:create-oraremote", om)
            config['oraremotes'][id] = r
            print "Oracle remote created:"
            pprint(r)

      self.factory.done = True
      self.sendClose()



class CrossbarCLIFactory(WampClientFactory):

   protocol = CrossbarCLIProtocol

   def __init__(self, options, reactor):
      self.options = options
      self.done = False
      WampClientFactory.__init__(self,
                                 self.options.server,
                                 debugWamp = self.options.debug)


   def startedConnecting(self, connector):
      if self.options.verbose:
         print
         print "Connecting to Crossbar.io instance as '%s' at %s .." % (self.options.user, self.options.server)


   def _maybeReconnect(self, phase, connector, reason):
      plog = self.options.verbose or phase == 'failed' or not self.done

      if plog:
         print 'Connection %s [%s]' % (phase, reason.value)

      if self.done:
         if plog:
            print "Done"
         try:
            self.reactor.stop()
         except:
            pass
      else:
         if self.options.reconnect > 0:
            if plog:
               print "Retrying in %s seconds" % self.options.reconnect
            self.reactor.callLater(self.options.reconnect, connector.connect)
         else:
            if plog:
               print "Giving up"
            try:
               self.reactor.stop()
            except:
               pass


   def clientConnectionLost(self, connector, reason):
      self._maybeReconnect('lost', connector, reason)


   def clientConnectionFailed(self, connector, reason):
      self._maybeReconnect('failed', connector, reason)



def run_admin_command(options):
   """
   Monitor a Crossbar.io server.
   """
   from choosereactor import install_reactor
   reactor = install_reactor(options.reactor, options.verbose)

   factory = CrossbarCLIFactory(options, reactor)
   connectWS(factory)
   reactor.run()



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
                                    description = "Crossbar.io multi-protocol application router")

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

   def add_common_admin_command_arguments(_parser):
      _parser.add_argument('--reconnect',
                           default = 0,
                           type = int,
                           help = 'Reconnect interval in seconds or 0.')

      _parser.add_argument('-s',
                           '--server',
                           type = str,
                           default = 'ws://127.0.0.1:9000',
                           help = 'Administration endpoint WebSocket URI.')

      _parser.add_argument('-u',
                           '--user',
                           type = str,
                           default = 'admin',
                           help = 'User name.')

      _parser.add_argument('-p',
                           '--password',
                           type = str,
                           help = 'Password.')

   ## "status" command
   ##
   parser_status = subparsers.add_parser('status',
                                         help = 'Get server status.')

   add_common_admin_command_arguments(parser_status)
   parser_status.set_defaults(func = run_admin_command)


   ## "watch" command
   ##
   parser_watch = subparsers.add_parser('watch',
                                        help = 'Watch a server.')

   add_common_admin_command_arguments(parser_watch)
   parser_watch.set_defaults(func = run_admin_command)


   ## "restart" command
   ##
   parser_restart = subparsers.add_parser('restart',
                                          help = 'Restart a server.')

   add_common_admin_command_arguments(parser_restart)
   parser_restart.set_defaults(func = run_admin_command)


   ## "scratchdb" command
   ##
   parser_scratchdb = subparsers.add_parser('scratchdb',
                                            help = 'Scratch service database.')

   add_common_admin_command_arguments(parser_scratchdb)

   parser_scratchdb.add_argument('--restart',
                                 action = 'store_true',
                                 help = 'Immediately perform a restart.')

   parser_scratchdb.set_defaults(func = run_admin_command)


   ## "scratchweb" command
   ##
   parser_scratchweb = subparsers.add_parser('scratchweb',
                                             help = 'Scratch Web directory.')

   add_common_admin_command_arguments(parser_scratchweb)

   parser_scratchweb.add_argument('--demoinit',
                                  action = 'store_true',
                                  help = 'Initialize Web directory with demo content.')

   parser_scratchweb.set_defaults(func = run_admin_command)


   ## "wiretap" command
   ##
   parser_wiretap = subparsers.add_parser('wiretap',
                                          help = 'Wiretap a WAMP session.')

   add_common_admin_command_arguments(parser_wiretap)

   parser_wiretap.add_argument('--sessionid',
                               type = str,
                               help = 'WAMP session ID.')

   parser_wiretap.set_defaults(func = run_admin_command)


   ## "config" command
   ##
   parser_config = subparsers.add_parser('config',
                                         help = 'Get service configuration.')

   parser_config.add_argument('--type',
                              required = True,
                              choices = ['settings',
                                         'appcreds',
                                         'clientperms',
                                         'postrules',
                                         'oraconnects',
                                         'oraremotes',
                                         'orapushrules'],
                              help = 'Configuration type to retrieve.')

   add_common_admin_command_arguments(parser_config)

   parser_config.set_defaults(func = run_admin_command)


   ## "modify" command
   ##
   parser_modify = subparsers.add_parser('modify',
                                         help = 'Change service configuration.')

   add_common_admin_command_arguments(parser_modify)

   parser_modify.add_argument('--config',
                              type = str,
                              help = 'Service configuration filename.')

   parser_modify.add_argument('--restart',
                              action = 'store_true',
                              help = 'Immediately perform a restart.')

   parser_modify.set_defaults(func = run_admin_command)


   ## parse cmd line args
   ##
   options = parser.parse_args()


   ## run the subcommand selected
   ##
   options.func(options)



if __name__ == '__main__':
   run()
