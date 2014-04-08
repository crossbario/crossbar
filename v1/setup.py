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


from setuptools import setup, find_packages

## keep in sync with LONGDESC in "crossbar/servicefactory.py"
##
LONGDESC = """
Crossbar.io - The open-source multi-protocol application router.
Documentation, community and source-code at http://crossbar.io

Created by Tavendo GmbH. Get in contact at http://tavendo.com

Open-source licensed under the GNU Affero General Public License version 3
https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE
"""

## See: http://stackoverflow.com/a/7071358/884770
##
import re
VERSIONFILE="crossbar/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
   verstr = mo.group(1)
else:
   raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))


setup (
   name = 'crossbar',
   version = verstr,
   description = 'Crossbar.io - multi-protocol application router',
   long_description = LONGDESC,
   author = 'Tavendo GmbH',
   author_email = 'autobahnws@googlegroups.com',
   url = 'http://crossbar.io/',
   platforms = ('Any'),
   install_requires = ['setuptools>=1.4',
                       'Twisted>=Twisted-13.2',
                       'pyOpenSSL>=0.13.1',
                       'pycrypto>=2.6', # FIXME: get rid of this
                       'netaddr==0.7.10',
                       'isodate>=0.4.9',
                       'tldextract>=1.2.2',
                       'Autobahn>=0.6.5',
                       'jinja2>=2.7.1'],
   extras_require = {
      'oracle': ["cx_Oracle>=5.1.2"],
      'postgres': ["psycopg2>=2.5.1"]
   },
   entry_points = {
      'console_scripts': [
         'crossbar = crossbar.cli:run'
      ]},
   packages = find_packages() + ['twisted.plugins'],
   include_package_data = True,
   data_files = [('.', ['LICENSE'])],
   zip_safe = False,
   ## http://pypi.python.org/pypi?%3Aaction=list_classifiers
   ##
   classifiers = ["License :: OSI Approved :: GNU Affero General Public License v3",
                  "Development Status :: 4 - Beta",
                  "Environment :: Console",
                  "Framework :: Twisted",
                  "Intended Audience :: Developers",
                  "Operating System :: OS Independent",
                  "Programming Language :: Python",
                  "Topic :: Internet",
                  "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
                  "Topic :: Communications",
                  "Topic :: Database",
                  "Topic :: Home Automation",
                  "Topic :: Software Development :: Libraries",
                  "Topic :: Software Development :: Libraries :: Application Frameworks",
                  "Topic :: Software Development :: Embedded Systems",
                  "Topic :: System :: Distributed Computing",
                  "Topic :: System :: Networking"],
   keywords = 'crossbar router autobahn autobahn.ws websocket realtime rfc6455 wamp rpc pubsub oracle postgres postgresql'
)
