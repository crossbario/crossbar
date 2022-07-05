###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import uuid

from autobahn import util

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

import humanize
from datetime import datetime

import zlmdb

from crossbar._util import hl, hlid, hltype
from cfxdb.globalschema import GlobalSchema
from cfxdb.user import User, UserRole
from cfxdb.user import ActivationType, ActivationStatus, ActivationToken
from crossbar.master.node.messenger import Messenger

__all__ = ('Authenticator', 'Principal')


class Principal(object):
    """
    """
    def __init__(self, realm, authid, role, extra):
        """
        """
        self.realm = realm
        self.authid = authid
        self.role = role
        self.extra = extra

    @staticmethod
    def parse(obj):
        realm = obj.get('realm', None)
        authid = obj.get('authid', None)
        role = obj.get('role', None)
        extra = obj.get('extra', None)
        return Principal(realm, authid, role, extra)


class Node(object):
    def __init__(self, node_id, heartbeat, heartbeat_time, status='online'):
        self.node_id = node_id
        self.heartbeat = heartbeat
        self.heartbeat_time = heartbeat_time
        self.status = status

    def marshal(self):
        return {
            'id': self.node_id,
            'heartbeat': self.heartbeat,
            'timestamp': self.heartbeat_time,
            'status': self.status,
        }

    @staticmethod
    def parse(data):
        assert (type(data) == dict)

        node_id = data.get('node_id', None)
        heartbeat = data.get('heartbeat', None)
        heartbeat_time = data.get('heartbeat_time', None)
        status = data.get('status', None)

        # FIXME: check above

        node = Node(node_id, heartbeat, heartbeat_time, status)
        return node


