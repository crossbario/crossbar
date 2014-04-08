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


import sys, datetime, os, zipfile, tempfile, re

from twisted.python import log
from twisted.internet import protocol, defer
from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.web.resource import Resource

from crossbar.platform import SYSCMD_SQLITE3


class DbImportProtocol(protocol.ProcessProtocol):

   def __init__(self, d, dumpfile, outfile):
      self.d = d
      self.dumpfile = dumpfile
      self.outfile = outfile
      self.stderr_data = ""

   def _removeIfExists(self, filename):
      if os.path.exists(filename):
         if os.path.isfile(filename):
            os.remove(filename)

   def run(self):
      self._removeIfExists(self.outfile)
      from twisted.internet import reactor
      reactor.spawnProcess(self,
                           SYSCMD_SQLITE3,
                           ['sqlite3',
                            self.outfile])

   def connectionMade(self):
      self.transport.write(self.dumpfile.read())
      self.transport.closeStdin()

   def outReceived(self, data):
      self.stderr_data += data

   def errReceived(self, data):
      self.stderr_data += data

   def processEnded(self, reason):
      if isinstance(reason.value, ProcessDone):
         dbinfo = GetDatabaseInfo(self.outfile)
         if dbinfo is not None:
            self.d.callback(dbinfo)
         else:
            self._removeIfExists(self.outfile)
            self.d.errback("SQLite database is not a crossbar.io service database")
      else:
         self._removeIfExists(self.outfile)
         msg = "Import of SQLite database dump failed"
         log.msg(msg)
         log.msg(self.stderr_data)
         self.d.errback(msg)


DUMP_UPLOAD_ERROR_TEMPLATE = """
<html>
   <body>
      <h1>Upload failed!</h1>
      <p>%(error)s</p>
   </body>
</html>
"""

DUMP_UPLOAD_SUCCESS_TEMPLATE = """
<html>
   <body>
      <h1>Upload succeeded. Please restart service.</h1>
      <p>Database Created <b>%(database-created)s</b></p>
      <p>Database Version <b>%(database-version)s</b></p>
   </body>
</html>
"""

class UploadDatabaseDump(Resource):

   def __init__(self, import_dir):
      Resource.__init__(self)
      self.import_dir = str(import_dir)
      if not os.path.exists(self.import_dir):
         os.mkdir(self.import_dir)
         log.msg("database import directory %s created" % self.import_dir)

   def writeSuccess(self, request, dbinfo):
      request.write(DUMP_UPLOAD_SUCCESS_TEMPLATE % dbinfo)

   def writeError(self, request, errmsg):
      #
      # Errors:
      #
      #   No dump file given
      #   File is not a zip file
      #   File is encrypted, password required for extraction
      #   Bad password for file
      #   No database dump file contained in ZIP archive
      #   Multiple database dump files in ZIP archive
      #   Import of SQLite database dump failed
      #   SQLite database is not a Autobahn WebSocket Hub database
      #
      request.write(DUMP_UPLOAD_ERROR_TEMPLATE % {"error": errmsg})

   def render_POST(self, request):

      ## avoid module level reactor import
      from twisted.web.server import NOT_DONE_YET

      if request.args.has_key('dbdump'):

         ## save uploaded file contents to temporary file
         ##
         data = request.args['dbdump'][0]
         f = tempfile.NamedTemporaryFile('wb', dir = self.import_dir)
         f.write(data)
         f.flush()

         ## if ZIP file password was given, use that
         ##
         password = None
         if request.args.has_key('password'):
            pw = request.args['password'][0].strip()
            if pw != "":
               password = pw

         z = None

         try:
            z = zipfile.ZipFile(f.name)
            if password is not None:
               z.setpassword(password)

            dfnames = z.namelist()
            pat = re.compile("^crossbar_\d{8,8}_\d{6,6}_\d+\.dump$") # crossbar_20111205_183519_37.dump
            dfn = None
            for df in dfnames:
               if pat.match(df):
                  if dfn is None:
                     dfn = df
                  else:
                     raise Exception("Multiple database dump files in ZIP archive")

            if dfn is not None:

               z.extract(dfn, self.import_dir, password)

               z.close()
               z = None
               f.close()
               f = None

               dumpfile = open(os.path.join(self.import_dir, dfn), 'rb')

               d = defer.Deferred()

               def closeremove():
                  fn = dumpfile.name
                  dumpfile.close()
                  if os.path.exists(fn) and os.path.isfile(fn):
                     os.remove(fn)

               def success(res, request):
                  closeremove()
                  self.writeSuccess(request, res)
                  request.finish()

               def error(err, request):
                  closeremove()
                  self.writeError(request, err.value)
                  request.finish()

               d.addCallbacks(success, error, callbackArgs = [request], errbackArgs = [request])

               p = DbImportProtocol(d, dumpfile, "%s.import" % DBFILE)
               p.run()

               return NOT_DONE_YET
            else:
               raise Exception("No database dump file contained in ZIP archive")

         except Exception, e:
            errmsg = e.args[0]
            self.writeError(request, errmsg)
            return ""
         finally:
            if z is not None:
               z.close()
            if f is not None:
               f.close()

      else:
         self.writeError(request, "No dump file given")
         return ""
