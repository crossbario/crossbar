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

import re
import os
import sys
import platform

from setuptools import setup, find_packages, __version__ as setuptools_ver

if setuptools_ver < "20.0":
    OLD_SETUPTOOLS = True

    if "bdist_wheel" in sys.argv:
        raise ValueError("too old setuptools to do bdist_wheel")

else:
    OLD_SETUPTOOLS = False


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

CPY = platform.python_implementation() == 'CPython'
PYPY = platform.python_implementation() == 'PyPy'

# enforce use of CFFI for LMDB
if PYPY:
    os.environ['LMDB_FORCE_CFFI'] = '1'

# enforce use of bundled libsodium
os.environ['SODIUM_INSTALL'] = 'bundled'

extras_require = {}

install_requires = [
    'click>=5.1',                 # BSD license
    'setuptools>=18.3.1',         # Python Software Foundation license
    'zope.interface>=4.1.2',      # Zope Public license
    'twisted>=16.0.0',            # MIT license
    'autobahn[twisted]>=0.13.0',  # MIT license
    'netaddr>=0.7.18',            # BSD license
    'pytrie>=0.2',                # BSD license
    'jinja2>=2.8',                # BSD license
    'mistune>=0.7.1',             # BSD license
    'pygments>=2.0.2',            # BSD license
    'pyyaml>=3.11',               # MIT license
    'shutilwhich>=1.1.0',         # PSF license
    'sdnotify>=0.3.0',            # MIT license

    'psutil>=3.2.1',              # BSD license
    'lmdb>=0.88',                 # OpenLDAP BSD

    # Serializers
    'msgpack-python>=0.4.6',      # Apache 2.0 license
    'cbor>=0.1.24',               # Apache 2.0 license

    # TLS
    'cryptography>=0.9.3',        # Apache license
    'pyOpenSSL>=0.15.1',          # Apache license
    'pyasn1>=0.1.8',              # BSD license
    'pyasn1-modules>=0.0.7',      # BSD license
    'service_identity>=14.0.0',   # MIT license

    # NaCl
    'pynacl>=1.0.1',              # Apache license

    # HTTP/REST bridge (also pulls in TLS packages!)
    'treq>=15.1.0',               # MIT license

]

setproctitle_version = "1.1.9"  # BSD license
pypiwin32_version = "219"  # PSF license
pyinotify_version = "0.9.6"  # MIT license
wsaccel_version = "0.6.2"  # Apache 2.0
ujson_version = "1.33"  # BSD license


if OLD_SETUPTOOLS:

    if sys.platform != 'win32':
        # setproctitle does not provide wheels (https://github.com/dvarrazzo/py-setproctitle/issues/47) => disable on Windows
        install_requires.append('setproctitle>=' + setproctitle_version)

    if sys.platform == 'win32':
        install_requires.append('pypiwin32>=' + pypiwin32_version)

    # FIXME: https://github.com/crossbario/crossbar/issues/581
    if sys.platform.startswith('linux'):
        install_requires.append('pyinotify>=' + pyinotify_version)

    # native WebSocket/JSON acceleration - only for CPy (skip for PyPy, since it'll be _slower_ on that!)
    if CPY:
        # wsaccel does not provide wheels (https://github.com/methane/wsaccel/issues/12) => disable on Windows
        if sys.platform != 'win32':
            install_requires.append('wsaccel>=' + wsaccel_version)

        # ujson is broken on Windows (https://github.com/esnme/ultrajson/issues/184)
        if sys.platform != 'win32':
            install_requires.append("ujson>=" + ujson_version)

else:

    extras_require[":sys_platform != 'win32'"] = [
        "setproctitle>=" + setproctitle_version
    ]

    extras_require[':sys_platform == "win32"'] = [
        'pypiwin32>=' + pypiwin32_version
    ]

    extras_require[':"linux" in sys_platform'] = [
        'pyinotify>=' + pyinotify_version
    ]

    extras_require[':sys_platform != "win32" and platform_python_implementation == "CPython"'] = [
        'wsaccel>=' + wsaccel_version, 'ujson>=' + ujson_version
    ]

# For Crossbar.io development
extras_require_dev = [
    'flake8>=2.5.1',                # MIT license
    'colorama>=0.3.3',              # BSD license
    'mock>=1.3.0',                  # BSD license
    'wheel>=0.26.0',                # MIT license
]

# Crossbar.io/PostgreSQL integration
extras_require_postgres = [
    'txpostgres>=1.4.0',            # MIT license
]

psycopg2_version = "2.6.1"  # LGPL license
psycopg2cffi_version = "2.7.2"  # LGPL license

if OLD_SETUPTOOLS:
    if CPY:
        extras_require_postgres.append('psycopg2>=' + psycopg2_version)
    else:
        extras_require_postgres.append('psycopg2cffi>=' + psycopg2cffi_version)

else:
    extras_require['postgres:platform_python_implementation == "CPython"'] = [
        'psycopg2>=' + psycopg2_version
    ]

    extras_require['postgres:platform_python_implementation != "CPython"'] = [
        'psycopg2cffi>=' + psycopg2cffi_version
    ]

# Crossbar.io/Oracle integration
extras_require_oracle = [
    'cx_Oracle>=5.2',               # Python Software Foundation license
]

extras_require.update({
    'all': [],
    'dev': extras_require_dev,
    'oracle': extras_require_oracle,
    'postgres': extras_require_postgres
})


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
    install_requires=install_requires,
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
