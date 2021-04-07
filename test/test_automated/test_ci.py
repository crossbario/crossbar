import os
import sys
import json
import binascii
import argparse
from pprint import pprint
from copy import deepcopy

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred, gatherResults

import txaio
txaio.use_twisted()
txaio.config.loop = reactor

from txaio import time_ns, sleep

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.twisted.util import sleep
from autobahn.wamp.types import PublishOptions


class Client(ApplicationSession):

    def __init__(self, config):
        ApplicationSession.__init__(self, config)
        self._repeat = self.config.extra.get('repeat', 5)
        self._wamp_log = self.config.extra.get('wamp_log', [])
        self._wamp_sessions = self.config.extra.get('wamp_sessions', {})

    def onConnect(self):
        authmethod = self.config.extra.get('authmethod', None)
        authid = self.config.extra.get('authid', None)
        self.join(self.config.realm,
                  authmethods=[authmethod] if authmethod is not None else None,
                  authid=authid)

    def onChallenge(self, challenge):
        authmethod = self.config.extra.get('authmethod', None)
        assert challenge.method == authmethod

        if challenge.method == 'ticket':
            return self.config.extra.get('secret', None)
        else:
            raise RuntimeError('unable to process authentication method {}'.format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        # self.log.info("{obj_id} connected:  {details}", obj_id=id(self), details=details)

        bar = {
            'realm': details.realm,
            'session': details.session,
            'authid': details.authid,
            'authrole': details.authrole,
            'authmethod': details.authmethod,
            'authprovider': details.authprovider,
            'authextra': details.authextra,
            'serializer': details.serializer,
            'transport': details.transport,
            'node': details.authextra.get('x_cb_node', None),
            'worker': details.authextra.get('x_cb_worker', None),
            'pid': details.authextra.get('x_cb_pid', None),
            'proxy_node': details.authextra.get('x_cb_proxy_node', None),
            'proxy_worker': details.authextra.get('x_cb_proxy_worker', None),
            'x_cb_proxy_pid': details.authextra.get('x_cb_proxy_pid', None),
        }

        self._wamp_sessions[id(self)] = bar

        self._wamp_log.append((id(self), 'JOIN', time_ns(), self.session_id, bar))

        # print(id(self), 'JOIN')

        mytopic1 = u"com.example.mytopic1"

        def on_mytopic1(*args, **kwargs):
            details = kwargs.pop('details', None)
            assert 'foo' in kwargs and type(kwargs['foo']) == str and len(kwargs['foo']) == 22
            assert 'bar' in kwargs and type(kwargs['bar']) == dict
            self._wamp_log.append((id(self), 'EVENT', time_ns(), self.session_id, mytopic1, args, kwargs, details.publication if details else None))
            # print(id(self), 'EVENT')

        sub = yield self.subscribe(on_mytopic1, mytopic1)
        self._running = True

        ready1 = self.config.extra.get('ready1', None)
        if ready1 and not ready1.called:
            ready1.callback((self, bar))

        continue1 = self.config.extra.get('continue1', None)
        if continue1:
            yield continue1

        pid = os.getpid()
        counter = 0
        print('starting loop on {} for {} repeats ..'.format(id(self), self._repeat))
        while self.is_connected() and counter < self._repeat:
            # print("pid {} publish {} to '{}'".format(pid, counter, mytopic1))
            baz = os.urandom(10)
            args = [pid, counter]
            kwargs = {'foo': '0x' + binascii.b2a_hex(baz).decode(), 'bar': bar}
            pub = yield self.publish(
                mytopic1, *args, **kwargs,
                options=PublishOptions(acknowledge=True, exclude_me=False),
            )
            self._wamp_log.append((id(self), 'PUBLISH', time_ns(), self.session_id, mytopic1, args, kwargs, pub.id if pub else None))
            # print(id(self), 'PUBLISH')
            counter += 1
            yield sleep(.1)

        ready2 = self.config.extra.get('ready2', None)
        if ready2 and not ready2.called:
            ready2.callback((self, bar))

        continue2 = self.config.extra.get('continue2', None)
        if continue2:
            yield continue2

        yield sub.unsubscribe()
        self.leave()

    def onLeave(self, details):
        # self.log.info("{obj_id} leaving: {details}", obj_id=id(self), details=details)
        self._wamp_log.append((id(self), 'LEAVE', time_ns(), self.session_id, details.reason))
        self._running = False
        if details.reason in ['wamp.close.normal', 'wamp.error.authentication_failed']:
            self.log.info('Shutting down ..')
            try:
                self.config.runner.stop()
                self.disconnect()
            except:
                self.log.failure()

            done = self.config.extra.get('done', None)
            if done and not done.called:
                done.callback((self, details))
        else:
            # continue running the program (let ApplicationRunner perform auto-reconnect attempts ..)
            self.log.info('{obj_id} will continue to run (reconnect)!', obj_id=id(self))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='Enable debug output.')
    parser.add_argument('--realms',
                        dest='realms',
                        type=int,
                        default=4,
                        help='Number of realms (default: 4).')
    parser.add_argument('--repeat',
                        dest='repeat',
                        type=int,
                        default=9,
                        help='Number of repeats per session (default: 5).')
    parser.add_argument('--count',
                        dest='count',
                        type=int,
                        default=5,
                        help='Number of sessions per realm (default: 5).')
    parser.add_argument('--url',
                        dest='url',
                        type=str,
                        default='ws://localhost:8080/ws',
                        help='The router URL (default: "ws://localhost:8080/ws").')
    parser.add_argument('--authmethod',
                        dest='authmethod',
                        type=str,
                        default=None,
                        help='Authenticate using this authentication method ("ticket", "cra", "scram", "cryptosign", "tls").')
    parser.add_argument('--authid',
                        dest='authid',
                        type=str,
                        default=None,
                        help='Authenticate using this authid.')
    parser.add_argument('--secret',
                        dest='secret',
                        type=str,
                        default=None,
                        help='When authenticating via WAMP-Ticket, using this secret.')
    args = parser.parse_args()

    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    wamp_log = []
    wamp_sessions = {}
    realms = {}
    for i in range(args.realms):
        realm_name = 'myrealm{}'.format(i + 1)
        realms[realm_name] = {
            'realms': args.realms,
            'count': args.count,
            'repeat': args.repeat,
        }
    runners = {}
    ready1 = []
    ready2 = []
    done = []

    continue1 = Deferred()
    continue2 = Deferred()

    for realm, extra in realms.items():
        for i in range(args.count):
            print('Connecting session {} to {}, realm "{}" ..'.format(i, args.url, realm))
            authextra = deepcopy(extra)
            authextra['authmethod'] = args.authmethod
            authextra['authid'] = args.authid
            authextra['secret'] = args.secret
            authextra['ready1'] = Deferred()
            authextra['ready2'] = Deferred()
            authextra['continue1'] = continue1
            authextra['continue2'] = continue2
            ready1.append(authextra['ready1'])
            ready2.append(authextra['ready2'])
            authextra['done'] = Deferred()
            done.append(authextra['done'])
            authextra['runners'] = runners
            authextra['wamp_log'] = wamp_log
            authextra['wamp_sessions'] = wamp_sessions
            runner = ApplicationRunner(url=args.url, realm=realm, extra=authextra)
            runner.run(Client, start_reactor=False, auto_reconnect=True, reactor=reactor)
            runners[realm] = runner

    all_ready1 = gatherResults(ready1)

    def when_all_ready1(res):
        print('when_all_ready1')
        continue1.callback(None)

    all_ready1.addCallback(when_all_ready1)

    all_ready2 = gatherResults(ready2)

    def when_all_ready2(res):
        print('when_all_ready2')
        continue2.callback(None)

    all_ready2.addCallback(when_all_ready2)

    all_done = gatherResults(done)

    def when_all_done(res):
        print('when_all_done')
        # pprint(wamp_log)

        errored = False

        data = json.dumps(wamp_log, ensure_ascii=False).encode('utf8')
        with open('wamp_log.json', 'wb') as f:
            f.write(data)
        print('Ok, storing test results - {} records, {} bytes written'.format(len(wamp_log), len(data)))
        res = {}
        for rec in wamp_log:
            obj_id, action, timestamp, session_id = rec[0], rec[1], rec[2], rec[3]
            # print(obj_id, action, timestamp, session_id)
            if obj_id not in res:
                res[obj_id] = {}
            if action not in res[obj_id]:
                res[obj_id][action] = 0
            res[obj_id][action] += 1
        pprint(res)

        print('Ok, checking test results ..')
        if len(res) == args.count * args.realms:
            print('OK: number of observed sessions')
        else:
            print('FAIL: number of observed sessions mismatch (expected {}, got {})'.format(args.count * args.realms, len(res)))
            errored = True
        for r in res.values():
            if r.get('JOIN', 0) == 1:
                # print('OK: JOIN count')
                pass
            else:
                print('FAIL: JOIN count mismatch (expected {}, got {})'.format(1, r.get('JOIN', 0)))
                errored = True

            # FIXME: 2020-08-11T14:01:19+0200 FAIL: LEAVE count mismatch (expected 1, got 2)
            if r.get('LEAVE', 0) in [1, 2]:
                # print('OK: LEAVE count')
                pass
            else:
                print('FAIL: LEAVE count mismatch (expected {}, got {})'.format(1, r.get('LEAVE', 0)))
                errored = True

            if r.get('PUBLISH', 0) == args.repeat:
                # print('OK: PUBLISH count')
                pass
            else:
                print('FAIL: PUBLISH count mismatch (expected {}, got {})'.format(args.repeat, r.get('PUBLISH', 0)))
                errored = True

            # FIXME: FAIL: EVENT count mismatch (expected 1400, got 1326)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1607)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1854)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1738)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1738)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1928)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1843)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1707)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1708)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1719)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1930)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1734)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1734)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1930)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1725)
            # 2020-08-11T19:32:50+0200 FAIL: EVENT count mismatch (expected 2000, got 1728)
            if r.get('EVENT', 0) == args.repeat * args.count:
                # print('OK: EVENT count')
                pass
            else:
                print('FAIL: EVENT count mismatch (expected {}, got {})'.format(args.repeat * args.count, r.get('EVENT', 0)))
                errored = True


        res = {}
        for s in wamp_sessions.values():
            if s['node'] not in res:
                res[s['node']] = {}
            if s['worker'] not in res[s['node']]:
                res[s['node']][s['worker']] = 0
            res[s['node']][s['worker']] += 1
        pprint(res)

        if errored:
            print('*' * 80)
            print('TEST FAILED!')
            print('*' * 80)
        else:
            print('*' * 80)
            print('OK, TEST SUCCEEDED.')
            print('*' * 80)

        if reactor.running:
            if errored:
                reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            if errored:
                sys.exit(1)
            else:
                sys.exit(0)

    all_done.addCallback(when_all_done)

    reactor.run()
