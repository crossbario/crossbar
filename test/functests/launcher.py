###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function

import sys
import os
import binascii
import tempfile
import traceback
from os import environ
from os import path, mkdir
from socket import gethostname
from tempfile import mkdtemp
from functools import partial
import json
from subprocess import check_call
from six import StringIO

import shutil

import click

#import tap.parser

from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import returnValue
from twisted.internet.defer import Deferred
from twisted.internet.defer import DeferredList
from twisted.internet.defer import maybeDeferred
from twisted.internet.defer import CancelledError
from twisted.internet import threads
from twisted.internet.error import ProcessTerminated, ProcessExitedAlready, ProcessDone
from twisted.internet.utils import getProcessOutput
from twisted.internet.utils import getProcessOutputAndValue
from twisted.internet.endpoints import ProcessEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.interfaces import IReactorProcess, IProcessProtocol

from zope.interface import Interface, implementer

from autobahn.util import newid
from autobahn.twisted.util import sleep
from autobahn.twisted.component import Component, run
from autobahn.wamp.exception import TransportLost
from autobahn.wamp import auth
from autobahn.wamp.types import PublishOptions, RegisterOptions, CallOptions
from autobahn.websocket.protocol import parse_url
from autobahn.wamp.cryptosign import SigningKey

from .util import CtsSubprocessProtocol


class IClientState(Interface):
    def get_state():
        """
        Returns a data structure representing the state of this client,
        and any children it deems interesting (that also implment
        IClientState). This will be suitable for sending to a client.
        """


@implementer(IClientState)
class PythonExecutable(object):
    """
    Holds information about configured Python executables.
    """

    def __init__(self, id, executable, version, env_dir):
        """

        :param id: The ID of the Python executable.
        :type id: str
        :param executable: Full path to Python executable.
        :type executable: str
        :param env_dir: Base directory where virtualenvs will be created.
        :type env_dir: str
        """
        self.id = id
        self.executable = executable
        self.version = version
        self.env_dir = env_dir
        self.envs = {}

    def get_state(self):
        return dict(
            id=self.id,
            executable=self.executable,
            version=self.version,
            env_dir=self.env_dir,
            envs=[IClientState(x).get_state() for x in self.envs.values()],
        )

# XXX these classes are nice, but kinda boilerplate-ish can
# "characteristic" save some typing?
@implementer(IClientState)
class PythonEnvironment(object):
    """
    Holds information about created Python virtualenvs.
    """

    def __init__(self, id, python_id, env_dir, testees_dir, requirements, installed):
        """

        :param id: The ID of the Python virtualenv.
        :type id: str
        :param python_id: The ID of the Python exeutable this virtualenv was created from.
        :type python_id: str
        :param env_dir: The directory the virtualenv was created in.
        :type env_dir: str
        :param testees_dir: The directory wherin Crossbar.io node directories will be created.
        :type testees_dir: str
        :param requirements: A list of requirements (e.g. lines like in a pip requirements.txt file).
        :type list
        """
        self.id = id
        self.python_id = python_id
        self.env_dir = env_dir
        self.testees_dir = testees_dir
        self.requirements = requirements
        self.installed = installed
        self.testees = {}

    def get_state(self):
        return dict(
            id=self.id,
            python=self.python_id,
            env_dir=self.env_dir,
            testees_dir=self.testees_dir,
            requirements=self.requirements,
            installed=self.installed,
            testees=[],  # FIXME
        )

@implementer(IClientState)
class TesteeProcess(object):
    """
    Holds information about a running testee process.
    """

    def __init__(self, id, env_id, config={}):
        """

        :param id: The ID of the testee process.
        :type id: str
        :param env_id: The ID of the Python virtualenv this testee is running from.
        :type env_id: str
        """
        self.id = id
        self.env_id = env_id
        self.running = False
        self.config = config

    def get_state(self):
        return dict(
            id=self.id,
            env=self.env_id,
            running=self.running,
            config=self.config,  # or could send prettyprinted JSON?
        )


@implementer(IClientState)
class ProbeProcess(object):
    """
    Holds information about a running probe process.
    """

    def __init__(self, _id):
        """

        :param id: The ID of the probe process.
        :type id: str
        """
        self.id = _id

    def get_state(self):
        return dict(
            id=self.id,
        )


def _run_crossbar(process_launcher, tmpdir, config):
    """
    Run a crossbar node from the specified tmpdir (which should be a
    virtualenv) and the specified args (which should NOT include
    'crossbar' itself).

    :returns: a Deferred that fires the (protocol, transport) of the
        launched crossbar.
    """

    # make our crossbar node configuration
    cbdir = path.join(tmpdir, 'crossbar_node')
    try:
        mkdir(cbdir)  # we keep a venv around if we're debugging so this fails
    except OSError:
        pass

    # write configuration for this crossbar instance
    with open(path.join(cbdir, 'config.json'), 'w') as cfgfile:
        cfgfile.write(json.dumps(config, sort_keys=True, indent=4))

    # launch the crossbar node
    # yields/returns (protocol, transport) if we need...
    # (process_launcher actually returns a Deferred of course)
    cb_cmd = path.join(tmpdir, 'bin', 'crossbar')
    return process_launcher([cb_cmd, 'start', '--cbdir', cbdir], environ)