class Authenticator(ApplicationSession):
    """
    Central CFC dynamic authenticator. This component is responsible for all
    frontend WAMP connections to CFC, for both CF nodes, CFC UI and user CFC scripts.
    """

    GLOBAL_USER_REALM = 'com.crossbario.fabric'
    """
    Global users realm on Crossbar.io.
    """

    GLOBAL_USER_REALM_USER_ROLE = 'user'
    """
    The WAMP authrole regular users get on the Crossbar.io domain (global) users
    realm. A role different from this only makes sense for Crossbar.io admins.
    """

    MREALM_USER_ROLES = ['guest', 'developer', 'operator', 'admin', 'owner']
    """
    All permissible roles a user can take on a management realm. This is a fixed
    set hardwired into Crossbar.io!
    """

    MREALM_CREATOR_DEFAULT_ROLES = ['owner']
    """
    THe set of roles a user creating a new management realm gets by default.
    """

    MREALM_NODE_ROLE = 'node'
    """
    The (fixed) role a user node gets when joining the management realm it is
    paired to.
    """

    ERROR_AUTH_INVALID_PARAMETERS = 'fabric.auth-failed.invalid-parameters'
    ERROR_AUTH_INVALID_PARAMETERS_MSG = 'Invalid parameters in authentication: {}'

    ERROR_AUTH_PENDING_ACT = 'fabric.auth-failed.pending-activation'
    ERROR_AUTH_PENDING_ACT_MSG = 'There is a pending activation (from {} ago) - please check your email inbox, or request a new code'

    ERROR_AUTH_NO_PENDING_ACT = 'fabric.auth-failed.no-pending-activation'
    ERROR_AUTH_NO_PENDING_ACT_MSG = 'There is no (pending) activation for this user/pubkey, but an activation code was provided'

    ERROR_AUTH_INVALID_ACT_CODE = 'fabric.auth-failed.invalid-activation-code'
    ERROR_AUTH_INVALID_ACT_CODE_MSG = 'This activation code is invalid: {}'

    ERROR_AUTH_NODE_UNPAIRED = 'fabric.auth-failed.node-unpaired'
    ERROR_AUTH_NODE_UNPAIRED_MSG = 'This node is unpaired. Please pair the node with management realm first.'

    ERROR_AUTH_NODE_ALREADY_CONNECTED = 'fabric.auth-failed.node-already-connected'
    ERROR_AUTH_NODE_ALREADY_CONNECTED_MSG = 'A node with this pubkey/node_id/authid is already connected.'

    ERROR_AUTH_EMAIL_FAILURE = 'fabric.auth-failed.email-failure'

    ERROR_AUTH_NEW_USER = 'fabric.auth-failed.new-user-auth-code-sent'
    ERROR_AUTH_NEW_USER_MSG = 'We have sent an authentication code to {email}.'

    ERROR_AUTH_REGISTERED_USER = 'fabric.auth-failed.registered-user-auth-code-sent'
    ERROR_AUTH_REGISTERED_USER_MSG = 'We have sent an authentication code to {email}.'

    def __init__(self, config):
        ApplicationSession.__init__(self, config)
        self._connected_nodes = {}

        # public keys of superusers
        self._superusers = []
        if 'CROSSBAR_FABRIC_SUPERUSER' in os.environ:
            superuser_keyfile = os.environ['CROSSBAR_FABRIC_SUPERUSER'].strip()
            if superuser_keyfile:
                pubkey_file = os.path.abspath(os.environ['CROSSBAR_FABRIC_SUPERUSER'])
                if not os.path.exists(pubkey_file):
                    raise Exception(
                        'superuser public key file {} (set from CROSSBAR_FABRIC_SUPERUSER env var) does not exist'.
                        format(pubkey_file))
                with open(pubkey_file, 'r') as f:
                    data = f.read()
                    pubkey_hex = None
                    for line in data.splitlines():
                        if line.startswith('public-key-ed25519'):
                            pubkey_hex = line.split(':')[1].strip()
                            break
                    if pubkey_hex is None:
                        raise Exception(
                            'no public key line found in super user public key file {}'.format(pubkey_file))

                    self._superusers.append(pubkey_hex)
                    self.log.info(
                        hl('SUPERUSER public key {} loaded from {}'.format(pubkey_hex, pubkey_file),
                           color='green',
                           bold=True))

    async def onJoin(self, details):
        """
        Authenticator has joined the global realm ("com.crossbario.fabric").

        :param details: Session details.
        :type details: :class:`autobahn.wamp.types.SessionDetails`
        """
        # create database and attach tables to database slots
        #
        cbdir = self.config.extra['cbdir']
        config = self.config.extra.get('database', {})

        dbpath = config.get('path', '.db-controller')
        assert type(dbpath) == str
        dbpath = os.path.join(cbdir, dbpath)

        maxsize = config.get('maxsize', 128 * 2**20)
        assert type(maxsize) == int
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30

        self.log.debug(
            '{msg} [realm={realm}, session={session}, authid={authid}, authrole={authrole}, dbpath={dbpath}, maxsize={maxsize}]',
            realm=hlid(details.realm),
            session=details.session,
            authid=details.authid,
            authrole=hlid(details.authrole),
            msg=hl('Crossbar.io main authenticator starting ..', bold=True, color='green'),
            dbpath=hlid(dbpath),
            maxsize=hlid(maxsize))

        # self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self._db = zlmdb.Database.open(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self._db.__enter__()
        self._schema = GlobalSchema.attach(self._db)

        # Mailgun access key
        #
        access_key = None
        if 'mailgun' in self.config.extra and \
           'access_key' in self.config.extra['mailgun'] and \
           self.config.extra['mailgun']['access_key']:
            access_key = self.config.extra['mailgun']['access_key']
        else:
            if 'MAILGUN_KEY' in os.environ:
                access_key = os.environ['MAILGUN_KEY']
            else:
                self.log.warn('Mailgun access key unconfigured (not in config, and no env var MAILGUN_KEY set)')

        # Mailgun mail submit URL
        # eg https://api.mailgun.net/v3/mailing.crossbar.io/messages
        #
        submit_url = None
        if 'mailgun' in self.config.extra and \
           'submit_url' in self.config.extra['mailgun'] and \
           self.config.extra['mailgun']['submit_url']:
            submit_url = self.config.extra['mailgun']['submit_url']
        else:
            if 'MAILGUN_URL' in os.environ:
                submit_url = os.environ['MAILGUN_URL']
            else:
                self.log.warn('Mailgun submit URL unconfigured (not in config, and no env var MAILGUN_URL set)')

        # Quick hack - the above code doesn't work properly
        access_key = os.environ.get('MAILGUN_KEY', access_key)
        submit_url = os.environ.get('MAILGUN_URL', submit_url)

        # create Email sender. if submit_url or access_key was None, then the Messenger
        # will not send out mails, but log them at level "warn"!
        #
        self._messenger = Messenger(submit_url, access_key)

        # register our dynamic authenticator
        try:
            await self.register(self._authenticate, 'com.crossbario.fabric.authenticate')
        except Exception:
            self.log.failure('failed to register dynamic authenticator: {log_failure}')
            raise Exception('fatal: failed to register dynamic authenticator')

        # set service session to our authenticator
        self.config.controller.set_service_session(self, self._realm, self._authrole)

        self.log.info(
            'Ok, {component} ready on realm "{realm}" (session={session}, authid="{authid}", authrole="{authrole}", controller={controller}) {func}',
            component=hl('master node authenticator', color='green', bold=True),
            func=hltype(self.onJoin),
            realm=hlid(self._realm),
            session=hlid(self._session_id),
            authid=hlid(self._authid),
            authrole=hlid(self._authrole),
            controller=self.config.controller)

    async def _authenticate(self, realm, authid, details):
        """
        Main authenticator for Crossbar.io. This authenticates both users and user nodes
        to Crossbar.io by authenticating against information stored in controller database.
        """
        self.log.debug('authenticate({realm}, {authid}, {details})', realm=realm, authid=authid, details=details)

        # proceed according to authmethod
        #
        if 'authmethod' not in details:
            msg = 'missing "authmethod" in authentication details (WAMP HELLO message details)'
            raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                   Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))

        authmethod = details['authmethod']

        if authmethod not in ['cryptosign']:
            msg = 'authmethod "{}" not permissible'.format(authmethod)
            raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                   Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))

        if authmethod == 'cryptosign':

            # extract mandatory public key
            #
            if 'authextra' not in details or 'pubkey' not in details['authextra']:
                msg = 'missing public key in authextra for authmethod cryptosign'
                raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                       Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))
            pubkey = details['authextra']['pubkey']

            # check requested authrole
            #
            authrole = details.get('authrole', None)
            if realm is None:
                # this is either a node joining a management realm or a user joining
                # the global user realm. a node must request authrole "node"
                if authrole not in [None, Authenticator.MREALM_NODE_ROLE]:
                    msg = 'invalid requested authrole "{}" for realm "{}"'.format(authrole, realm)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                           Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))

            elif realm == Authenticator.GLOBAL_USER_REALM:
                # this is a user joining the global user realm - authrole is assigned
                # automatically and cannot be requested explicitly
                if authrole not in [None, Authenticator.GLOBAL_USER_REALM_USER_ROLE]:
                    msg = 'invalid requested authrole "{}" for realm "{}"'.format(authrole, realm)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                           Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))
            else:
                # this is a user joining a specific management realm.
                if authrole is not None and authrole not in Authenticator.MREALM_USER_ROLES:
                    msg = 'invalid requested authrole "{}" for realm "{}"'.format(authrole, realm)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                           Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))

            # proceed depending on whether to authenticate a user or a node
            #
            if authrole == Authenticator.MREALM_NODE_ROLE:
                if realm is not None:
                    msg = 'invalid requested realm "{}" for node - nodes MUST NOT request a realm (the realm is auto-assigned based on Crossbar.io configuration)'.format(
                        realm)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                           Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG.format(msg))

                # a node is authenticated based on the pubkey only, and realm/authid/authrole/..
                # are set from the configuration stored in controller database purely
                auth = self._auth_node(pubkey)
                return auth

            else:
                # a user may request to join different realms using the same pubkey, hence
                # we forward all info the client supplied
                activation_code = details['authextra'].get('activation_code', None)
                request_new_activation_code = details['authextra'].get('request_new_activation_code', False)
                auth = await self._auth_user(realm, authid, authrole, pubkey, activation_code,
                                             request_new_activation_code)
                return auth

        # safeguard: should not arrive here
        raise Exception('logic error')

    def _auth_node(self, pubkey):
        """
        Authenticate a Crossbar.io node.

        A user node is purely authenticated based on the node's public key, MUST request
        the authrole="node", and MUST NOT request a specific realm (the management realm
        of a node is automatically assigned by Crossbar.io).
        """
        self.log.debug('authenticating node with pubkey={pubkey}', pubkey=pubkey)

        # lookup the node by its public key (in hex)
        node = None
        with self._db.begin() as txn:
            node_oid = self._schema.idx_nodes_by_pubkey[txn, pubkey]
            if node_oid:
                node = self._schema.nodes[txn, node_oid]

        if node and node.mrealm_oid:
            if node.mrealm_oid not in self._connected_nodes:
                self._connected_nodes[node.mrealm_oid] = {}

            # for nodes, realm + authid MUST be configured, and authextra MAY be configured
            # note that a authenticating node MUST NOT override the configured values for
            # realm, authid, etc  - this is critical. Eg the management realm a node is
            # assigned to must only be chanced under the control of the Crossbar.io
            # backend, since the owner of a management realm pays for the usage the nodes
            # assigned to do produce. And since a node MUST have the realm set (or the whole
            # record is deleted, and the public key "no longer known"), nodes are always
            # authenticated and associated with the correct realm.
            #
            with self._db.begin() as txn:
                mrealm = self._schema.mrealms[txn, node.mrealm_oid]
            if mrealm:

                # use the node name (which can change!)
                assigned_auth_id = node.authid

                # use the node UUID (which never changes)
                # assigned_auth_id = str(node_oid)

                auth = {
                    'pubkey': pubkey,
                    'realm': mrealm.name,
                    'authid': assigned_auth_id,
                    'role': Authenticator.MREALM_NODE_ROLE,
                    'extra': node.authextra,
                    'cache': False
                }

                self._connected_nodes[node.mrealm_oid][node_oid] = auth

                self.log.info(
                    'authenticated managed node "{authid}" with pubkey "{pubkey}" on management realm "{realm}" (authrole="{authrole}") {func}',
                    pubkey=hlid('0x' + pubkey[:16] + '..'),
                    authid=hlid(auth['authid']),
                    authrole=hlid(auth['role']),
                    realm=hlid(auth['realm']),
                    func=hltype(self._auth_node))
                return auth

        # the node pairing process is completely driven from a logged in user session!
        # so either the node already is paired, or it is not - in which case, it needs
        # to be paired by a user, and there is nothing a node could do about or needs
        # to care, so we plainly bail out here ..
        #
        self.log.info('denied unpaired CF node with pubkey {pubkey}', pubkey=pubkey)
        raise ApplicationError(Authenticator.ERROR_AUTH_NODE_UNPAIRED, Authenticator.ERROR_AUTH_NODE_UNPAIRED_MSG)

    async def _auth_user(self,
                         realm,
                         authid,
                         authrole,
                         pubkey,
                         activation_code=None,
                         request_new_activation_code=False):
        """
        Authenticate a Crossbar.io user.

        For a user that is not yet registered, or a user key not yet associated
        with a user, this will raise an ApplicationError signaling the state
        of the registration process.
        """
        self.log.debug(
            'authenticating user for realm={realm}, authid={authid}, authrole={authrole}, pubkey={pubkey}, activation_code={activation_code}, request_new_activation_code={request_new_activation_code}',
            realm=realm,
            authid=authid,
            authrole=authrole,
            pubkey=pubkey,
            activation_code=activation_code,
            request_new_activation_code=request_new_activation_code)

        # we must protect against this!
        if activation_code and not authid:
            raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_PARAMETERS,
                                   Authenticator.ERROR_AUTH_INVALID_PARAMETERS_MSG)

        # get activation for authid/pubkey pair (this will succeed when the user is registered and
        # the pubkey is associated with the user - the 99% case)
        activation = None
        with self._db.begin() as txn:
            oid = self._schema.idx_act_tokens_by_authid_pubkey[txn, authid + pubkey]
            if oid:
                activation = self._schema.activation_tokens[txn, oid]

        # if the activation is still pending, allow to reset it and we will send
        # a new activation code
        if activation and activation.status == ActivationStatus.PENDING and request_new_activation_code:
            with self._db.begin(write=True) as txn:
                oid = self._schema.idx_act_tokens_by_authid_pubkey[txn, authid + pubkey]
                if oid:
                    del self._schema.activation_tokens[txn, oid]
                else:
                    raise Exception('no such activation')
            activation = None

        # get user (if any)
        user = None
        if authid:
            with self._db.begin() as txn:
                oid = self._schema.idx_users_by_email[txn, authid]
                if oid:
                    user = self._schema.users[txn, oid]

        is_new_user = user is None

        self.log.debug('authenticating user={user}, is_new_user={is_new_user}, activation={activation}',
                       user=user,
                       is_new_user=is_new_user,
                       activation=activation)

        if realm is None or realm == 'com.crossbario.fabric':
            realm = Authenticator.GLOBAL_USER_REALM
            authrole = Authenticator.GLOBAL_USER_REALM_USER_ROLE
        else:
            if authrole is None:
                authrole = 'owner'

        # superusers are treated special ..
        if pubkey in self._superusers:
            auth = {
                'pubkey': pubkey,
                'realm': realm,
                'authid': 'superuser',
                'role': authrole,
                'extra': None,
                'cache': False
            }
            self.log.info(
                hl('SUPERUSER authenticated (realm={}, authid={}, authrole={})'.format(
                    auth['realm'], auth['authid'], auth['role']),
                   color='green',
                   bold=True))
            return auth

        # if there is no activation yet, create/store a new one
        elif not activation:

            # check for user provided an activation code, though there is no activation currently
            if activation_code:
                raise ApplicationError(Authenticator.ERROR_AUTH_NO_PENDING_ACT,
                                       Authenticator.ERROR_AUTH_NO_PENDING_ACT_MSG)

            # ok, create a new activation in the database
            activation = ActivationToken()
            activation.oid = uuid.uuid4()
            activation.atype = ActivationType.REGISTRATION if is_new_user else ActivationType.LOGIN
            activation.created = datetime.utcnow()
            # activation.activated = None
            activation.code = util.generate_activation_code()
            activation.status = ActivationStatus.PENDING
            activation.email = authid
            activation.pubkey = pubkey

            with self._db.begin(write=True) as txn:
                self._schema.activation_tokens[txn, activation.oid] = activation

            if is_new_user:
                # send user message with activation code
                await self._messenger.send_user_registration_mail(authid, activation.code)
                self.log.info('User registration mail sent to {authid} with activation code {activation_code}',
                              authid=hlid(authid),
                              activation_code=hl(activation.code, color='red', bold=True))

                # deny authentication by raising an error and providing feedback to client
                raise ApplicationError(Authenticator.ERROR_AUTH_NEW_USER,
                                       Authenticator.ERROR_AUTH_NEW_USER_MSG.format(email=authid),
                                       email=authid)
            else:
                # send user message with activation code
                await self._messenger.send_user_login_mail(authid, activation.code)
                self.log.info('User login mail sent to {authid} with activation code {activation_code}',
                              authid=hlid(authid),
                              activation_code=hl(activation.code, color='red', bold=True))

                # deny authentication by raising an error and providing feedback to client
                raise ApplicationError(Authenticator.ERROR_AUTH_REGISTERED_USER,
                                       Authenticator.ERROR_AUTH_REGISTERED_USER_MSG.format(email=authid),
                                       email=authid)
        else:

            self.log.debug('Activation found in database:\n{activation}', activation=activation)

            if activation.status == ActivationStatus.ACTIVE:

                # ok, so the user's public key is known and active .. the 99% case

                # user provided an activation code, though there is no activation currently
                if activation_code:
                    raise ApplicationError(Authenticator.ERROR_AUTH_NO_PENDING_ACT,
                                           Authenticator.ERROR_AUTH_NO_PENDING_ACT_MSG)

                # .. if the user wants to join the global users realm, allow that,
                # but ignore any authrole that might have been requested
                if realm is None or realm == Authenticator.GLOBAL_USER_REALM:
                    auth = {
                        'pubkey': pubkey,
                        'realm': Authenticator.GLOBAL_USER_REALM,
                        'authid': authid,
                        'role': Authenticator.GLOBAL_USER_REALM_USER_ROLE,
                        'extra': None,
                        'cache': False
                    }
                    self.log.info('Found user {authid} with active pubkey, authenticating for global user realm',
                                  authid=authid)

                    return auth

                # .. if the user wants to join a specific (management) realm, we need to check more ..
                else:
                    user_roles = None
                    with self._db.begin() as txn:
                        user_oid = self._schema.idx_users_by_email[txn, authid]
                        if user_oid:
                            mrealm_oid = self._schema.idx_mrealms_by_name[txn, realm]
                            if mrealm_oid:
                                user_roles = self._schema.users_mrealm_roles[txn, (user_oid, mrealm_oid)]
                                self.log.info('user roles {user_roles}', user_roles=user_roles)
                            else:
                                self.log.info('no mrealm with name "{realm}"', realm=realm)
                        else:
                            self.log.info('no user for authid "{authid}"', authid=authid)

                    if not user_roles:
                        raise Exception('no realm "{}" or user not permitted'.format(realm))
                    else:
                        self.log.info('user has {roles} roles on realm {realm}', roles=user_roles.roles, realm=realm)

                    if authrole is None:
                        # the user did not request a specific role, so take the first one?
                        # or take the role with the highest privileges? or lowest? FIXME
                        authrole = min(user_roles.roles)  # the minimum is the _highest_ permission (OWNER=1)
                    else:
                        MAP = {
                            'owner': UserRole.OWNER,
                            'admin': UserRole.ADMIN,
                            'user': UserRole.USER,
                            'guest': UserRole.GUEST,
                        }
                        authrole = MAP.get(authrole, None)

                    # the user requested a specific role: check that the role is in the
                    # list of permitted roles the user may take on the management realm
                    if authrole not in user_roles.roles:
                        raise Exception('not authorized for role {}'.format(authrole))

                    # map the integer authrole to a string
                    MAP = {
                        UserRole.OWNER: 'owner',
                        UserRole.ADMIN: 'admin',
                        UserRole.USER: 'user',
                        UserRole.GUEST: 'guest',
                    }
                    authrole = MAP.get(authrole, None)

                    auth = {
                        'pubkey': pubkey,
                        'realm': realm,
                        'authid': authid,
                        'role': authrole,
                        'extra': None,
                        'cache': False
                    }
                    self.log.info('auth=\n{auth}', auth=auth)

                    self.log.info(
                        'Authenticated CF user with pubkey {pubkey}.. as authid "{authid}" on realm "{realm}"',
                        authid=authid,
                        realm=realm,
                        pubkey=pubkey[:16])

                    return auth

            elif activation.status == ActivationStatus.PENDING:

                now = datetime.utcnow()

                passed_secs = (now - activation.created).total_seconds()
                passed_secs_str = humanize.naturaldelta(passed_secs)

                if not activation_code:
                    raise ApplicationError(Authenticator.ERROR_AUTH_PENDING_ACT,
                                           Authenticator.ERROR_AUTH_PENDING_ACT_MSG.format(passed_secs_str))

                if activation_code != activation.code:
                    msg = 'code does not match pending one'
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_ACT_CODE,
                                           Authenticator.ERROR_AUTH_INVALID_ACT_CODE_MSG.format(msg))

                # check if the activation is expired (15min). if so, delete it, and bail out
                if passed_secs > (60 * 15):

                    with self._db.begin(write=True) as txn:
                        oid = self._schema.idx_act_tokens_by_authid_pubkey[txn, authid + pubkey]
                        if oid:
                            del self._schema.activation_tokens[txn, oid]
                        else:
                            raise Exception('no such activation')

                    msg = 'code created {} ago has expired'.format(passed_secs_str)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_ACT_CODE,
                                           Authenticator.ERROR_AUTH_INVALID_ACT_CODE_MSG.format(msg))

                # sanitize the stored activation info against what the client provided
                if activation.atype not in [ActivationType.LOGIN, ActivationType.REGISTRATION]:
                    msg = 'activation type "{}" is not for user login/registration.'.format(activation.atype)
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_ACT_CODE,
                                           Authenticator.ERROR_AUTH_INVALID_ACT_CODE_MSG.format(msg))

                if activation.email != authid:
                    msg = 'email associated with activation code does not match authid provided by client.'
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_ACT_CODE,
                                           Authenticator.ERROR_AUTH_INVALID_ACT_CODE_MSG.format(msg))

                if activation.pubkey != pubkey:
                    msg = 'pubkey associated with activation code does not match pubkey provided by client.'
                    raise ApplicationError(Authenticator.ERROR_AUTH_INVALID_ACT_CODE,
                                           Authenticator.ERROR_AUTH_INVALID_ACT_CODE_MSG.format(msg))

                activation.status = ActivationStatus.ACTIVE
                activation.activated = now

                # create user
                if is_new_user:
                    user = User()
                    user.oid = uuid.uuid4()
                    user.email = authid
                    user.registered = datetime.utcnow()

                    with self._db.begin(write=True) as txn:
                        self._schema.users[txn, user.oid] = user

                    self.log.info('New user stored in database:\n{user}', user=user)
                else:
                    self.log.info('User already stored in database:\n{user}', user=user)

                # update user-pubkey activation
                with self._db.begin(write=True) as txn:
                    oid = self._schema.idx_act_tokens_by_authid_pubkey[txn, authid + pubkey]
                    if oid:
                        self._schema.activation_tokens[txn, oid] = activation
                    else:
                        raise Exception('no such activation')

                # immediately auth user on global users realm
                auth = {
                    'pubkey': pubkey,
                    'realm': Authenticator.GLOBAL_USER_REALM,
                    'authid': authid,
                    'role': Authenticator.GLOBAL_USER_REALM_USER_ROLE,
                    'extra': None,
                    'cache': False
                }

                self.log.info('found principal for public key {pubkey} of {authid}',
                              pubkey=pubkey,
                              authid=auth['authid'])

                return auth

            else:
                raise Exception('internal error: unprocessed activation status {}'.format(activation.status))

    def _send_user_login_mail(self, receiver, activation_code):
        subject = 'Crossbar.io: your LOGIN code'
        text = 'We have received a login request for your account. Please use this activation code: {}'.format(
            activation_code)
        return self._messenger.send_message(receiver, subject, text)

    def _send_user_registration_mail(self, receiver, activation_code):
        subject = 'Crossbar.io: your REGISTRATION code'
        text = 'We have received a registration request for your account. Please use this activation code: {}'.format(
            activation_code)
        return self._messenger.send_message(receiver, subject, text)
