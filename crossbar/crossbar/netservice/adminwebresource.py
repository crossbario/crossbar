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


import pkg_resources, inspect, cgi, json, re, datetime

from twisted.python import log
from twisted.application import service
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from autobahn.util import utcnow, parseutc, utcstr

from crossbar.cryptoutil import verify_and_decrypt
from crossbar.database import Database
from crossbar.tlsctx import TlsContextFactory

from adminwebsocket import AdminWebSocketProtocol

from crossbar.adminwebmodule.appcreds import AppCreds
from crossbar.adminwebmodule.clientperms import ClientPerms
from crossbar.adminwebmodule.extdirectremotes import ExtDirectRemotes
from crossbar.adminwebmodule.ftpusers import FtpUsers
from crossbar.adminwebmodule.hanaconnects import HanaConnects
from crossbar.adminwebmodule.hanapushrules import HanaPushRules
from crossbar.adminwebmodule.hanaremotes import HanaRemotes
from crossbar.adminwebmodule.oraconnects import OraConnects
from crossbar.adminwebmodule.orapushrules import OraPushRules
from crossbar.adminwebmodule.oraremotes import OraRemotes
from crossbar.adminwebmodule.pgconnects import PgConnects
from crossbar.adminwebmodule.pgpushrules import PgPushRules
from crossbar.adminwebmodule.pgremotes import PgRemotes
from crossbar.adminwebmodule.postrules import PostRules
from crossbar.adminwebmodule.restremotes import RestRemotes
from crossbar.adminwebmodule.serviceconfig import ServiceConfig
from crossbar.adminwebmodule.servicecontrol import ServiceControl
from crossbar.adminwebmodule.servicekeys import ServiceKeys
from crossbar.adminwebmodule.servicestatus import ServiceStatus


from crossbar.adminwebmodule.uris import *
from crossbar.dbimport import UploadDatabaseDump
from crossbar.database import Database

from portconfigresource import addPortConfigResource



class ApiHelpResource(Resource):
   """
   Built-in API documentation.
   """

   def render_GET(self, request):
      help0 = ""
      help1 = ""
      cdel = 100

      prefixes = [('api', URI_API),
                  ('error', URI_ERROR),
                  ('error#remoting', URI_ERROR_REMOTING),
                  ('event', URI_EVENT),
                  ('appcred', URI_APPCRED),
                  ('postrule', URI_POSTRULE),
                  ('hanaconnect', URI_HANACONNECT),
                  ('hanapushrule', URI_HANAPUSHRULE),
                  ('hanaremote', URI_HANAREMOTE),
                  ('pgconnect', URI_PGCONNECT),
                  ('pgpushrule', URI_PGPUSHRULE),
                  ('pgremote', URI_PGREMOTE),
                  ('oraconnect', URI_ORACONNECT),
                  ('orapushrule', URI_ORAPUSHRULE),
                  ('oraremote', URI_ORAREMOTE),
                  ('servicekey', URI_SERVICEKEY),
                  ('clientperm', URI_CLIENTPERM),
                  ('extdirectremote', URI_EXTDIRECTREMOTE),
                  ('restremote', URI_RESTREMOTE),
                  ('ftpuser', URI_FTPUSER),
                  ]

      for p in prefixes:
         help0 += "%s %s\n" % (p[0] + ' ' * (20 - len(p[0])), p[1])
      help0 += "\n\n"

      docclasses = [AdminWebSocketProtocol,
                    AppCreds,
                    ClientPerms,
                    ExtDirectRemotes,
                    FtpUsers,
                    HanaConnects,
                    HanaPushRules,
                    HanaRemotes,
                    OraConnects,
                    OraPushRules,
                    OraRemotes,
                    PgConnects,
                    PgPushRules,
                    PgRemotes,
                    PostRules,
                    RestRemotes,
                    ServiceConfig,
                    ServiceControl,
                    ServiceKeys,
                    ServiceStatus]

      docmethods = []

      for cls in docclasses:
         methods = []
         #print cls.__dict__
         for an in sorted(cls.__dict__):
            a = getattr(cls, an)
            if callable(a) and a.__dict__.has_key('_autobahn_rpc_id'):
               methods.append(a.__name__)
         if cls.__dict__.has_key('DOCNAME'):
            docname = cls.DOCNAME
         else:
            docname = cls.__name__
         docmethods.append((cls, docname, methods))

      #log.msg(docmethods)

      for cls, docname, methods in docmethods:
         #help1 += "\n\n%s\n" % docname
         help1 += "\n\n"
         if cls.__doc__:
            s = cls.__doc__.strip()
            i = s.find('.')
            if i > 0:
               s = s[:i]
            help1 += s + "\n"
         else:
            help1 += "Undocumented"
         help1 += "=" * cdel + "\n\n"
         for m in methods:
            fun = getattr(cls, m)
            #help1 += "\n\n%s.%s\n" % (cls.__name__, fun.__name__)
            signature = []
            fargs = inspect.getargspec(fun).args
            fdefaults = inspect.getargspec(fun).defaults
            if fdefaults is None:
               fdefaults = ()
            i = 1
            k = len(fargs) - len(fdefaults)
            for a in fargs[1:]:
               xx = str(a)
               if i >= k:
                  d = fdefaults[i - k]
                  if d is None:
                     d = "null"
                  elif d == True:
                     d = "true"
                  elif d == False:
                     d = "false"
                  xx += " [Default: %s]" % str(d)
               signature.append(xx)
               i += 1

            help1 += "\napi:%s (%s)\n" % (fun._autobahn_rpc_id, ', '.join(signature))
            help1 += "." * cdel + "\n\n"
            if fun.__doc__:
               fdoc = cgi.escape(inspect.getdoc(fun))
            else:
               fdoc = "Documentation missing."
            help1 += "%s\n\n\n" % fdoc

      html = """
<html>
   <body style="background-color: #fff; color: #333; font-family: Consolas, monospace;">
      <div style="position: relative; width: 100%%;">
         <div style="margin: auto; width: 960px;">
            <h1>API Documentation</h1>

            <h2>Prefixes</h2>
            <pre style="font-family: Consolas, monospace;">%s</pre>

            <h2>RPCs</h2>
            <pre style="font-family: Consolas, monospace;">%s</pre>
         </div>
      </div>
   </body>
</html>"""
      return html % (help0, help1)