def sequential_ids(prefix):
    counter = 1
    while True:
        yield '{}_{}'.format(prefix, counter)
        counter += 1


def _create_signing_key():
    """
    :returns: a new SigningKey instance and a hex encoding of the
        private key data.
    """
    keydata = os.urandom(32)
    sk = SigningKey.from_key_bytes(keydata)
    privkey_hex = sk._key.encode(encoder=encoding.HexEncoder).decode('ascii')

    return sk, privkey_hex


class LauncherProcessController(object):

    """
    Instances of this are owned by the LauncherSession and used to do
    process control: launch testees and probes and terminate them.
    """

    def __init__(self, reactor, session, id_, router_uri, privkey_fname, workdir, debug=True):
        """
        :param session: a WAMP ApplicationSession we may use. This will be
        a LauncherSession; see
        :meth:`.LauncherSession._create_process_controller` below.

        XXX maybe just roll all this into LauncherSession? I'm just
        trying to avoid that class being huge and have many concerns...
        """
        self._spawn = IReactorProcess(reactor).spawnProcess
        self._session = session
        self._processes = dict()
        self._prefix = 'io.crossbar.cts.launcher.{}'.format(id_)
        self._id = id_
        self._debug = debug
        self._router_uri = router_uri
        self._privkey_fname = privkey_fname
        self._workdir = workdir

    async def spawn_testee(self, testee_id, pyenv, cbdir):
        """
        testee_id: unicode, ID
        pyenv: PythonEnvironment instance
        cbdir: path
        """
        launched = Deferred()
        all_done = Deferred()
        transport_listening = Deferred()
        # XXX FIXME replace with "broadcast testee logs to topic",
        # like the wamp on_log things.
        logs = StringIO()

        class FindTransport(object):
            def write(self, data):
                logs.write(data.decode('utf8'))  # wha?? an we just open StringIO as binary?
                # XXX horrific hack; are there some wamp metaevents we
                # can listen for "or something"?
                if b"started Transport ws_test_0" in data:
                    # print("Detected transport starting up")
                    transport_listening.callback(None)

        # create our subprocess protocol, hooking in the stderr-scanner
        proto = CtsSubprocessProtocol(
            all_done, launched,
            stdout=FindTransport(),
            stderr=FindTransport(),
        )
        exe = path.join(pyenv.env_dir, 'bin', 'crossbar')
        args = (exe, 'start', '--cbdir', cbdir)
        print("running: {}".format(' '.join(args)))
        transport = self._spawn(
            proto, args[0],
            args=args,
            env={
                "HOME": cbdir,
                "PYTHONUNBUFFERED": "1",
                "LANG": environ['LANG'],
            },
            path=cbdir,
        )
        # XXX FIXME use a class to hold these things, not 4-tuple!
        self._processes[testee_id] = (proto, transport, all_done, launched)

        def get_errors():
