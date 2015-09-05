#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import sys
import re
import os
import platform
from setuptools import setup, find_packages

CPY = platform.python_implementation() == 'CPython'
PYPY = platform.python_implementation() == 'PyPy'

# Get package version and docstring from crossbar/__init__.py
#
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


#
# extra requirements for install variants
#

extras_require_system = [
    'psutil>=3.1.1',        # BSD license
]
if sys.platform.startswith('linux'):
    extras_require_system.append('setproctitle>=1.1.9')  # BSD license
    extras_require_system.append('pyinotify>=0.9.6')  # MIT license
if 'bsd' in sys.platform or sys.platform.startswith('darwin'):
    extras_require_system.append('setproctitle>=1.1.9')  # BSD license

extras_require_db = [
    'lmdb>=0.87',           # OpenLDAP BSD
]
if PYPY:
    os.environ['LMDB_FORCE_CFFI'] = '1'

extras_require_manhole = [
    'pyasn1>=0.1.8',        # BSD license
    'pycrypto>=2.6.1'       # Public Domain license
]

extras_require_msgpack = [
    'msgpack-python>=0.4.6'  # Apache license
]

extras_require_tls = [
    'cryptography>=0.9.3',          # Apache license
    'pyOpenSSL>=0.15.1',            # Apache license
    'pyasn1>=0.1.8',                # BSD license
    'pyasn1-modules>=0.0.7',        # BSD license
    'service_identity>=14.0.0',     # MIT license
]

extras_require_accelerate = [
    "wsaccel>=0.6.2",       # Apache license
    "ujson>=1.33"           # BSD License
] if CPY else []  # only for CPy (skip for PyPy)!

# Extra requirements which enhance the development experience
extras_require_dev = [
    "colorama>=0.3.3",       # BSD license
    "mock>=1.3.0",           # BSD license
]

extras_require_postgres = [
    'txpostgres>=1.4.0'   # MIT license
]
if CPY:
    # LGPL license
    extras_require_postgres.append('psycopg2>=2.6.1')
else:
    extras_require_postgres.append('psycopg2cffi>=2.7.2')

extras_require_all = extras_require_system + extras_require_db + \
    extras_require_manhole + extras_require_msgpack + extras_require_tls + \
    extras_require_accelerate + extras_require_dev

setup(
    name='crossbar',
    version=verstr,
    description='Crossbar.io - The Unified Application Router',
    long_description=docstr,
    author='Tavendo GmbH',
    author_email='autobahnws@googlegroups.com',
    url='http://crossbar.io/',
    platforms=('Any'),
    install_requires=[
        'click>=4.1',                 # BSD license
        'setuptools>=18.1',           # Python Software Foundation license
        'zope.interface>=3.6.0',      # Zope Public license
        'twisted>=15.3.0',            # MIT license
        'autobahn[twisted]>=0.10.6',  # MIT license
        'netaddr>=0.7.15',            # BSD license
        'pytrie>=0.2',                # BSD license
        'jinja2>=2.8',                # BSD license
        'mistune>=0.7',               # BSD license
        'pygments>=2.0.2',            # BSD license
        'pyyaml>=3.11',               # MIT license
        'shutilwhich>=1.1.0',         # PSF license
        'treq>=15.0.0',               # MIT license
    ],
    extras_require={
        'all': extras_require_all,
        'db': extras_require_db,
        'dev': extras_require_dev,
        'tls': extras_require_tls,
        'manhole': extras_require_manhole,
        'msgpack': extras_require_msgpack,
        'system': extras_require_system,
        'accelerate': extras_require_accelerate,
        'oracle': [
            'cx_Oracle>=5.2'         # Python Software Foundation license
        ],
        'postgres': extras_require_postgres,
    },
    entry_points={
        'console_scripts': [
            'crossbar = crossbar.controller.cli:run'
        ]},
    packages=find_packages(),
    include_package_data=True,
    data_files=[('.', ['LICENSE', 'COPYRIGHT'])],
    zip_safe=False,
    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    #
    classifiers=["License :: OSI Approved :: GNU Affero General Public License v3",
                 "Development Status :: 4 - Beta",
                 "Environment :: No Input/Output (Daemon)",
                 "Environment :: Console",
                 "Framework :: Twisted",
                 "Intended Audience :: Developers",
                 "Operating System :: OS Independent",
                 "Programming Language :: Python :: 2.7",
                 "Programming Language :: Python :: 3.3",
                 "Programming Language :: Python :: 3.4",
                 "Programming Language :: Python :: Implementation :: CPython",
                 "Programming Language :: Python :: Implementation :: PyPy",
                 "Topic :: Internet",
                 "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
                 "Topic :: Communications",
                 "Topic :: Database",
                 "Topic :: Home Automation",
                 "Topic :: Software Development :: Libraries",
                 "Topic :: Software Development :: Libraries :: Application Frameworks",
                 "Topic :: Software Development :: Embedded Systems",
                 "Topic :: Software Development :: Object Brokering",
                 "Topic :: System :: Distributed Computing",
                 "Topic :: System :: Networking"],
    keywords='crossbar router autobahn autobahn.ws websocket realtime rfc6455 wamp rpc pubsub oracle postgres postgresql'
)