ACTIVATE_DENY_HTML = """<!DOCTYPE html>
<html>
   <head>
      <style>
         body {
            background: #fff;
            color: #f00;
            font-family: sans-serif;
            font-size: 24px;
         }
      </style>
   </head>
   <body>
      <p>License activation failed: <b>%(reason)s</b></p>
   </body>
</html>
"""


class Activate(Resource):
   """
   License activation web resource.
   """

   def __init__(self, dbpool, services):
      Resource.__init__(self)
      self.dbpool = dbpool
      self.services = services


   def deny(self, request, reason):
      """
      Called when HTTP/POST is denied.
      """
      request.setResponseCode(400)
      return ACTIVATE_DENY_HTML % {'reason': str(reason)}


   def _activateLicense(self, txn, license, licenseRaw):

      now = utcnow()
      txn.execute("SELECT license_id FROM license WHERE enabled = 1 AND valid_from <= ? AND valid_to > ?", [now, now])
      res = txn.fetchone()
      if res:
         raise Exception("there is already a active license (%s)" % res[0])

      txn.execute("INSERT INTO license (created, license, enabled, license_id, host_id, instance_id, valid_from, valid_to, license_type, connection_cap, tls_enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  [now,
                   licenseRaw,
                   1,
                   license['license-id'],
                   license['host-id'],
                   license['instance-id'],
                   license['valid-from'],
                   license['valid-to'],
                   license['type'],
                   int(license['connection-cap']),
                   1 if license['tls-enabled'] else 0])
      return "OK, license inserted"


   def _onLicenseActivateSuccess(self, res, request):
      ## reload admin UI
      ##
      log.msg("\n\n!!! LICENSE ACTIVATED !!!\n\n")
      request.write(redirectTo("/", request))
      request.finish()

   def _onLicenseActivateError(self, res, request):
      request.write(self.deny(request, res))
      request.finish()

   def render_POST(self, request):
      """
      Perform license activation. The POST must contain a 'payload' field.
      Payload must be a string consisting of 3 substrings concatenated
      by comma:

         msg, key, sig

         msg: the AES encrypted license
         key: the RSA encrypted AES key
         sig: the RSA signature over the encrypted msg and key

      For details, see cryptoutil.verify_and_decrypt.
      """
      try:
         args = request.args
         headers = request.getAllHeaders()

         if headers.get("content-type", "missing") != 'application/x-www-form-urlencoded':
            return self.deny(request, "bad or missing content type ('%s')" % headers.get("content-type", "missing"))

         if args.has_key('payload'):
            payload = request.args['payload'][0]
         else:
            return self.deny(request, "1: missing payload field")

         # remove any whitespace (also line) from payload string
         re.sub(r'\s', '', payload)

         log.msg("License activation received:")
         log.msg("Raw License: " + payload)

         try:
            license = Database.parseLicense(self.services["config"].get('instance-priv-key'), payload)
         except Exception, e:
            return self.deny(request, "2: " + str(e))

         hostid = str(self.services['platform'].getHostId())
         if hostid != license['host-id']:
            return self.deny(request, "3: license is for host-id '%s', but this host has host-id '%s'" % (license['host-id'], hostid))

         instanceid = str(self.services['config'].get("instance-id"))
         if instanceid != license['instance-id']:
            return self.deny(request, "4: license is for instance-id '%s', but this instance has instance-id '%s'" % (license['instance-id'], instanceid))

         validfrom = parseutc(license['valid-from'])
         validto = parseutc(license['valid-to'])
         now = datetime.datetime.utcnow()
         if now < validfrom:
            return self.deny(request, "5: license is not yet valid (license validity %s - %s, now is %s)" % (license['valid-from'], license['valid-to'], utcstr(now)))
         if now >= validto:
            return self.deny(request, "6: license is expired (license validity %s - %s, now is %s)" % (license['valid-from'], license['valid-to'], utcstr(now)))

         d = self.dbpool.runInteraction(self._activateLicense, license, payload)

         d.addCallback(lambda res: self._onLicenseActivateSuccess(res, request))
         d.addErrback(lambda res: self._onLicenseActivateError(res, request))

         ## avoid module level import of reactor
         from twisted.web.server import NOT_DONE_YET

         return NOT_DONE_YET

      except Exception, e:
         ## catch all .. should not happen (usually)
         return self.deny(request, "0: internal error (%s)" % str(e))