#            all_logs = logs.getvalue()
#            if len(all_logs) > 400:
#                return '...' + logs.getvalue()[-400:]
            return logs.getvalue()

        def spawn_failed(fail):
            print("Testee spawn failed:", fail)
            if self._debug:
                fail.printTraceback()
                # print(logs.getvalue())

            cmdline = ' '.join(args)
            msg = "Failed to spawn process:\n{}\n\ntail of log:\n{}".format(
                cmdline, get_errors())
            err = RuntimeError(msg)
            if not launched.called:
                launched.errback(err)
            elif not transport_listening.called:
                transport_listening.errback(err)
            else:
                # we haven't yet dealt with the error
                return err
            # we have passed on the error, cancel this errback chain
            return None

        def already_done(_):
            if not transport_listening.called:
                # the process exited (without error) but before we
                # noticed our transport starting up.
                err = RuntimeError("Exited cleanly before we saw a transport:\n" + get_errors())
                transport_listening.errback(err)
        all_done.addCallbacks(already_done, spawn_failed)

        await launched
        print("crossbar started, waiting for transports")

        await transport_listening
        print("transports listening")

    async def spawn_probe(self, probe_id):
        launched = Deferred()
        all_done = Deferred()
        class LogPrinter(object):
            def write(self, data):
                print(data.decode('utf8'), end='')

        proto = CtsSubprocessProtocol(
            all_done, launched,
            stdout=LogPrinter(), stderr=LogPrinter(),
        )
        keydata = os.urandom(32)
        signing_key = SigningKey.from_key_bytes(keydata)
        probe_privkey_fname = path.join(self._workdir, "{}.privkey".format(probe_id))
        with open(probe_privkey_fname, 'wb') as f:
            f.write(keydata)

        # enroll this pubkey with the master
        await self._session.call(
            u"io.crossbar.cts.enroll_probe", signing_key.public_key(),
        )

        args = (
            sys.executable,  # cts.probe from "our" venv, not testee's
            u"-m", "cts.probe",
            u"--id", str(probe_id),
            u"--realm", "io.crossbar.test", # str(self._session.config.realm),
            u"--router", self._router_uri,
            u"--privkey-file", probe_privkey_fname,
            u"--launcher", self._id,
            # "--afinity", 1,
        )
        print("probe: {}".format(" ".join(args)))
        transport = self._spawn(
            proto, args[0],
            args=args,
            env={
                "PYTHONUNBUFFERED": "1",
                "LANG": environ["LANG"],
            }
        )
        self._processes[probe_id] = (proto, transport, all_done, launched)

        # XXX super-similar to spawn_testee...
        def spawn_failed(fail):
            print("Probe spawn failed:", fail)
            if True:#self._debug:
                fail.printTraceback()

            err = RuntimeError("Failed to spawn probe.")
            if not launched.called:
                launched.errback(err)
                return None
            else:
                # we haven't yet dealt with the error
                return err

        all_done.addErrback(spawn_failed)

        x = await launched
        # print("launched", x, probe_id)
        # XXX should wait for probe_ready or something

        return probe_id

    async def terminate_process(self, process_id):
        """
        Kills off an already-running probe.
        """
        print("terminate_process():", process_id)
        try:
            (proto, transport, all_done, launched) = self._processes[process_id]
        except KeyError:
            raise RuntimeError('No process "{}" found'.format(process_id))

        # ask somewhat nicely for it to die; Twisted will call processEnded
        transport.signalProcess('TERM')

        # DeferredList around [all_done, sleep(1)] then do a KILL if
        # all_done still isn't callback()'d
        x = await all_done
        return x

    def list_processes(self):
        """
        List running processes that we've launched.
        """
        return self._processes.keys()

    def _cleanup_process(self, procid):
        """
        ProbeProcessProtocol calls me when it dies
        """
        del self._processes[procid]

        print('Process "{}" exited'.format(procid))
        try:
            # XXX what about some interesting args, like:
            # 'probe', proto.id, statusmsg,
            self._session._launcher_publish('on_process_exit', procid)
        except TransportLost as e:
            pass  # we might be shutting down, and have no WAMP connection
            # XXX maybe just any ApplicationError??


def check_executable(fpath):
    """
    :returns: true if `fpath` is a file and executable
    """
    return os.path.exists(fpath) and os.access(fpath, os.F_OK | os.X_OK) and not os.path.isdir(fpath)


async def create_launcher(reactor, session, id_, address, workdir, router_uri, privkey_fname, pythons=None):
    """
    :returns: a new Launcher instance, prepared to answer RPC calls.
    """
    process_controller = await create_process_controller(reactor, session, id_, router_uri, privkey_fname, workdir)
    launcher = Launcher(session, id_, address, workdir, process_controller)
    if pythons:
        await launcher.setup_pythons(pythons)
    await launcher.register_procedures()
    return launcher


