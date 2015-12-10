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
from setuptools import setup, find_packages

version = getattr(sys, "version_info", (0,))

LONGSDESC = open('README.rst').read()

# Get package version from crossbar/__init__.py
#
VERSIONFILE = "crossbar/__init__.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in {}.".format(VERSIONFILE))

#
# extra requirements for install variants
#
extras_require = {
    'db': [
        'lmdb>=0.87',                   # OpenLDAP BSD
    ],
    'dev': [
        "colorama>=0.3.3",              # BSD license
        "mock>=1.3.0",                  # BSD license
    ],
    'tls': [
        'cryptography>=0.9.3',          # Apache license
        'pyOpenSSL>=0.15.1',            # Apache license
        'pyasn1>=0.1.8',                # BSD license
        'pyasn1-modules>=0.0.7',        # BSD license
        'service_identity>=14.0.0',     # MIT license
    ],
    'manhole': [
        {
            'environment': 'python_implementation=="CPython"',
            'requires': [
                'pyasn1>=0.1.8',        # BSD license
                'pycrypto>=2.6.1',      # Public Domain license
            ]
        }
    ],
    'msgpack': [
        'msgpack-python>=0.4.6',        # Apache license
    ],
    'system': [
        'psutil>=3.2.1',                # BSD license
        {
            "environment": 'sys_platform=="linux2" or "bsd" in sys_platform or sys_platform=="darwin"',
            'requires': [
                'setproctitle>=1.1.9',  # BSD license
            ]
        },
        {
            "environment": 'sys_platform=="linux2"',
            'requires': [
                'pyinotify>=0.9.6',     # MIT license
            ]
        }
    ],
    'accelerate': [

        {
            'environment': 'python_implementation=="CPython"',
            'requires': [
                "wsaccel>=0.6.2",        # Apache 2.0
            ]
        },
        {
            'environment': 'sys_platform!="win32" and python_implementation == "CPython"',
            'requires': [
                "ujson>=1.33",           # BSD license
            ]
        }
    ],
    'oracle': [
        'cx_Oracle>=5.2',               # Python Software Foundation license
    ],
    "postgres": [
        'txpostgres>=1.4.0',            # MIT license
        {
            'environment': 'python_implementation=="CPython"',
            'requires': [
                'psycopg2>=2.6.1',      # LGPL license
            ]
        },
        {
            'environment': 'python_implementation=="PyPy"',
            'requires': [
                'psycopg2cffi>=2.7.2',  # LGPL license
            ]
        },
    ],
}

extras_require["all"] = (extras_require['db'] + extras_require['dev'] +
                         extras_require['tls'] + extras_require['manhole'] +
                         extras_require['msgpack'] + extras_require['system'] +
                         extras_require['accelerate'] +
                         extras_require['postgres'])


setup(
    name='crossbar',
    version=verstr,
    description='Crossbar.io - The Unified Application Router',
    long_description=LONGSDESC,
    author='Tavendo GmbH',
    author_email='autobahnws@googlegroups.com',
    url='http://crossbar.io/',
    platforms=('Any'),
    license="AGPL3",
    install_requires=[
        'click>=5.1',                 # BSD license
        'setuptools>=18.3.1',         # Python Software Foundation license
        'zope.interface>=4.1.2',      # Zope Public license
        'twisted>=15.4.0',            # MIT license
        'autobahn[twisted]>=0.11.0',  # MIT license
        'netaddr>=0.7.18',            # BSD license
        'pytrie>=0.2',                # BSD license
        'jinja2>=2.8',                # BSD license
        'mistune>=0.7.1',             # BSD license
        'pygments>=2.0.2',            # BSD license
        'pyyaml>=3.11',               # MIT license
        'shutilwhich>=1.1.0',         # PSF license
        'treq>=15.0.0',               # MIT license
    ],
    extras_require=extras_require,
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
                 "Programming Language :: Python :: 3.5",
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
