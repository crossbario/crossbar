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


__all__ = ['LONGDESC', 'Options', 'makeService']


import os
from twisted.python import log
from twisted.python import usage


## keep in sync with LONGDESC in "setup.py"
##
LONGDESC = """
Crossbar.io - The open-source multi-protocol application router.
Documentation, community and source-code at http://crossbar.io

Created by Tavendo GmbH. Get in contact at http://tavendo.com

Open-source licensed under the GNU Affero General Public License version 3
https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE
"""


class Options(usage.Options):
   """
   Crossbar.io command line options when run from twistd as plugin.
   """
   longdesc = LONGDESC

   optFlags = [['debug', 'd', 'Emit debug messages']]
   optParameters = [["cbdata", "c", None, "Crossbar.io data directory (overrides environment variable CROSSBAR_DATA)."],
                    ["webdata", "w", None, "Crossbar.io static Web directory (overrides default CROSSBAR_DATA/web)."]]


def makeService(options = {}):
   """
   Main entry point into Crossbar.io application.
   This creates an instance CrossbarService which can be run under twistd
   as a plugin or directly.
   """
   ## We need to monkey patch in the new Python IO
   ## because of http://www.freebsd.org/cgi/query-pr.cgi?pr=148581
   ## when using the kqueue reactor and twistd.
   ##
   import io, __builtin__
   __builtin__.open = io.open


   ## install our log observer before anything else is done
   ##
   from crossbar.logger import Logger
   logger = Logger()
   log.addObserver(logger)
   #print "Log observers", log.theLogPublisher.observers

   ## suggest a background thread pool size
   ##
   from twisted.internet import reactor
   reactor.suggestThreadPoolSize(30)

   ## massage options
   ##
   if not options.has_key('cbdata') or not options['cbdata']:
      if os.environ.has_key("CROSSBAR_DATA"):
         options['cbdata'] = os.environ["CROSSBAR_DATA"]
         log.msg("Crossbar.io service data directory %s set from environment variable CROSSBAR_DATA." % options['cbdata'])
      else:
         options['cbdata'] = os.path.join(os.getcwd(), 'cbdata')
         log.msg("Crossbar.io service directory unspecified - using %s." % options['cbdata'])
   else:
      log.msg("Crossbar.io application data directory %s set via command line option." % options['cbdata'])

   if not options.has_key('webdata') or not options['webdata']:
      if os.environ.has_key("CROSSBAR_DATA_WEB"):
         options['webdata'] = os.environ["CROSSBAR_DATA_WEB"]
         log.msg("Crossbar.io static Web directory %s set from environment variable CROSSBAR_DATA_WEB." % options['webdata'])
      else:
         options['webdata'] = None
   else:
      log.msg("Crossbar.io static Web directory %s set via command line option." % options['webdata'])

   options['debug'] = True if options.get('debug') else False

   ## now create the Crossbar.io service object
   ##
   from crossbar.service import CrossbarService
   svc = CrossbarService(logger, options['cbdata'], options['webdata'], options['debug'])

   #from twisted.python.log import ILogObserver, FileLogObserver
   #from twisted.python.logfile import DailyLogFile

   #application = Application("myapp")
   #logfile = DailyLogFile("my.log", "/tmp")
   #application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
   #svc.setComponent(ILogObserver, None)


   return svc