# XXX see scenariotests/utility.py for an idea to have e.g. ILauncher
# or RLauncher or something that represents "a remote API" ... to save
# typing out the interesting methods twice.
@implementer(IClientState)
class Launcher(object):
    """
    The actual launcher application (see controller/cli.py where it is
    started)

    A launcher needs to manage:

    - pythons executable paths
    - virtual environment dirs
    - testee node dirs
    - probe work dirs


    A Crossbar.io testee will be launched from a directory like

    /tmp/.cts/envs/pypy240/_E0KVqZzRXYlcNJm/testees/M89hhaR68/.crossbar

    XXX this would never let two launchers run on the same machine --
    which shouldn't be the "usual" case, but might hinter testing
    ... also why the dot-file? /tmp/cts/... ? /tmp/cts-%(id)s/ ?
    """

    def __init__(self, session, id_, address, workdir, process_controller):
        # options from the command lines
        self._id = id_
        self._workdir = workdir
        self._session = session
        self._process_controller = process_controller
        self._address = address

        # map: Python ID -> PythonExecutable
        self._pythons = {}

        # map: Environment ID -> PythonEnvironment
        self._envs = {}

        # map: Testee Process ID -> TesteeProcess
        self._testees = {}

        # map: Probe Process ID -> ProbeProcess
        self._probes = {}

        self._testee_id_generator = sequential_ids("testee")
        self._probe_id_generator = sequential_ids("probe")
        self._env_id_generator = sequential_ids("env_")

        # shared options for our publishes
        self._publish_options = PublishOptions(
            acknowledge=True,
        )

        # check for the virtualenv executable we will use
        #
        self._cmd_virtualenv = shutil.which("virtualenv")
        if not self._cmd_virtualenv or not check_executable(self._cmd_virtualenv):
            raise ValueError("virtualenv not found!")

        # register hooks in WAMP Session
        session.on('leave', self.end_session)

    def get_state(self):
        """IClientState API"""
        # XXX grab all the active-probe information from probes via RPC?
        return dict(
            id=self._id,
            pythons=[IClientState(x).get_state() for x in self._pythons.values()],
            envs=[IClientState(x).get_state() for x in self._envs.values()],
            testees=[IClientState(x).get_state() for x in self._testees.values()],
            probes=[IClientState(x).get_state() for x in self._probes.values()],
            address=self._address,
            python=sys.executable,
            workdir=self._workdir,
        )

    async def setup_pythons(self, pythons):
        """
        setup Python executables and environments

        :param pythons: a list of 2-tuples of ("name", "python binary")
        """

        for name, path in pythons:
            if check_executable(path):
                exe = path
            else:
                exe = shutil.which(path)
                if exe is None or not check_executable(exe):
                    print("Failed to find Python for '{}'".format(path))
                    raise Exception("Fatal: no executable '{}' found for Python '{}'".format(path, name))

            version = await getProcessOutput(exe, ["-V"], errortoo=True)
            version = version.replace(b'\n', b' ').strip().decode('ascii')

            env_dir = os.path.join(self._workdir, "envs", name)
            os.makedirs(env_dir)

            self._pythons[name] = PythonExecutable(name, exe, version, env_dir)

    async def register_procedures(self):
        # register procedures
        #
        procs = [
            # Echo test/debug procedure
            ("echo", self.echo),

            # get_state + corresponding topic "io.crossbar.cts.launcher.<id>.state"
            # returns simple struct of entire state of this launcher
            ("get_state", self.get_state),

            # Python executables
            ("get_pythons", self.get_pythons),

            # Python virtualenvs
            ("get_envs", self.get_envs),
            ("create_env", self.create_env, RegisterOptions(details_arg="details")),
            ("update_env", self.update_env),
            ("destroy_env", self.destroy_env),

            # running the pytest-based 'functests'
            ("run_functests", self.run_functests, RegisterOptions(details_arg="details")),

            # Testees
            ("get_testees", self.get_testees),
            ("create_testee", self.create_testee),
            ("start_testee", self.start_testee),
            ("stop_testee", self.stop_testee),
            ("destroy_testee", self.destroy_testee),

            # Probes
            ("get_probes", self.get_probes),
            ("start_probe", self.start_probe),
            ("stop_probe", self.stop_probe),
        ]
        for proc in procs:
            uri = "io.crossbar.cts.launcher.{}.{}".format(self._id, proc[0])
            func = proc[1]
            options = None if len(proc) < 3 else proc[2]
            await self._session.register(func, uri, options=options)
            print("  {}".format(uri))

        # let CTS know we're prepared for action
        #
        await self._session.publish(
            u'io.crossbar.cts.on_launcher_ready',
            self._id,
            options=self._publish_options,
        )
        await self._publish_changed()

    def _publish_changed(self):
        topic = 'io.crossbar.cts.launcher.{}.state'.format(self._id)
        print("publish: {}".format(topic))
        return self._session.publish(
            topic, self.get_state(),
            options=self._publish_options,
        )

    async def end_session(self, session, details):
        print("Launcher session ended with reason '{}': {}".format(details.reason, details.message))

        shutil.rmtree(self._workdir)

        if self._process_controller:
            for procid in self._process_controller.list_processes():
                # print("Killing subprocess '{}' ...".format(procid))
                d = self._process_controller.terminate_process(procid)
                try:
                    await d  # XXX FIXME use DeferredList
                except Exception as e:
                    # we'll probably always (?) get an exception as we
                    # just nuked the process
                    print("Ignoring (we're shutting down):", e)
        else:
            print("No subprocesses running.")

        session.disconnect()

    def echo(self, msg):
        """
        Echo back message (for testing purposes).
        """
        return msg

    def get_pythons(self):
        """
        Returned configured Python executables.
        """
        res = {}
        for p in self._pythons.values():
            res[p.id] = IClientState(p).get_state()
        return res

    def get_envs(self):
        """
        Return currently existing Python environments.
        """
        res = {}
        for e in self._envs.values():
            res[e.id] = IClientState(e).get_state()
        return res

    async def create_env(self, python_id, requirements=None, details=None):
        """
        Create a new Python virtualenv from a given Python executable.

        :param python_id: The ID of a configured Python executable.
        :type python_id: str
        :param requirements: A list of requirements (e.g. lines from a pip requirements.txt file).
        :type requirements: list of str

        :returns: environment id
        """
        print("create_env: {}".format(details))
        print("create_env: {}".format(details.progress))
        if python_id not in self._pythons:
            raise Exception("no Python with ID '{}'".format(python_id))

        python = self._pythons[python_id]
        env = environ.copy()
        envid = next(self._env_id_generator)
        env_dir = os.path.join(python.env_dir, envid)

        if requirements is not None:
            requirements = [r.strip() for r in requirements]

        print("Creating new Python virtualenv '{}' for Python '{}' ...".format(envid, python_id))
        installed = await create_virtualenv(python.executable, env_dir, env, requirements, progress=details.progress)

        testees_dir = os.path.join(env_dir, "testees")
        os.mkdir(testees_dir)

        python_env = PythonEnvironment(envid, python_id, env_dir, testees_dir, requirements, installed)
        python.envs[envid] = python_env
        self._envs[envid] = python_env
        info = python_env.get_state()

        await self._publish_changed()
        await self._launcher_publish(
            'on_env_updated', info,
            options=self._publish_options,
        )
        return envid

    async def update_env(self, env_id, requirements=None):
        """
        Update dependencies in an existing environment

        :param python_id: The ID of an existing environment
        :type python_id: str
        :param requirements: A list of requirements (e.g. lines from a pip requirements.txt file).
        :type requirements: list of str

        :returns: environment id
        """
        if env_id not in self._envs:
            raise Exception("no Python environment '{}'".format(env_id))
        env = self._envs[env_id]
        python = self._pythons[env.python_id]

        if requirements is not None:
            requirements = [r.strip() for r in requirements]

        print("Updating requirements in '{}'".format(env_id))
        installed = await create_virtualenv(python.executable, env.env_dir, environ.copy(), requirements, just_update=True)

        python.requirements = requirements
        python.installed = installed
        info = python.get_state()

        await self._publish_changed()
        await self._launcher_publish(
            'on_env_updated', info,
            options=self._publish_options,
        )

    async def _launcher_publish(self, topic, *args, **kw):
        top = 'io.crossbar.cts.launcher.{}.{}'.format(self._id, topic)
        print("publish to: {}".format(top))
        await self._session.publish(top, *args, **kw)

    async def destroy_env(self, env_id):
        """
        Destroys a previously created Python virtualenv. Note that a
        Pyhton virtualenv can only be destroyed if it not in use by
        a testee currently.

        :param env_id: The ID of the Python virtualenv to destroy.
        :type env_id: str
        """
        ## XXX do I do destroyed events too? kind needed for UI updates...
        del self._envs[env_id]
        await self._launcher_publish(
            'on_env_destroyed',
            env_id,
            options=self._publish_options
        )
        await self._publish_changed()
        return None

    async def run_functests(self, env_id, details=None):
        """
        Can accept progressive results, which callback with 4 kwargs:
           completed= (an int, tests run)
           total= (an int, total tests to run)
           failed= (an int, how many tests have failed so far
           ok= (a bool, whether this test failed or not)
           description= (a string, which test this is)
        """
        env_id = str(env_id).strip()
        if env_id not in self._envs:
            raise Exception("no Python environment with ID '{}'".format(env_id))
        pyenv = self._envs[env_id]

        from distutils.version import LooseVersion
        have_cts = False
        for req in pyenv.installed:
            v = LooseVersion(req)
            print(v, v.version[0])
            if v.version[0] == 'cts':
                have_cts = True

        if not have_cts:
            raise RuntimeError(
                "Requirements in env {} do not include CTS iteself".format(
                    env_id,
                )
            )

        launched = Deferred()
        all_done = Deferred()
        logs = StringIO()

        # find all the functional tests
        import cts
        functest_dir = path.join(cts.__path__[0], "functional_tests")
        # functest_dir = path.join(os.getcwd(), "functests_simple")
        functests = [
            #path.join("functests", p)  # this is relative; can py.test take absolute paths?
            path.join(functest_dir, p)
            for p in os.listdir(functest_dir)
            if p.startswith("test_") and p.endswith(".py")
        ]
        if not functests:
            raise RuntimeError(
                "No functests found in '{}'".format(functest_dir)
            )


        class ParseTap(object):
            """
            Parsing incoming TAP (test anything protocol) lines.
            """
            def __init__(self, on_progress):
                self.goal = 0
                self.completed = 0
                self.failed = 0
                self.parser = tap.parser.Parser()
                self._progress = on_progress
                self._last_diag = []

            def write(self, data):
                """
                Receives incoming data from stdout + stderr of the underlying
                py.test process.
                """
                for line in data.decode('utf8').strip().split('\n'):
                    t = self.parser.parse_line(line)
                    if isinstance(t, tap.parser.Plan):
                        self.goal = t.expected_tests
                        self.completed = 0
                        self.failed = 0
                    elif isinstance(t, tap.parser.Result):
                        self.completed = t.number
                        if not t.ok:
                            self.failed += 1
                        if self.goal is not None:
                            self._progress(
                                completed=self.completed,
                                total=self.goal,
                                failed=self.failed,
                                ok=t.ok,
                                description=t.description,
                                diagnostic=self._last_diag,
                            )
                            self._last_diag = []
                    elif isinstance(t, tap.parser.Diagnostic):
                        self._last_diag.append(t.text)
                if self.completed == self.goal and self.completed > 0:
                    # wait, so this actually happens .. but why/when?
                    if not all_done.called:
                        all_done.callback(None)

        # create our subprocess protocol, hooking in a TAP ("test
        # anything protocol") parser as well

        tap_parser = ParseTap(details.progress) if details.progress else None
        proto = CtsSubprocessProtocol(all_done, launched, stdout=tap_parser, stderr=tap_parser)
        exe = path.join(pyenv.env_dir, 'bin', 'py.test')
        # args = (exe, '--tap-stream', '--verbose', '--coverage', '--slow') + tuple(functests)
        args = (exe, '-s', '--tap-stream', '--verbose', '--coverage') + tuple(functests)

        # w/o PYTHONUNBUFFERED we don't get updates about each test in
        # a timely fashion
        env = environ.copy()
        env['PYTHONUNBUFFERED'] = "1"

        from twisted.internet import reactor
        print("Spawning py.test subprocess")
        print(" ".join([str(x) for x in args]))
        transport = reactor.spawnProcess(
            proto, args[0],
            args=args,
            path=os.getcwd(),
            env=env,
        )

        def get_errors():
            all_logs = logs.getvalue()
            if len(all_logs) > 400:
                return '...' + logs.getvalue()[-400:]
            return logs.getvalue()

        def spawn_failed(fail):
            if True:#self._debug:
                fail.printTraceback()
                print(logs.getvalue())

            cmdline = ' '.join(args)
            msg = "py.test failed: :\n{}\n\ntail of log:\n{}".format(
                cmdline, get_errors())
            err = RuntimeError(msg)
            if not launched.called:
                launched.errback(err)
            else:
                # we haven't yet dealt with the error
                raise err
                #return err
            # we have passed on the error, cancel this errback chain
            return None

        all_done.addErrback(spawn_failed)

        try:
            await launched
        except Exception as e:
            print("BAD: {}".format(e))
            print(proto._stderr.getvalue())
        await all_done
        return {
            "total": tap_parser.goal,
            "success": tap_parser.completed - tap_parser.failed,
            "failure": tap_parser.failed,
        }


    def get_testees(self):
        """
        Return currently running testee processes.
        """
        res = {}
        for t in self._testees.values():
            res[t.id] = IClientState(t).get_state()
        return res

    def create_testee(self, env_id, config):
        """
        Initializes a Crossbar.io testee node directory.

        :param env_id: The ID of the Python virtualenv to use for the testee.
        :type env_id: str

        :param config: Configuration to use for the Crossbar instance
        :type config: dict

        :returns: The ID of the testee created.
        """

        env_id = str(env_id).strip()
        if env_id not in self._envs:
            raise Exception("no Python environment with ID '{}'".format(env_id))
        env = self._envs[env_id]
        testee_id = next(self._testee_id_generator)
        testee_dir = path.join(env.testees_dir, testee_id)

        names, ports = self._validate_testee_config(config)  # raises if there's an error
        portlist = ', '.join(map(str, zip(names, ports)))
        print("Starting testee with transports on: {}.".format(portlist))
        os.mkdir(testee_dir)
        with open(path.join(testee_dir, 'config.json'), 'w') as cfgfile:
            cfgfile.write(json.dumps(config, sort_keys=True, indent=4))

        testee = TesteeProcess(testee_id, env_id, config)
        self._testees[testee_id] = testee
        env.testees[testee_id] = testee
        self._publish_changed()
        return testee_id

    def _validate_testee_config(self, config):
        """
        Checks that we have a transport named "test_ws_0" or else our
        startup-detection won't work.

        Could also detect if we conflict with other ports (or just
        wait for the process to die).
        """
        # XXX I guess I could call crossbar.common.checkconfig things
        # but I'd rather just let the underlying crossbar error-out if
        # it's unhappy -- this is just presuming we have the right
        # data-structure.
        ports = []
        names = []
        for worker in config.get('workers', []):
            for transport in worker.get('transports', []):
                if 'url' in transport:
                    (isSecure, host, port, resource, path, params) = parse_url(transport['url'])
                    ports.append(port)
                else:
                    ports.append(transport['endpoint']['port'])
                names.append(transport['id'])

        if 'ws_test_0' not in names:
            raise RuntimeError('Config needs a transport named "ws_test_0".')
        return names, ports

    async def start_testee(self, testee_id):
        """
        """
        if testee_id not in self._testees:
            raise Exception("no Testee with ID '{}'".format(testee_id))
        testee = self._testees[testee_id]
        env = self._envs[testee.env_id]
        pwd = path.join(env.testees_dir, testee_id)
        failed = None

        try:
            await self._process_controller.spawn_testee(testee_id, env, pwd)
            self._session.publish(
                'io.crossbar.cts.launcher.{}.on_process_start'.format(self._id),
                testee.get_state(),  # XXX or just testee_id?
            )
        except Exception as e:
            testee.running = False
            failed = e
        else:
            testee.running = True
        await self._publish_changed()
        if not testee.running and failed:
            raise failed

    async def stop_testee(self, testee_id):
        """
        """
        if testee_id not in self._testees:
            raise Exception("no Testee with ID '{}'".format(testee_id))

        testee = self._testees[testee_id]
        try:
            await self._process_controller.terminate_process(testee_id)
        except ProcessExitedAlready:
            pass
        testee.running = False
        await self._publish_changed()

    async def destroy_testee(self, testee_id):
        """
        """
        if testee_id not in self._testees:
            raise Exception("no Testee with ID '{}'".format(testee_id))

        testee = self._testees[testee_id]
        if testee.running:
            await self._process_controller.terminate_process(testee_id)
        env = self._envs[testee.env_id]
        del env.testees[testee_id]
        testee_dir = path.join(env.testees_dir, testee_id)
        # defer to thread?
        shutil.rmtree(testee_dir)
        del self._testees[testee_id]
        await self._publish_changed()

    def get_probes(self):
        """
        Return currently running probe processes.
        """
        res = {}
        for p in self._probes.values():
            res[p.id] = IClientState(p).get_state()
        return res

    async def start_probe(self):
        """
        Initializes a probe working directory and starts a new probe
        from there.

        :returns: The ID of the launched probe.
        """

        probe_id = next(self._probe_id_generator)## + '-' + str(self._id)
        await self._process_controller.spawn_probe(probe_id)
        print("Spawned", probe_id)
        probe = ProbeProcess(probe_id)
        self._probes[probe_id] = probe
        self._session.publish(
            'io.crossbar.cts.launcher.{}.on_process_start'.format(self._id),
            probe.get_state(),
        )
        await self._publish_changed()
        return probe_id

    async def stop_probe(self, probe_id):
        if probe_id not in self._probes:
            raise RuntimeError("no Probe with ID '{}'".format(probe_id))
        proc = self._probes[probe_id]
        await self._process_controller.terminate_process(proc.id)
        del self._probes[proc.id]
        await self._publish_changed()

