###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import sys
import argparse
import binascii

import txaio
from autobahn.wamp import cryptosign
from autobahn.wamp.exception import ApplicationError
from autobahn.websocket.util import parse_url
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

__all__ = ('ShellClient', 'ManagementClientSession', 'run', 'create_management_session')

from crossbar.shell.command import CmdListManagementRealms
from twisted.internet.defer import Deferred


class ShellClient(ApplicationSession):
    """
    Management CLI application session.
    """
    def onConnect(self):  # noqa: N802
        self.log.info('{klass}.onConnect()', klass=self.__class__.__name__)

        self._key = self.config.extra['key']
        self._command = self.config.extra.get('command', None)
        self._main = self.config.extra.get('main', None)

        # authentication extra information for wamp-cryptosign
        #
        extra = {
            # forward the client pubkey: this allows us to omit authid as
            # the router can identify us with the pubkey already
            'pubkey': self._key.public_key(),

            # not yet implemented. a public key the router should provide
            # a trustchain for it's public key. the trustroot can eg be
            # hard-coded in the client, or come from a command line option.
            'trustroot': self.config.extra.get('trustroot', None),

            # not yet implemented. for authenticating the router, this
            # challenge will need to be signed by the router and send back
            # in AUTHENTICATE for client to verify. A string with a hex
            # encoded 32 bytes random value.
            'challenge': self.config.extra.get('challenge', None),

            # use TLS channel binding
            'channel_binding': self.config.extra.get('channel_binding', None),
        }

        # used for user login/registration activation code
        for k in ['activation_code', 'request_new_activation_code']:
            if k in self.config.extra and self.config.extra[k]:
                extra[k] = self.config.extra[k]

        # now request to join ..
        self.join(self.config.realm,
                  authmethods=['cryptosign'],
                  authid=self.config.extra.get('authid', None),
                  authrole=self.config.extra.get('authrole', None),
                  authextra=extra)

    def onChallenge(self, challenge):  # noqa: N802
        self.log.info('{klass}.onChallenge(challenge={challenge})', klass=self.__class__.__name__, challenge=challenge)

        # sign and send back the challenge with our private key.
        try:
            channel_id_type = self.config.extra.get('channel_binding', None)
            channel_id = self.transport.transport_details.channel_id.get(channel_id_type, None)
            sig = self._key.sign_challenge(challenge, channel_id=channel_id, channel_id_type=channel_id_type)
        except Exception as e:
            self.log.failure()
            self.leave(ApplicationError.AUTHENTICATION_FAILED, str(e))
        else:
            return sig

    async def onJoin(self, details):  # noqa: N802
        self.log.info('{klass}.onJoin(details={details})', klass=self.__class__.__name__, details=details)

        done = self.config.extra.get('done', None)

        result = None
        error = None
        if self._command:
            self.log.info('{klass}: running command {command}', klass=self.__class__.__name__, command=self._command)
            try:
                result = await self._command.run(self)
                self.log.info('command run with result {result}', result=result)
            except Exception as e:
                self.log.warn('command failed: {error}', error=e)
                error = e
        elif self._main:
            self.log.info('{klass}: running main function {main}', klass=self.__class__.__name__, main=self._main)
            try:
                result = await self._main(self)
                self.log.info('main run with result {result}', result=result)
            except Exception as e:
                self.log.warn('main failed: {error}', error=e)
                error = e
        else:
            self.log.info('{klass}: no command or main function to run!', klass=self.__class__.__name__)

        if done and not txaio.is_called(done):
            if error:
                self.log.warn('{klass}: command returned with error ({error})',
                              klass=self.__class__.__name__,
                              error=error)
                txaio.reject(done, error)
            else:
                self.log.info('{klass}: command returned with success ({result})',
                              klass=self.__class__.__name__,
                              result=result)
                txaio.resolve(done, (details, result))

        self.log.info('{klass}.onJoin(): finished!', klass=self.__class__.__name__)

        if self._main:
            self.leave()

    def onLeave(self, details):  # noqa: N802
        self.log.info('{klass}.onLeave(details={details})', klass=self.__class__.__name__, details=details)

        # reason=<wamp.error.authentication_failed>
        if details.reason != 'wamp.close.normal':
            done = self.config.extra.get('done', None)
            error = ApplicationError(details.reason, details.message)
            if done and not txaio.is_called(done):
                self.log.warn('{klass}: command returned with error ({error})',
                              klass=self.__class__.__name__,
                              error=error)
                txaio.reject(done, error)

        self.disconnect()

    def onDisconnect(self):  # noqa: N802
        self.log.info('{klass}.onDisconnect()', klass=self.__class__.__name__)
        if self._main:
            try:
                self.config.runner.stop()
                self.disconnect()
            except:
                self.log.failure()
            from twisted.internet import reactor
            if reactor.running:
                reactor.stop()