class AdminWebService(service.Service):

   SERVICENAME = "Admin Web"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False
      self.factory = None
      self.listener = None

   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)

      ## avoid module level reactor import
      from twisted.web.static import File
      from twisted.web.server import Site

      ## Crossbar.io Dashboard
      ##
      try:
         import crossbardashboard
         root = File(pkg_resources.resource_filename("crossbardashboard", "web"))

      except ImportError, e:
         log.msg("Crossbar.io Dashboard not installed [%s]" % e)
         root = Resource()

      else:
         log.msg("Found Crossbar.io Dashboard package v%s" % crossbardashboard.__version__)

         ## Crossbar.io ControlCenter
         ##
         try:
            import crossbarcontrolcenter
            root.putChild("controlcenter", File(pkg_resources.resource_filename("crossbarcontrolcenter", "web")))
         except ImportError, e:
            log.msg("Crossbar.io ControlCenter not installed [%s]" % e)
         else:
            log.msg("Found Crossbar.io ControlCenter package v%s" % crossbarcontrolcenter.__version__)

         ## Crossbar.io CodeLab
         ##
         try:
            import crossbarcodelab
            root.putChild("codelab", File(pkg_resources.resource_filename("crossbarcodelab", "web")))
         except ImportError, e:
            log.msg("Crossbar.io CodeLab not installed [%s]" % e)
         else:
            log.msg("Found Crossbar.io CodeLab package v%s" % crossbarcodelab.__version__)

         ## Crossbar.io Manual
         ##
         try:
            import crossbarmanual
            root.putChild("manual", File(pkg_resources.resource_filename("crossbarmanual", "web")))
         except ImportError, e:
            log.msg("Crossbar.io Manual not installed [%s]" % e)
         else:
            log.msg("Found Crossbar.io Manual package v%s" % crossbarmanual.__version__)


      ## REST interface to get config values
      ##
      addPortConfigResource(self.services["config"], root, "config")

      ## API Documentation
      ##
      root.putChild("apidoc", ApiHelpResource())

      ## Database Export
      ##
      dbexp = File(str(self.services["config"].get("export-dir")))
      root.putChild(str(self.services["config"].get("export-url")), dbexp)

      ## Database Import
      ##
      dbimp = UploadDatabaseDump(str(self.services["config"].get("import-dir")))
      root.putChild(str(self.services["config"].get("import-url")), dbimp)

      ## Activate
      ##
      root.putChild("doactivate", Activate(self.dbpool, self.services))


      ## create twisted.web Site
      ##
      factory = Site(root)
      factory.log = lambda _: None # disable any logging

      cfg = self.services["config"]

      port = cfg["admin-web-port"]
      if cfg["admin-web-tls"]:
         contextFactory = TlsContextFactory(cfg["admin-web-tlskey-pem"],
                                            cfg["admin-web-tlscert-pem"],
                                            dhParamFilename = self.services['master'].dhParamFilename)
         self.listener = self.reactor.listenSSL(port, factory, contextFactory)
      else:
         self.listener = self.reactor.listenTCP(port, factory)

      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
         self.factory = None
      self.isRunning = False
