###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function

import json
import sys
import shutil
from os import path, mkdir, environ, listdir
from six import StringIO
from tempfile import mkdtemp

import pytest

from autobahn.wamp import auth
from autobahn.twisted.util import sleep

from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, returnValue
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import ProcessExitedAlready


import os
import binascii

import txaio
txaio.use_twisted()

from autobahn.twisted.wamp import ApplicationRunner, ApplicationSession
from autobahn.wamp import cryptosign

from crossbar._util import hl
from crossbar.shell.command import CmdListManagementRealms


@inlineCallbacks
def wait_for(d, timeout=1, msg="Timed out in wait_for()"):
    '''
    This helper waits up to ``timeout`` seconds for the Deferred ``d``
    to callback; if it doesn't, we errback. Otherwise we callback with
    the results from ``d``.

    Of course, ``d`` can be a DeferredList
    '''
    timeout_d = sleep(timeout)
    # note that we're just letting exceptions out, so if this
    # .errbacks, then we'll correctly errback in the caller as well
    r = yield DeferredList([d, timeout_d], fireOnOneErrback=True, fireOnOneCallback=True)
    if timeout_d.called:
        raise RuntimeError(msg)
    returnValue(r)


class AuthenticatedSession(ApplicationSession):
    """
    This is a WAMP session for the tests to use.
    """

    def onConnect(self):
        authid = self.config.extra.get('authid', u'username')
        self.join(self.config.realm, authmethods=[u'wampcra'], authid=authid)

    def onChallenge(self, challenge):
        password = self.config.extra.get('password', u"p4ssw0rd")
        if challenge.method == u"wampcra":
            signature = auth.compute_wcs(
                password.encode('utf8'),  # XXX FIXME isn't this just using that as the key, directly?!
                # ...i.e. probably docs should use os.urandom(32) in the examples...?
                challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        raise RuntimeError("unknown authmethod {}".format(challenge.method))

    def onJoin(self, details):
        self.config.extra['running'].callback(self)

    def onLeave(self, details):
        # print("onLeave", details)
        d = self.config.extra['running']
        if not d.called:
            d.errback(RuntimeError("onLeave: {}".format(details.message)))
        all_done = self.config.extra.get('all_done', None)
        if all_done:
            all_done.callback(self)
        ApplicationSession.onLeave(self, details)

    @inlineCallbacks
    def quit(self):
        all_done = self.config.extra.get('all_done', Deferred())
        self.config.extra['all_done'] = all_done
        self.leave(u"quitting")
        yield all_done


# XXX FIXME use endpoint, plus stuff from Crossbar instead
class CrossbarProcessProtocol(ProcessProtocol):
    """
    A helper to talk to a crossbar instance we've launched.
    """

    def __init__(self, reactor, all_done, launched, stdout=None, stderr=None):
        """
        :param all_done: Deferred that gets callback() when our process exits (.errback if it exits non-zero)
        :param launched: Deferred that gets callback() when our process starts.
        :param stdout: a file-like object for any stdout data
        :param stderr: a file-like object for any stderr data
        """
        self._reactor = reactor
        self._stderr = stderr
        self._stdout = stdout

        self._all_done = all_done
        self._launched = launched

        # message -> Deferred
        # for everything being awaited in the logs
        self._awaiting_messages = dict()
        # everything waiting for exit
        self._awaiting_exit = []

        #: all the collected stderr and stdout output
        self.logs = StringIO()

    def when_log_message_seen(self, msg):
        """
        :returns: a Deferred that fires when 'msg' is seen in the logs (or
            err if we lose the connection before that)
        """
        d = Deferred()
        try:
            self._awaiting_messages[msg].append(d)
        except KeyError:
            self._awaiting_messages[msg] = [d]
        self._check_awaiting_messages()
        return d

    def when_exited(self):
        """
        :returns: a Deferred that fires when this crossbar has exited
        """
        d = Deferred()
        self._awaiting_exit.append(d)
        return d

    def connectionMade(self):
        """ProcessProtocol override"""
        if not self._launched.called:
            self._launched.callback(self)

    def outReceived(self, data):
        """ProcessProtocol override"""
        self.logs.write(data.decode('utf8'))
        if self._stdout:
            self._stdout.write(data.decode('utf8'))
        self._check_awaiting_messages()

    def errReceived(self, data):
        """ProcessProtocol override"""
        self.logs.write(data.decode('utf8'))
        if self._stderr:
            self._stderr.write(data.decode('utf8'))
        self._check_awaiting_messages()

    def _check_awaiting_messages(self):
        found = []
        done = []
        for msg, waiters in self._awaiting_messages.items():
            if msg in self.logs.getvalue():
                found.extend(waiters)
                done.append(msg)
        for msg in done:
            del self._awaiting_messages[msg]
        for d in found:
            d.callback(None)

    def processExited(self, reason):
        """IProcessProtocol API"""
        # print("processExited", reason)

    def processEnded(self, reason):
        """IProcessProtocol API"""
        # reason.value should always be a ProcessTerminated instance
        fail = reason.value
        # print('processEnded', fail)

        for _, waiters in self._awaiting_messages.items():
            for d in waiters:
                d.errback(reason)

        for d in self._awaiting_exit:
            d.callback(None)
        self._awaiting_exit = []

        if fail.exitCode != 0 and fail.exitCode is not None:
            msg = 'Process exited with code "{}".'.format(fail.exitCode)
            err = RuntimeError(msg)
            self._all_done.errback(fail)
            if not self._launched.called:
                self._launched.errback(err)
        else:
            self._all_done.callback(fail)
            if not self._launched.called:
                print("FIXME: _launched should have been callbacked by now.")
                self._launched.callback(self)


class HelperSession(ApplicationSession):
    '''
    This is a WAMP session for the tests to use.
    '''

    def onJoin(self, details):
        # XXX could register methods etc if we wanted, too
        self.config.extra['running'].callback(self)

    def onLeave(self, details):
        # XXX note to self: this is the solution to the "illegal
        # switch in blockon" problem I was having -- the ultimate
        # reason, though, is because autobahn/wamp/protocol.py:426 or
        # so is aborting from the other side (missing import in my
        # case) and so we simply never call/errback on our
        # Deferred. But this bring up an interesting issue: how *is*
        # one supposed to deal with this sort of thing in client-code?
        d = self.config.extra['running']
        if not d.called:
            d.errback(RuntimeError("onLeave: {}".format(details.message)))
        ApplicationSession.onLeave(self, details)
        all_done = self.config.extra.get('all_done', None)
        if all_done:
            all_done.callback(details)


# these helpers all just call into _start_session, but exist to make
# it more obvious what type of session your test is *trying* to
# create. Just the url/realm defaults change. Beware that these
# URIs/realms are tied to the configuration in conftest.py in the
# crossbar() and auth_crossbar() fixtures.
# NOTE: these can't start with "test". "testee_session" starts with "test"...


@inlineCallbacks
def functest_session(debug=False, url=u'ws://localhost:6565/ws', realm=u'functest_realm1',
                     session_factory=HelperSession, ssl=None, **kw):
    """
    Create a session connected to the crossbar fixture's websocket
    """
    r = yield _start_session(debug, url, realm, session_factory, ssl=ssl, **kw)
    returnValue(r)


@inlineCallbacks
def functest_auth_session(debug=False, url=u'ws://localhost:7575/test_wampcra', realm=u'auth_realm',
                          session_factory=AuthenticatedSession, **kw):
    """
    WAMP-CRA authenticated session to the auth_crossbar fixture's websocket
    """
    r = yield _start_session(debug, url, realm, session_factory, **kw)
    returnValue(r)


@inlineCallbacks
def cts_session(debug=False, url=u'ws://localhost:8080', realm=u'io.crossbar.cts',
                session_factory=HelperSession, **kw):
    """
    A session connected to the CTS session itself
    """
    r = yield _start_session(debug, url, realm, session_factory, **kw)
    returnValue(r)


# the "real" session-starting helper, not intended to be used outside
# here (use one of the helpers above, or create another one if that
# makes sense)
# note: not pytest.inlineCallbacks because this isn't a test
@inlineCallbacks
def _start_session(debug, url, realm, session_factory, ssl=None, **kw):
    """
    A helper that returns a Deferred that yields a fresh
    HelperSession running against the local test crossbar
    instance. "running" means onJoin was just called.

    Any extra kwargs are passed through to the ApplicationSession
    instance via the "confg.extra" dict.

    For more advanced test-cases, you can pass in the url, realm
    and/or the ApplicationSession subclass (or factory function) if
    you need control of those. The factory-method is passed the config
    object, a :class:`autobahn.wamp.types.ComponentConfig` instance.

    Note if you do this and aren't using HelperSession, you'll
    have to arrange for the Deferred passed in self.config.extra['running'] to
    have its callback or errback invoked.
    """
    running_d = Deferred()       # see HelperSession above
    extra = kw
    assert 'running' not in extra
    extra['running'] = running_d
    extra.update(kw)

    runner = ApplicationRunner(url, realm=realm, extra=extra, ssl=ssl)
    runner.run(session_factory, start_reactor=False)
    session = yield running_d
    returnValue(session)

@inlineCallbacks
def start_crossbar(reactor, virtualenv, cbdir, crossbar_config, log_level=False,
                   stdout=sys.stdout, stderr=sys.stderr):
    sys.stdout.write('start_crossbar\n\n')
    sys.stdout.flush()
    try:
        mkdir(cbdir)
    except OSError as e:
        pass
    print("   running in", cbdir)

    # write configuration for this crossbar instance
    with open(path.join(cbdir, 'config.json'), 'w') as cfgfile:
        cfgfile.write(json.dumps(crossbar_config, sort_keys=True, indent=4))

    finished = Deferred()
    launched = Deferred()

    # launch the crossbar node
    protocol = CrossbarProcessProtocol(
        reactor, finished, launched,
        stdout=stdout, stderr=stderr,
    )
    # exe = path.join(virtualenv, 'bin', 'crossbar')
    # exe = os.path.abspath('./crossbar-linux-amd64-20190129-085ba04')
    exe = 'crossbar'
    #exe = '/usr/local/bin/crossbar-linux-amd64-20190130-684dd82'
    args = [exe, 'start', '--cbdir', cbdir]
    if log_level:
        levels = ("critical", "error", "warn", "info", "debug", "failure", "trace")
        if log_level not in levels:
            raise RuntimeError('log_level not in {}'.format(", ".join(levels)))
        args.extend(['--loglevel', str(log_level)])

    env = environ.copy()
    # Because Python has buffered stdout and our tests have such short life
    # cycles, some logs won't be flushed from stderr/stdout until the process
    # ends, rather than when the events happen. This environment variable turns
    # off buffered stdout/stderr.
    env["PYTHONUNBUFFERED"] = "1"

    transport = reactor.spawnProcess(
        protocol, exe, args, path=cbdir, env=env)

    yield launched
    returnValue(protocol)


@inlineCallbacks
def start_cfx(reactor, personality, cbdir, config=None, log_level=False, stdout=sys.stdout, stderr=sys.stderr):
    sys.stdout.write('crossbar\n\n')
    sys.stdout.flush()

    # write configuration for this crossbar instance
    if config:
        with open(path.join(cbdir, 'config.json'), 'w') as cfgfile:
            cfgfile.write(json.dumps(config, sort_keys=True, indent=4))

    finished = Deferred()
    launched = Deferred()

    # launch the crossbar node
    protocol = CrossbarProcessProtocol(
        reactor, finished, launched,
        stdout=stdout, stderr=stderr,
    )
    # exe = os.path.abspath('./crossbar-linux-amd64-20190129-085ba04')
    #exe = '/usr/local/bin/crossbar-linux-amd64-20190130-684dd82'
    exe = 'crossbar'
    args = [exe, personality, 'start', '--cbdir', str(cbdir)]
    if log_level:
        levels = ("critical", "error", "warn", "info", "debug", "failure", "trace")
        if log_level not in levels:
            raise RuntimeError('log_level not in {}'.format(", ".join(levels)))
        args.extend(['--loglevel', str(log_level)])

    env = environ.copy()
    # Because Python has buffered stdout and our tests have such short life
    # cycles, some logs won't be flushed from stderr/stdout until the process
    # ends, rather than when the events happen. This environment variable turns
    # off buffered stdout/stderr.
    env["PYTHONUNBUFFERED"] = "1"

    transport = reactor.spawnProcess(
        protocol, exe, args, path=cbdir, env=env)

    yield launched
    returnValue(protocol)


def _create_temp(request, prefix="cts_"):
    """
    internal helper. request should be a py.test request context
    """
    tmp = mkdtemp(prefix=prefix)
    def cleanup():
        if request.config.getoption('coverage', False):
            for covfile in listdir(tmp):
                if covfile.startswith('.coverage'):
                    p = path.join(tmp, covfile)
                    print('   saved "{}" to "{}".'.format(p, path.curdir))
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


def _cleanup_crossbar(protocol):
    print("Running Crossbar.io cleanup")
    try:
        # if this is KILL we won't get coverage data written
        protocol.transport.signalProcess('TERM')
        pytest.blockon(sleep(1))
#        protocol.transport.signalProcess('KILL')

    except ProcessExitedAlready:
        print("  crossbar already exited.")


class ManagementClientSession(ApplicationSession):

    def onConnect(self):
        self._key = self.config.extra[u'key']
        extra = {
            u'pubkey': self._key.public_key(),
            u'trustroot': None,
            u'challenge': None,
            u'channel_binding': u'tls-unique',
        }
        for k in [u'activation_code', u'request_new_activation_code']:
            if k in self.config.extra and self.config.extra[k]:
                extra[k] = self.config.extra[k]

        self.join(
            self.config.realm,
            authmethods=[u'cryptosign'],
            authid=self.config.extra.get(u'authid', None),
            authrole=self.config.extra.get(u'authrole', None),
            authextra=extra)

    def onChallenge(self, challenge):
        return self._key.sign_challenge(self, challenge)

    def onJoin(self, details):
        print(hl('ManagementClientSession.onJoin: {}'.format(details), bold=True))
        if 'ready' in self.config.extra:
            self.config.extra['ready'].callback((self, details))

    def onLeave(self, reason):
        print(hl('ManagementClientSession.onLeave: {}'.format(reason), bold=True))
        self.disconnect()


class AppClientSession(ApplicationSession):

    def onJoin(self, details):
        # print(hl('AppClientSession.onJoin: {}'.format(details), color='green', bold=True))
        if 'ready' in self.config.extra:
            self.config.extra['ready'].callback((self, details))

    def onLeave(self, reason):
        # print(hl('AppClientSession.onLeave: {}'.format(reason), color='green', bold=True))
        self.disconnect()


def functest_management_session(url=u'ws://localhost:9000/ws', realm=u'com.crossbario.fabric'):

    txaio.start_logging(level='info')

    privkey_file = os.path.abspath(os.path.expanduser('~/.crossbar/default.priv'))
    print('usering keyfile from', privkey_file)

    # for authenticating the management client, we need a Ed25519 public/private key pair
    # here, we are reusing the user key - so this needs to exist before
    privkey_hex = None
    user_id = None

    if not os.path.exists(privkey_file):
        raise Exception('private key file {} does not exist'.format(privkey_file))
    else:
        with open(privkey_file, 'r') as f:
            data = f.read()
            for line in data.splitlines():
                if line.startswith('private-key-ed25519'):
                    privkey_hex = line.split(':')[1].strip()
                if line.startswith('user-id'):
                    user_id = line.split(':')[1].strip()

    if privkey_hex is None:
        raise Exception('no private key found in keyfile!')

    if user_id is None:
        raise Exception('no user ID found in keyfile!')

    key = cryptosign.SigningKey.from_key_bytes(binascii.a2b_hex(privkey_hex))
    extra = {
        u'key': key,
        u'authid': user_id,
        u'ready': Deferred(),
        u'return_code': None,
        u'command': CmdListManagementRealms()
    }

    runner = ApplicationRunner(url=url, realm=realm, extra=extra)
    runner.run(ManagementClientSession, start_reactor=False)

    return extra[u'ready']


def functest_app_session(url=u'ws://localhost:8080/ws', realm=u'realm1'):

    txaio.start_logging(level='info')

    extra = {
        u'ready': Deferred(),
    }
    runner = ApplicationRunner(url=url, realm=realm, extra=extra)
    runner.run(AppClientSession, start_reactor=False)

    return extra[u'ready']
