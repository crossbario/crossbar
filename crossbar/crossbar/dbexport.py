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


import sys, datetime, os, re

from twisted.internet import utils, protocol, defer
from twisted.python import log
from twisted.internet.error import ProcessDone, ProcessTerminated

from crossbar.platform import SYSCMD_ZIP, SYSCMD_SQLITE3


class DbExportZipperProtocol(protocol.ProcessProtocol):

   def __init__(self, d, outdir, outurl, infile, password, extrafiles = []):
      self.d = d
      self.outdir = outdir
      self.outurl = outurl
      self.infile = infile
      self.outfile = '%s.zip' % self.infile
      self.password = password
      self.extrafiles = extrafiles
      self.stderr_data = ""

   def run(self):
      cmd = ['zip', '-q', '-9', '-j']
      if self.password is not None:
         cmd.append('-e')
         cmd.append('-P%s' % self.password)
      cmd.append(self.outfile)
      cmd.append(self.infile)
      for e in self.extrafiles:
         if os.path.exists(e):
            cmd.append(e)
      log.msg("%s %s %s", (SYSCMD_ZIP, cmd, self.outdir))
      from twisted.internet import reactor
      reactor.spawnProcess(self,
                           SYSCMD_ZIP,
                           cmd,
                           path = self.outdir)

   def connectionMade(self):
      self.transport.closeStdin()

   def outReceived(self, data):
      self.stderr_data += data

   def errReceived(self, data):
      self.stderr_data += data

   def processEnded(self, reason):
      if isinstance(reason.value, ProcessDone):
         try:
            os.remove(os.path.join(self.outdir, self.infile))
         except Exception, e:
            self.d.errback(e)
         self.d.callback("%s/%s" % (self.outurl, self.outfile))
      else:
         log.msg("ZIPing SQLite database dump failed")
         log.msg(self.stderr_data)
         self.d.errback(reason)


class DbExportProtocol(protocol.ProcessProtocol):
   """
   SQLite database dumper as Twisted process protocol.
   """

   MODE_BACKUP = 1
   MODE_DIAGNOSTICS = 2

   def __init__(self, d, services, dbfile, dbversion, outdir, outurl, password = None, mode = MODE_BACKUP, logsdir = None):
      """
      Create a ZIP file with a dump of a SQLite database.

      :param d: A deferred which gets fired upon completion.
      :type d: A twisted.internet.defer.Deferred
      :param dbfile: Full path to SQLite database file to export.
      :type dbfile: str
      :param dbversion: Appliance database version.
      :type dbversion: int
      :param outdir: Output directory where to create dump file.
      :type outdir: str
      :param password: Password to encrypt ZIP file or None.
      :type password: str
      :param mode: Export mode, one of MODE_BACKUP (normal DB dump) or MODE_DIAGNOSTICS (diagnostics file).
      :type mode: int
      :param logsdir: Directory of Twisted logs (only relevant for MODE_DIAGNOSTICS, but even there optional)
      :type logsdir: str
      """
      self.mode = mode
      self.logsdir = logsdir
      self.d = d
      self.services = services
      self.dbfile = dbfile
      self.dbversion = dbversion
      self.outdir = outdir

      if not os.path.exists(self.outdir):
         os.mkdir(self.outdir)
         log.msg("database export directory %s created" % self.outdir)

      now = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

      self.extrafiles = []

      if self.mode == DbExportProtocol.MODE_BACKUP:
         self.outfile = "crossbar_%s_%s.dump" % (now, self.dbversion)
      else:
         self.outfile = "diagnostic_crossbar_%s_%s.dump" % (now, self.dbversion)

         ## add diagnostics log
         ##
         fn = '/tmp/crossbar.diagnostic.log'
         f = open(fn, 'wb')
         f.write(self.services['platform'].getDiagnostics(as_json = True))
         f.close()
         self.extrafiles.append(fn)

         ## add crossbar.io logs (Twisted logs)
         ##
         if self.logsdir is not None:
            self._addExtra(self.logsdir, "^crossbar\.log.*$")

         ## add system logs
         ##
         # FIXME: those are world readable on FreeBSD, but only root-readble on Linux
         #self._addExtra("/var/log", "^messages.*$")

      self.stderr_data = ""
      self.zipper = DbExportZipperProtocol(d, outdir, outurl, self.outfile, password, self.extrafiles)


   def _addExtra(self, fdir, fpat):
      pat = re.compile(fpat)
      for f in os.listdir(fdir):
         if pat.match(f):
            fn = os.path.join(fdir, f)
            if os.path.isfile(fn):
               self.extrafiles.append(fn)


   def run(self):
      from twisted.internet import reactor
      reactor.spawnProcess(self,
                           SYSCMD_SQLITE3,
                           ['sqlite3',
                            self.dbfile],
                           path = self.outdir)

   def connectionMade(self):
      self.transport.write(".output '%s'\n" % self.outfile)

      if self.mode == DbExportProtocol.MODE_BACKUP:
         self.transport.write(".dump\n")
      else:
         self.transport.write(".header on\n")
         self.transport.write(".echo on\n")
         self.transport.write(".mode tabs\n")
         self.transport.write(".schema\n")
         views = ['d_config',
                  'd_license',
                  'd_servicekey',
                  'd_cookie',
                  'd_ftpuser',

                  'd_appcredential',
                  'd_clientperm',
                  'd_postrule',

                  'd_extdirectremote',
                  'd_restremote',

                  'd_hanaconnect',
                  'd_hanapushrule',
                  'd_hanaremote',

                  'd_pgconnect',
                  'd_pgpushrule',
                  'd_pgremote',

                  'd_oraconnect',
                  'd_orapushrule',
                  'd_oraremote'
                  ]
         for v in views:
            self.transport.write("SELECT * FROM %s;\n" % v)

      self.transport.write(".quit\n")
      self.transport.closeStdin()

   def outReceived(self, data):
      self.stderr_data += data

   def errReceived(self, data):
      self.stderr_data += data

   def processEnded(self, reason):
      if isinstance(reason.value, ProcessDone):
         self.zipper.run()
      else:
         msg = "Export of SQLite database to dump failed"
         log.msg(msg)
         log.msg(self.stderr_data)
         self.d.errback(msg)
