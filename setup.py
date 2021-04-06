#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os

from setuptools import setup, find_packages


# read package description
with open('README.rst') as f:
    long_description = f.read()

# read package version
with open('crossbar/_version.py') as f:
    exec(f.read())  # defines __version__

# we read requirements from requirements*.txt files down below
install_requires = []
extras_require = {
    'dev': []
}

# minimum, open-ended requirements
reqs = 'requirements-min.txt'

# pinned requirements
#reqs = 'requirements-pinned.txt'

# pinned & hashed requirements: we cannot use that here sadly,
# as setuptools doesn't understand hashes ..
# reqs = 'requirements.txt'

with open(reqs) as f:
    for line in f.read().splitlines():
        line = line.strip()
        if not line.startswith('#'):
            parts = line.strip().split(';')
            if len(parts) > 1:
                print('Warning: requirements line "{}" ignored, as it uses env markers, which are not supported in setuptools'.format(line))
            else:
                install_requires.append(parts)

with open('requirements-dev.txt') as f:
    for line in f.read().splitlines():
        extras_require['dev'].append(line.strip())

# enforce use of CFFI for LMDB
os.environ['LMDB_FORCE_CFFI'] = '1'

# enforce use of bundled libsodium
os.environ['SODIUM_INSTALL'] = 'bundled'

# enforce use of pure Python py-ubjson (no Cython)
os.environ['PYUBJSON_NO_EXTENSION'] = '1'

# now actually call into setuptools ..
setup(
    name='crossbar',
    version=__version__,
    description='Crossbar.io multi-protocol (WAMP/WebSocket, REST/HTTP, MQTT) application router for microservices.',
    long_description=long_description,
    author='Crossbar.io Technologies GmbH',
    url='http://crossbar.io/',
    platforms=('Any'),
    license="European Union Public Licence 1.2 (EUPL 1.2)",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        # CLI entry function
        'console_scripts': [
            'crossbar = crossbar:run'
        ]
    },
    packages=find_packages(),
    include_package_data=True,
    data_files=[('.', ['crossbar/LEGAL', 'crossbar/LICENSE', 'crossbar/LICENSE-FOR-API', 'crossbar/LICENSES-OSS'])],
    zip_safe=False,
    python_requires='>=3.7',

    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=["License :: OSI Approved :: European Union Public Licence 1.2 (EUPL 1.2)",
                 "Development Status :: 5 - Production/Stable",
                 "Environment :: No Input/Output (Daemon)",
                 "Environment :: Console",
                 "Framework :: Twisted",
                 "Intended Audience :: Developers",
                 "Operating System :: OS Independent",
                 "Programming Language :: Python :: 3.7",
                 "Programming Language :: Python :: 3.8",
                 "Programming Language :: Python :: 3.9",
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