async def create_process_controller(reactor, session, myid, router_uri, privkey_fname, workdir):
    """
    Create our LauncherProcessController instance and register some of
    its methods as part of our exported WAMP API
    """
    return LauncherProcessController(
        reactor, session, myid, router_uri, privkey_fname, workdir,
    )

    api = [
# XXX now i guess registered as "create_testee" instead?
#            controller.launch_testee,
# XXX now as start_probe
#            controller.launch_probe,
        controller.terminate_process,
        controller.list_processes,
    ]
    registers = []
    for method in api:
        name = method.__name__
        api = "io.crossbar.cts.launcher.{}.{}".format(myid, name)
        registers.append(self._session.register(method, api))
        print('Registering "{}".'.format(name))

    results = await DeferredList(registers)
    for (ok, result) in results:
        if not ok:
            raise RuntimeError(
                'Failed to register method ("{}").'.format(result))


@implementer(IProcessProtocol)
class LoggingProcessProtocol(ProcessProtocol):
    def __init__(self, topic_publisher, stdout_topic, stderr_topic, done=None):
        """
        topic_publisher is usually your ApplicationSession.publish
        method. Can be ``None`` for no logging.

        done, if passed, should be a Deferred which will callback()
        when this process exits.
        """
        self._stdout_topic = stdout_topic
        self._stderr_topic = stderr_topic
        self._publish = topic_publisher
        self._all_done = done
        # XXX should probably line-buffer too?

        #: None, or an integer if the process has exited
        self.exit_status = None

    def outReceived(self, data):
        if self._publish:
            self._publish(self._stdout_topic, data)
        print(data.decode('utf8'))

    def errReceived(self, data):
        if self._publish:
            self._publish(self._stderr_topic, data)
        print(data.decode('utf8'))

    def processEnded(self, reason):
        if isinstance(reason.value, ProcessTerminated):
            self.exit_status = reason.value.exitCode
        elif isinstance(reason.value, ProcessDone):
            self.exit_status = 0
        else:
            raise RuntimeError("Unexpected exit reason")
        if self._all_done:
            self._all_done.callback(None)


