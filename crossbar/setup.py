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

import sys
from distutils import log

try:
   import setuptools
except ImportError:
   from ez_setup import use_setuptools
   use_setuptools()

from setuptools import setup, find_packages


## Get package version and docstring from crossbar/__init__.py
##
import re
PACKAGE_FILE = "crossbar/__init__.py"
initfile = open(PACKAGE_FILE, "rt").read()

VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, initfile, re.M)
if mo:
   verstr = mo.group(1)
else:
   raise RuntimeError("Unable to find version string in {}.".format(PACKAGE_FILE))

DSRE = r"__doc__ = \"\"\"(.*)\"\"\""
mo = re.search(DSRE, initfile, re.DOTALL)
if mo:
   docstr = mo.group(1)
else:
   raise RuntimeError("Unable to find doc string in {}.".format(PACKAGE_FILE))


extra_require_system = [
   'psutil>=2.1.1',        # BSD license
   'setproctitle>=1.1.8'   # BSD license
]
if sys.platform.startswith('linux'):
   extra_require_system.append('pyinotify>=0.9.4') ## MIT license
elif sys.platform.startswith('win'):
   ## PyWin32 - Python Software Foundation License
   pass
else:
   pass


setup (
   name = 'crossbar',
   version = verstr,
   description = 'Crossbar.io - The Unified Application Router',
   long_description = docstr,
   author = 'Tavendo GmbH',
   author_email = 'autobahnws@googlegroups.com',
   url = 'http://crossbar.io/',
   platforms = ('Any'),
   install_requires = [
      'setuptools>=2.2',            # Python Software Foundation license
      'zope.interface>=3.6.0',      # Zope Public license
      'twisted>=twisted-13.2',      # MIT license
      'autobahn[twisted]>=0.8.14',  # Apache license
      'netaddr>=0.7.11',            # BSD license
      'pytrie>=0.2',                # BSD license
      'jinja2>=2.7.2',              # BSD license
      'mistune>=0.3.0',             # BSD license
      'pygments>=1.6',              # BSD license
      'pyyaml>=3.11',               # MIT license
   ],
   extras_require = {
      'tls': [
         'cryptography>=0.4',    # Apache license
         'pyOpenSSL>=0.14',      # Apache license
         'pyasn1',               # BSD license
         'pyasn1-modules',       # BSD license
         'service_identity',     # MIT license
      ],
      'oracle': [
         'cx_Oracle>=5.1.2'      # Python Software Foundation license
      ],
      'postgres': [
         'psycopg2>=2.5.1'       # LGPL license
      ],
      'manhole': [
         'pyasn1>=0.1.7',        # BSD license
         'pycrypto>=2.6.1'       # Public Domain license
      ],
      'msgpack': [
         'msgpack-python>=0.4.2' # Apache license
      ],
      'system': extra_require_system
   },
   entry_points = {
      'console_scripts': [
         'crossbar = crossbar.controller.cli:run'
      ]},
   #packages = ['crossbar'],
   packages = find_packages(),
   include_package_data = True,
   data_files = [('.', ['LICENSE'])],
   zip_safe = False,
   ## http://pypi.python.org/pypi?%3Aaction=list_classifiers
   ##
   classifiers = ["License :: OSI Approved :: GNU Affero General Public License v3",
                  "Development Status :: 3 - Alpha",
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
