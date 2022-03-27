###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from backports.tempfile import TemporaryDirectory

##pytest_plugins = 'pytest_twisted'

"""
these are pytest fixtures for inclusion in tests. This eases common
setup/teardown code, but also limits the number of times each
fixture is instantiated, according to its scope -- so a "module"
scoped fixture, for example, will only be instantiated once per
module and re-used for all tests in that module.

see http://pytest.org/latest/fixture.html for details
"""

import os
import sys
import shutil
import json
from tempfile import mkdtemp
from functools import partial
from os import environ, path, mkdir, listdir, walk
from subprocess import check_call

from autobahn.twisted.util import sleep

from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, ensureDeferred
from twisted.internet.error import ProcessExitedAlready

import pytest

from .launcher import create_virtualenv
from .helpers import _create_temp, _cleanup_crossbar, start_cfx, start_crossbar

__all__ = (
    'session_temp',
    'temp_dir',
    'reactor',
    'virtualenv',
    'crossbar',
    'auth_crossbar',
)

crossbar_startup_timeout = 60

# XXX need to install crossbartest as well or something in
# py.test/python freaks out when trying to print tracebacks into test
# code...but that will "usually" be a local path

# set these to your local paths: '-e /home/foo/src/crossbar[tls]'
# but the below will work out-of-the-box
default_requirements = [
    '-e git+https://github.com/crossbario/txaio.git#egg=txaio',
    '-e git+https://github.com/crossbario/autobahn-python.git#egg=autobahn[twisted]',
    '-e git+https://github.com/crossbario/crossbar.git#egg=crossbar[dev]',
    '-e .'
]
# don't forget to add "~/etc/etc/crossbar" if you're making local requirements


# some py.test configuration hooks, before all the fixtures. These add
# two command-line options.
def pytest_addoption(parser):
    # if specified, we use the given virtualenv instead of a fresh
    # tmpdir one; faster if you're iterating on testing.
    parser.addoption(
        "--venv", type=str,
        help="use the given venv instead of temporary"
    )

    # if this is here at all we turn on coverage tracing
    parser.addoption(
        "--coverage", action="store_true", dest="coverage",
        help="Turn on coverage tracing of Crossbar and sub-processes."
    )

    # must add --slow to run any tests marked @pytest.mark.slowtest
    parser.addoption(
        "--slow", action="store_true", dest="slow",
        help="Turn on any tests marked slow."
    )

    # create fresh temporary and venv directories, but don't delete
    # them when we exit (e.g. for debugging)
    parser.addoption(
        "--keep", action="store_true", dest="keep",
        help="keep created temp_dir and virtualenv fixture directories",
    )

    # don't do anything at all to the venv (requires --venv)
    parser.addoption(
        "--no-install", action="store_true", dest="no_install",
        help="don't install anything in the venv given by --venv",
    )

    # enable debug-level logging in the launched crossbars
    parser.addoption(
        "--logdebug", action="store_true", dest="logdebug",
        help="enable debug-level logging in crossbar",
    )


def pytest_runtest_setup(item):
    # look for tests with @pytest.mark.slowtest on them
    # "old" pytest api now broken?
    try:
        slowmark = item.get_marker('slowtest')
    except AttributeError:
        slowmark = list(item.iter_markers(name="slowtest"))
    if slowmark:
        if not item.config.getoption('slow', False):
            pytest.skip("pass --slow to run")


# Note: it seems there can be only one "copy" of the fixtures, and
# they must appear in conftest.py In particular, *don't* import them
# into a test or the session-scoping no longer works.


@pytest.fixture(scope='session')
def session_temp(request):
    tmp = mkdtemp(prefix="cts_sess")
    def cleanup():
        if request.config.getoption('coverage', False):
            for (pth, dirs, files) in walk(tmp):
                for f in files:
                    if f.startswith('.coverage'):
                        p = path.join(pth, f)
                        print('   (session) saved "{}" to "{}".'.format(p, path.curdir))
                        shutil.move(p, path.curdir)
        if request.config.getoption('keep', False):
            print('Preserving {}'.format(tmp))
        else:
            try:
                shutil.rmtree(tmp)
            except Exception as e:
                print("Failed to remove tmpdir: {}".format(e))
    request.addfinalizer(cleanup)
    return tmp


@pytest.fixture
def temp_dir(request):
    return _create_temp(request, prefix="cts_")