def stdout_publisher(_, data):
    """
    Can be used as the "topic_publisher" to a LoggingProcessProtocol
    instantiation to get logs of the subprocess to stdout.
    """
    sys.stdout.write(data.decode('utf8'))
    sys.stdout.flush()


async def run_process(exe, args, env, publisher=stdout_publisher):
    """
    Similar to
    https://twistedmatrix.com/documents/current/api/twisted.internet.utils.getProcessOutput.html
    except gives us a way to log the output of the
    subprocess. Callback with the exit_status when the process
    completes.
    """
    done = Deferred()
    print("Running: {} {}".format(exe, ' '.join(args)))
    if False:
        print("Env:")
        for (k, v) in env.iteritems():
            print("  {}: {}".format(k, v))
    # XXX FIXME why isn't this getting propagated from the env?
    # hmm, seems like we don't need this anymore?
#    env['C_INCLUDE_PATH'] = '/usr/local/include/'
    proto = LoggingProcessProtocol(publisher, None, None, done)
    from twisted.internet import reactor
    proc = reactor.spawnProcess(proto, exe, [exe] + args, env=env)
    try:
        await done
    except CancelledError:
        print("cancelled!")
        proto.transport.loseConnection()
        return 1
    return proto.exit_status


async def create_virtualenv(python, env_dir, env, requirements, logging=True, just_update=False, progress=None):
    """
    Create a new Python virtualenv at ``env_dir`` with the Python
    executable ``python``. Returns a Deferred, which callbacks with
    nothing (when "virtualenv" exits).
    """

    def progress_publisher(_, data):
        progress_publisher.logs += data.decode('utf8')
        lines = progress_publisher.logs.split('\n')
        if lines and lines[-1] and lines[-1][-1] != '\n':  # if last line doesn't end in \n
            progress_publisher.logs = lines[-1]
            lines = lines[:-1]
        for line in lines:
            progress(output=line)
    progress_publisher.logs = ""

    publisher = stdout_publisher if progress is None else progress_publisher
    if not logging:
        publisher = None

    python = shutil.which(python)
    venv_py = os.path.join(env_dir, "bin", "python")
    exe = shutil.which('virtualenv')
    # https://twistedmatrix.com/documents/current/api/twisted.internet.utils.getProcessOutput.html

    if not just_update:
        args = ['--python', python, env_dir]
        ecode = await run_process(exe, args, env, publisher)
        if ecode != 0 and not os.path.exists(os.path.join(env_dir, "bin", "python")):
            raise RuntimeError("Creating virtualenv failed.")
        print("Python virtualenv created in '{}'.".format(env_dir))

    if requirements:
        print("Installing requirements in Python virtualenv '{}' ...".format(env_dir))
        req_fname = os.path.join(env_dir, "requirements-latest.txt")
        with open(req_fname, 'w') as reqfile:
            for line in requirements:
                reqfile.write("{}\n".format(line))

        if not python.startswith('python3'):
            # upgrading pip, "because Debian" :/
            ecode = await run_process(venv_py, ["-m", "pip", "install", "--upgrade", "pip"], env)
            if ecode != 0:
                raise RuntimeError("pip upgrade failed")

        ecode = await run_process(venv_py, ["-m", "pip", "install", "--upgrade", "-r", req_fname], env,
                                  publisher=publisher)
        if ecode != 0:
            raise RuntimeError("pip install failed (req_fname={}): ecode={}".format(req_fname, ecode))
        print("Requirements for Python virtualenv installed.")
    else:
        log_pip = None
        print("No requirements to install.")

    installed_data = []
    def collect_lines(x, data):
        installed_data.append(data)
    ecode = await run_process(venv_py, ["-m", "pip", "freeze"], env, collect_lines)
    if ecode != 0:
        raise RuntimeError("pip freeze failed")

    freeze_lines = [
        line.strip()
        for line in b''.join(installed_data).decode('utf8').split('\n')
        if len(line.strip())
    ]
    return freeze_lines