class ManagementClientSession(ApplicationSession):
    def onConnect(self):
        self._key = self.config.extra['key']
        extra = {
            'pubkey': self._key.public_key(),
            'trustroot': self.config.extra.get('trustroot', None),
            'challenge': self.config.extra.get('challenge', None),
            'channel_binding': self.config.extra.get('channel_binding', None),
        }
        for k in ['activation_code', 'request_new_activation_code']:
            if k in self.config.extra and self.config.extra[k]:
                extra[k] = self.config.extra[k]

        self.join(self.config.realm,
                  authmethods=['cryptosign'],
                  authid=self.config.extra.get('authid', None),
                  authrole=self.config.extra.get('authrole', None),
                  authextra=extra)

    def onChallenge(self, challenge):
        channel_id_type = self.config.extra.get('channel_binding', None)
        channel_id = self.transport.transport_details.channel_id.get(channel_id_type, None)
        sig = self._key.sign_challenge(challenge, channel_id=channel_id, channel_id_type=channel_id_type)
        return sig

    def onJoin(self, details):
        if 'ready' in self.config.extra:
            self.config.extra['ready'].callback((self, details))

    def onLeave(self, reason):
        self.disconnect()


def create_management_session(url='wss://master.xbr.network/ws',
                              realm='com.crossbario.fabric',
                              privkey_file='default.priv'):

    txaio.start_logging(level='info')

    privkey_file = os.path.join(os.path.expanduser('~/.crossbar'), privkey_file)

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

    url_is_secure, _, _, _, _, _ = parse_url(url)

    key = cryptosign.CryptosignKey.from_bytes(binascii.a2b_hex(privkey_hex))
    extra = {
        'key': key,
        'authid': user_id,
        'ready': Deferred(),
        'return_code': None,
        'command': CmdListManagementRealms(),

        # WAMP-cryptosign TLS channel binding
        'channel_binding': 'tls-unique' if url_is_secure else None,
    }

    runner = ApplicationRunner(url=url, realm=realm, extra=extra)
    runner.run(ManagementClientSession, start_reactor=False)

    return extra['ready']


def run(main=None, parser=None):

    # parse command line arguments
    parser = parser or argparse.ArgumentParser()

    parser.add_argument('--debug',
                        dest='debug',
                        action='store_true',
                        default=False,
                        help='Enable logging at level "debug".')
    parser.add_argument('--url',
                        dest='url',
                        type=str,
                        default='wss://master.xbr.network/ws',
                        help='Management service of the XBR Network'
                        '(default: wss://master.xbr.network/ws')
    parser.add_argument('--realm',
                        dest='realm',
                        type=str,
                        default=None,
                        help='The (management) realm to join on the management server')
    parser.add_argument('--keyfile',
                        dest='keyfile',
                        type=str,
                        default=None,
                        help='The private client key file to use for authentication.')
    parser.add_argument('--authmethod',
                        dest='authmethod',
                        type=str,
                        default='cryptosign',
                        help='Authentication method: cryptosign or anonymous')

    args = parser.parse_args()

    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    args.keyfile = os.path.abspath(os.path.expanduser(args.keyfile))
    print('usering keyfile from', args.keyfile)

    extra = None
    if args.authmethod == 'cryptosign':

        # for authenticating the management client, we need a Ed25519 public/private key pair
        # here, we are reusing the user key - so this needs to exist before
        privkey_file = os.path.expanduser(args.keyfile)
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

        key = cryptosign.CryptosignKey.from_bytes(binascii.a2b_hex(privkey_hex))

        extra = {'args': args, 'key': key, 'authid': user_id, 'main': main, 'return_code': None}

    elif args.authmethod == 'anonymous':

        extra = {'args': args, 'main': main, 'return_code': None}

    else:
        raise Exception('logic error')

    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra)

    runner.run(ShellClient)

    return_code = extra['return_code']
    if isinstance(return_code, int) and return_code != 0:
        sys.exit(return_code)


if __name__ == '__main__':
    run()