@pytest.fixture(scope='session')
def reactor():
    """
    This is a session-scoped fixture to return a Twisted reactor instance.

    DO NOT import Twisted's reactor in any test files; specify a
    "reactor" arg instead to get this fixture.
    """
    import txaio
    txaio.start_logging(level='info')

    # start Autobahn's logging (so components etc used in the tests
    # have their logs produced)
    # XXX use wamp's select-reactor stuff, and-or paramtrize on the
    # different reactors we'd like to try out.
    from twisted.internet import reactor as _reactor
    return _reactor


@pytest.fixture(scope='session')
def virtualenv(request):
    """
    Session-scoped fixture to create a fresh virtualenv using the
    Python from sys.executable and install the requirements. If --venv
    is provided on py.test's command-line, we re-use that virtualenv
    (but still do the install etc).
    """

    return _create_virtualenv(request, python=sys.executable)

@pytest.fixture(scope='session')
def virtualenv3(request):
    """
    Session-scoped fixture to create a fresh virtualenv using Python3
    and install the requirements.
    """

    return _create_virtualenv(request, python='python3')

def _create_virtualenv(request, python=sys.executable):
    fixed_venv = request.config.getoption('venv', None)
    if python != sys.executable:
        fixed_venv = None  # won't re-use venvs for specific Pythons
    do_coverage = request.config.getoption('coverage', False)

    tmpdir = fixed_venv
    if tmpdir is None:
        tmpdir = mkdtemp()
        print("Creating virtualenv", tmpdir)
    else:
        print("re-using virtualenv", tmpdir)

    if default_requirements is None:
        raise RuntimeError("You must set default_requirements in {}".format(__file__))

    # XXX "the python exe" should be a fixture too -- and then vary it
    # over python, pypy etc not sys.executable
    # Could make the different package-options paramtrized too
    reqs = default_requirements
    if do_coverage and 'coverage' not in reqs:
        reqs.append('coverage')  # py.test wants coverage < 4.0

    if fixed_venv is None or not request.config.getoption('no_install', False):
        # actual venv creation
        pytest.blockon(
            ensureDeferred(
                create_virtualenv(python, tmpdir, environ, reqs, logging=False)
            )
        )

    # need to ensure venv has sitecustomize.py for coverage, and set
    # up env-var and config-file for "coverage" program
    if do_coverage:
        print("   enabling coverage in Crossbar.io + subprocesses")
        coveragerc = _write_coverage_files(tmpdir)
        environ['COVERAGE_PROCESS_START'] = coveragerc

    def cleanup():
        # if we did coverage analysis, save the .coverage* files
        # XXX do they go to temp_dir too/instead?
        if do_coverage:
            for covfile in listdir(tmpdir):
                if covfile.startswith('.coverage'):
                    p = path.join(tmpdir, covfile)
                    print('   saved "{}" to "{}".'.format(p, path.curdir))
                    shutil.move(p, path.curdir)

        if fixed_venv is None:
            if request.config.getoption('keep', False):
                print('Preserving {}'.format(tmpdir))
            else:
                try:
                    shutil.rmtree(tmpdir)
                except Exception as e:
                    print("Failed to remove tmpdir: {}".format(e))
    request.addfinalizer(cleanup)
    return tmpdir


@pytest.fixture(scope='session')
def crossbar(reactor, request, virtualenv, session_temp):
    """
    A fixture which runs a Crossbar instance in a tempdir. This
    crossbar will have minimal configuration -- the expectation is
    that tests themselves would do any additional configuration needed
    or provide their own fixture.

    This fixture is **session** scoped, so there will just be a single
    Crossbar instance created per test-run. Tests should take care not
    to do anything catastrophic to the instance, or use their own
    instance in that case. Or, we could make it scope='function'...
    """

    print("Starting Crossbar.io. scope='{0}'".format(request.scope))

    # XXX could pytest.mark.paramtrize on transports, for example, to
    # test both websocket and rawsocket -- but then would need to
    # provide the configuration onwards somehow...
    crossbar_config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee",
                "type": "router",