def make_launcher_command(cts):
    @cts.command()
    @click.option(
        '--id', type=str,
        default=gethostname(),
        help='ID used in WAMP-CRA authentication and as part of WAMP URIs.',
    )
    @click.option(
        '--privkey-file', type=click.Path(exists=True),
        required=True,
        help='The authentication secret used for cryptosign.',
        metavar='FNAME',
    )
    @click.option(
        '--python', type=str, multiple=True, nargs=2,
        help='A Python to be used from this launcher: (name binary).',
    )
    @click.option(
        '--workdir', type=str, default=os.path.join(tempfile.gettempdir(), ".cts"),
        help='Working directory where Python virtualenvs are created.'
    )
    @click.pass_obj
    def launcher(config, privkey_file, id, python, workdir):
        """
        Runs the CTS 'Launcher' process.

        The launcher is a CTS process started on a host taking part in a
        CTS test setup and is responsible for starting processes like
        probes and testees. It exposes an API via WAMP.

        This function is also specified as an entry point in setup.py
        for the `ctslauncher` script.
        """
        # create clean working directory for Python virtualenvs
        #
        if not os.path.exists(workdir):
            print("Working directory {} does not exist. Creating ...".format(workdir))
            os.makedirs(workdir)
        else:
            if not os.path.isdir(workdir):
                print("Fatal: path {} for working directory exists, but is not a directory".format(workdir))
                sys.exit(1)
            else:
                print("Working directory {} exists already - cleaning and recreating.".format(workdir))
                try:
                    shutil.rmtree(workdir)
                except Exception as e:
                    print("Fatal: error during cleaning of working directory - {}".format(e))
                os.makedirs(workdir)


        with open(privkey_file, 'rb') as f:
            privkey = f.read()

        comp = Component(
            transports=[
                {
                    u"type": u"websocket",
                    u"url": config.router,
                }
            ],
            realm="io.crossbar.cts",
            authentication={
                "cryptosign": {
                    "authid": id,
                    "privkey": binascii.b2a_hex(privkey),
                }
            },
        )

        from twisted.internet import reactor

        @comp.on_join
        async def setup_launcher(session, details):
            ip = await session.call("io.crossbar.cts.launcher_ip", details.session)
            print("address: {}".format(ip))
            print("Launcher '{}' connected, session_id={}".format(id, details.session))
            try:
                # XXX since we already loaded the key, maybe privkey= instead of privkey_file here?
                launch = await create_launcher(reactor, session, id, ip, workdir, config.router, privkey_file, pythons=python)
            except Exception as e:
                print(str(e))
                raise
                ##await session.leave()
        run([comp], log_level=("debug" if config.debug else "info"))
    return launcher


if __name__ == '__main__':
    make_launcher_command(click)()