#                "options": {
#                    "auto_realms": True,
#                },
                "realms": [
                    {
                        "name": "functest_realm1",
                        "roles": [
                            {
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "websocket",
                        "id": "ws_test_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 6565,
                        },
                        "url": u"ws://localhost:6565/ws",
                    },
                    {
                        "type": "rawsocket",
                        "id": "ws_test_1",
                        "endpoint": {
                            "type": "tcp",
                            "port": 6564,
                        },
                    }
                ],
            }
        ]
    }

    class WaitForTransport(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if "started Transport ws_test_0" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    listening = Deferred()
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv,
            session_temp, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(crossbar_startup_timeout)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


@pytest.fixture(scope="session")
def auth_crossbar(reactor, request, virtualenv, session_temp):
    """
    Similar to the global "crossbar" fixture, but provides more
    configuration so we can do authentication as well.

    XXX reduce dupes between auth_crossbar + crossbar

    Note that both these fixtures will be active at once, potentially
    (so no crossing the ports etc)
    """

    crossbar_config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee",
                "type": "router",
                "realms": [
                    {
                        "name": "auth_realm",
                        "roles": [
                            {
                                "name": "authenticated",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "subscribe": True,
                                            "call": True,
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "role0",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "role1",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "web",
                        "id": "ws_test_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 7575
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "test_wampcra": {
                                "type": "websocket",
                                "auth": {
                                    "wampcra": {
                                        "type": "static",
                                        "users": {
                                            "username": {
                                                "secret": "p4ssw0rd",
                                                "role": "authenticated"
                                            },
                                            "steve": {
                                                "secret": "p4ssw0rd",
                                                "role": "authenticated"
                                            },
                                            "alice": {
                                                "secret": "p4ssw0rd",
                                                "role": "role0"
                                            },
                                            "bob": {
                                                "secret": "p4ssw0rd",
                                                "role": "role0"
                                            },
                                            "carol": {
                                                "secret": "p4ssw0rd",
                                                "role": "role1"
                                            }
                                        },
                                    },
                                    "anonymous": {
                                        "type": "static",
                                        "role": "anonymous",
                                    },
                                    "cookie": {
                                        "store": {
                                            "type": "file",
                                            "filename": "foo.cookies.dat"
                                        }
                                    },
                                    "ticket": {
                                        "type": "static",
                                        "principals": {
                                            "foo": {
                                                "ticket": "seekr1t!!",
                                                "role": "authenticated"
                                            }
                                        },
                                    }
                                },
                                "cookie": {
                                    "store": {
                                        "type": "file",
                                        "filename": "foo.cookies.dat"
                                    }
                                }
                            }
                        }
                    }
                ],
            }
        ]
    }

    class WaitForTransport(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if "started Transport ws_test_0" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    listening = Deferred()
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv, tempdir, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(crossbar_startup_timeout)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


# XXX I'm porting at least some of the SSL tests -- which formerly
# used the "old" management API -- to use this fixture
# instead. *ideally* I think what we'd do is have just *one* crossbar
# fixture and a custom test management-uplink thing so that we could
# mess with the config that way. But for now, I'm trying to make a
# single "SSL stuff" crossbar instance.

@pytest.fixture(scope='session')
def self_signed_cert(request):
    # creates a fresh self-signed certificate and returns it
    # 1. create private key
    # x. remove passphrase from key
    # 2. create signing request
    # 3. sign the request (with same key that created it)
    tmp = mkdtemp()

    def cleanup():
        try:
            shutil.rmtree(tmp)
        except:
            print('Failed to remove "{}".'.format(tmp))
    request.addfinalizer(cleanup)

    pwfile = path.join(tmp, 'password')
    privkey = path.join(tmp, 'private.key')
    csrfile = path.join(tmp, 'server.csr')
    certfile = path.join(tmp, 'server.crt')

    # attempt number 2, in a single command-line w00t
    check_call(["openssl", "req", "-nodes", "-new", "-x509", "-keyout", privkey,
                "-subj", "/C=CA/ST=Germany/L=Erlangen/O=Tavendo/CN=root_ca/",
                "-out", certfile])
    return (privkey, certfile)




    # XXX might be easier if we just do password-less key?
    with open(pwfile, 'w') as f:
        f.write("p@ssw3rd")

    # 1. create private key
#    check_call(["openssl", "genrsa", "-passout", "file:" + pwfile, "-des3",
#                "-out", privkey, "1024"])
    check_call(["openssl", "genrsa", "-des3", "-out", privkey, "1024"])

    # 2. create signing request
    #check_call(["openssl", "req", "-config", "config.ssl", "-batch", "-passin", "file:" + pwfile,
    #"-new", "-subj", "/C=CA/ST=Germany/L=Erlangen/O=Tavendo/CN=root_ca/DN=root_ca/",
    #"-x509", "-days", "1", "-key", "root-ca.key", "-out", "root-ca.crt"])
    check_call(["openssl", "req", "-batch", "-passin", "file:" + pwfile,
                "-new", "-subj", "/C=CA/ST=Germany/L=Erlangen/O=Tavendo/CN=root_ca/DN=root_ca/",
                "-days", "1", "-key", privkey, "-out", csrfile])

    # 3. sign the request (with our own key)
    check_call(["openssl", "x509", "-req", "-days", "1", "-in", csrfile,
                "-signkey", privkey, "-passin", "file:" + pwfile, "-out",
                certfile])

    # server is going to need the private key + certificate
    return (privkey, certfile)


@pytest.fixture(scope="session")
def crypto_crossbar(reactor, request, virtualenv, session_temp, self_signed_cert):
    """
    Similar to the global "crossbar" fixture, but provides more
    configuration so we can do self-signed SSL certificates as well.

    XXX reduce dupes between auth_crossbar + crossbar

    Note that this means there are *three* crossbar instances active
    at once, so mind those port-numbers ;)
    """

    (privkey, certfile) = self_signed_cert

    crossbar_config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "ssl_testee",
                "type": "router",
                "realms": [
                    {
                        "name": "auth_realm",
                        "roles": [
                            {
                                "name": "authenticated",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "anonymous",
                                "type": "static",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "subscribe": True,
                                            "call": True,
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "web",
                        "id": "test_ssl_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 6464,
                            "tls": {
                                "key": privkey,
                                "certificate": certfile,
                            }
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "tls_ws": {
                                "type": "websocket",
                                "auth": {
                                    "wampcra": {
                                        "type": "static",
                                        "users": {
                                            "username": {
                                                "secret": "p4ssw0rd",
                                                "role": "authenticated"
                                            },
                                        }
                                    },
                                    "anonymous": {
                                        "type": "static",
                                        "role": "anonymous"
                                    }
                                }
                            }
                        }
                    }
                ],
            }
        ]
    }

    class WaitForTransport(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if "started Transport test_ssl_0" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    listening = Deferred()
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv, tempdir, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(crossbar_startup_timeout)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


def _write_coverage_files(venv):
    """
    Write the configuration files we need for coverage support, into
    the virtualenv given by ``envdir``. This writes <envdir>/coveragerc
    and <envdir>/lib/py*/sitecustomize.py

    Returns the coveragerc path (which will be in the root of the
    given envdir as "coveragerc")
    """
    # loop, so we find python dirs below lib/
    # like: /tmp/testing/lib/python2.7/sitecustomize.py
    # ...where python2.7 could be pypy, python3.4 etc
    libdir = path.join(venv, 'lib')
    for pydir in listdir(libdir):
        if path.isdir(path.join(libdir, pydir)) and pydir.startswith('py'):
            sitecustom = path.join(venv, 'lib', pydir, 'sitecustomize.py')
            with open(sitecustom, 'w') as f:
                f.write('import coverage\ncoverage.process_startup()\n')

    coveragerc = path.join(venv, 'coveragerc')
    with open(coveragerc, 'w') as f:
        f.write(
            '[run]\n'
            'parallel = True\n'  # same as -p command-line arg
            'omit = __init__.py,*/test/*\n'
            'branch = True\n'
        )
    return coveragerc


def _create_cfx_node_fixture(personality, node):

    @pytest.fixture(scope='module')
    def _cfx_edge(request, reactor):

        cbdir = os.path.join(os.path.dirname(__file__), '../{}/.crossbar'.format(node))

        class WaitForTransport(object):
            """
            Super hacky, but ... other suggestions? Could busy-wait for ports
            to become connect()-able? Better text to search for?
            """
            def __init__(self, done):
                self.data = ''
                self.done = done

            def write(self, data):
                print(data, end='')
                if self.done.called:
                    return

                # in case it's not line-buffered for some crazy reason
                self.data = self.data + data
                if "Skipping any local node configuration (on_start_apply_config is off)" in self.data or \
                   "MrealmController initialized" in self.data or \
                   "Domain controller ready" in self.data or \
                   "Connected to Crossbar.io Master" in self.data:
                    print("Detected crossbar node is up!")
                    self.done.callback(None)

        listening = Deferred()
        protocol = pytest.blockon(
            start_cfx(reactor, personality, cbdir, config=None,
                stdout=WaitForTransport(listening), stderr=WaitForTransport(listening), log_level='info')
        )
        request.addfinalizer(partial(_cleanup_crossbar, protocol))

        timeout = sleep(crossbar_startup_timeout)
        pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))

        if timeout.called:
            raise RuntimeError("Timeout waiting for crossbar to start")

        return protocol

    return _cfx_edge


cfx_master = _create_cfx_node_fixture('master', 'cfc')
cfx_edge1 = _create_cfx_node_fixture('edge', 'cf1')
cfx_edge2 = _create_cfx_node_fixture('edge', 'cf2')
cfx_edge3 = _create_cfx_node_fixture('edge', 'cf3')
