###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import re
import six
import uuid
from datetime import datetime

from autobahn import wamp
from autobahn.util import utcnow, utcstr
from autobahn.wamp.types import PublishOptions, CallDetails
from autobahn.wamp.exception import ApplicationError

from crossbar.master.node.authenticator import Authenticator

from cfxdb.mrealm import ManagementRealm, Node
from cfxdb.user import UserRole, UserMrealmRole

# users cannot use realm names starting with these:
_PROTECTED_REALM_PREFIXES = [
    'io.crossbar',
    'com.crossbario',
    'de.crossbario',
    'crossbar',
    'crossbar-wamp',
    'crossbarfabric',
    'crossbarfabric-wamp',
    'crossbarfabriccenter',
    'crossbario',
    'fabric',
    'autobahn',
    'wamp',
    'ws.wamp',
    'io.wamp',
]

ERROR_INVALID_REALM = 'fabric.invalid-realm'
ERROR_REALM_ALREADY_EXISTS = 'fabric.realm-already-exists'
ERROR_NO_SUCH_REALM = 'fabric.no-such-realm'
ERROR_NOT_AUTHORIZED = 'fabric.not-authorized'
ERROR_NODE_ALREADY_PAIRED = 'fabric.node-already-paired'
ERROR_NODE_NOT_PAIRED = 'fabric.node-not-paired'
ERROR_NO_SUCH_NODE = 'fabric.node-not-exist'

_REALM_NAME_PAT_STR = r"^[A-Za-z][A-Za-z0-9_\-@\.]{2,254}$"
_REALM_NAME_PAT = re.compile(_REALM_NAME_PAT_STR)

ON_REALM_ASSIGNED = 'crossbarfabriccenter.mrealm.on_realm_created'


def _check_realm_name(name):
    """
    Check a realm name.

    Valid (management) realm names in Crossbar.io should be
    a strict subset of what is allowed in Crossbar.io (Community).

    Hence, the following code needs to be in line with the code in

        crossbar.common.checkconfig.check_realm_name
    """
    if not isinstance(name, six.text_type):
        msg = 'invalid realm name "{}" - type must be string, was {}'.format(name, type(name))
        raise ApplicationError(ERROR_INVALID_REALM, msg)
    if not _REALM_NAME_PAT.match(name):
        msg = 'invalid realm name "{}" - must match regular expression {}'.format(name, _REALM_NAME_PAT_STR)
        raise ApplicationError(ERROR_INVALID_REALM, msg)
    for prefix in _PROTECTED_REALM_PREFIXES:
        if name.startswith(prefix):
            msg = 'invalid realm name "{}": names starting with "{}" are protected'.format(name, prefix)
            raise ApplicationError(ERROR_INVALID_REALM, msg)


def _rtype(realm_type):
    if realm_type == 'realm':
        return ManagementRealm.RTYPE_MREALM
    elif realm_type == 'app':
        return ManagementRealm.RTYPE_APP
    else:
        raise ValueError('invalid realm_type "{}"'.format(realm_type))


class MrealmManager(object):
    """
    Management Realms API (domain-global).

    Prefix: ``crossbarfabriccenter.mrealm.``
    """
    def __init__(self, session, db, schema):
        """

        :param session: crossbar.master.node.controller.DomainController
        :param db:
        :param schema:
        """
        self.log = session.log
        self.db = db
        self.schema = schema

        # DomainController._domain_mgr
        # DomainController._user_mgr
        # DomainController._mrealm_mgr
        self._session = session

    def register(self, session, prefix, options):
        return session.register(self, prefix=prefix, options=options)

    @wamp.register(None)
    def list_mrealms(self, return_names=None, details=None):
        """
        List the management realms accessible for the calling user. A mrealm is accessible for a user
        when at least one role was granted.

        :procedure: ``crossbarfabriccenter.mrealm.list_mrealms``

        Here is an example:

        .. code-block:: python

            async def test_list_mrealms(session):
                oids = await session.call('crossbarfabriccenter.mrealm.list_mrealms')
                print('got realms:', oids)
                return oids

        :param return_names: Return realm names instead of  object IDs
        :type return_names: bool

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of OIDs (or names) of management realms
        :rtype: list[str]
        """
        assert return_names is None or type(return_names) == bool
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.list_mrealms(return_names={return_names}, details={details})',
                      klass=self.__class__.__name__,
                      return_names=return_names,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        if return_names:
            with self.db.begin() as txn:
                realms = self.schema.mrealms.select(txn, return_keys=False, return_values=True)
                res = sorted([realm.name for realm in realms])
        else:
            with self.db.begin() as txn:
                realm_oids = self.schema.mrealms.select(txn, return_keys=True, return_values=False)
                res = [str(realm_oid) for realm_oid in realm_oids]
        return res

    @wamp.register(None)
    def get_mrealm_by_name(self, mrealm_name, details=None):
        """

        :param mrealm_name:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        assert type(mrealm_name) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.get_mrealm_by_name(mrealm_oid={mrealm_name}, details={details})',
                      mrealm_name=mrealm_name,
                      klass=self.__class__.__name__,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        with self.db.begin() as txn:

            mrealm_oid = self.schema.idx_mrealms_by_name[txn, mrealm_name]
            if mrealm_oid:
                mrealm = self.schema.mrealms[txn, mrealm_oid]
                self.log.info('Management realm loaded:\n{mrealm}', mrealm=mrealm)
                return mrealm.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no management realm with name {}'.format(mrealm_name))

    @wamp.register(None)
    def get_mrealm(self, mrealm_oid, details=None):
        """
        Return the management realm definition by object OID. When no such object exists,
        an error will be returned.

        :procedure: ``crossbarfabriccenter.mrealm.get_mrealm``
        :error: ``crossbar.error.no_such_object``

        Here is a typical example, fetching all management realms:

        .. code-block:: python

            async def test_get_all_mrealms(session):
                oids = await session.call('crossbarfabriccenter.mrealm.list_mrealms')
                mrealms = []
                if oids:
                    for oid in oids:
                        mrealm = await session.call('crossbarfabriccenter.mrealm.get_mrealm', oid)
                        print('got realm {}: {}'.format(mrealm.oid, mrealm))
                        mrealms.append(mrealm)
                return mrealms

        :param mrealm_oid: OID of the management realm to get
        :type mrealm_oid: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: The management realm (marshaled instance)
        :rtype: :class:`cfxdb.mrealm.ManagementRealm`
        """
        assert type(mrealm_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.get_realm(mrealm_oid={mrealm_oid}, details={details})',
                      mrealm_oid=mrealm_oid,
                      klass=self.__class__.__name__,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        mrealm_oid = uuid.UUID(mrealm_oid)

        with self.db.begin() as txn:

            mrealm = self.schema.mrealms[txn, mrealm_oid]
            if mrealm:
                self.log.debug('Management realm loaded:\n{mrealm}', mrealm=mrealm)
                return mrealm.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no management realm with oid {}'.format(mrealm_oid))

    @wamp.register(None)
    async def create_mrealm(self, mrealm, details=None):
        """
        Create a new management realm from the creation object provided with
        partially present attributes (non-empty values).

        Create attribute ``name`` must be given, and ``label``, ``description`` and ``tags`` may be
        optionally set. The name must be unique within the domain and only consist of lower case
        latin letters, digits and the ``_`` character (and begin with a letter). You can use the ``label``,
        ``description`` and ``tags`` attributes for arbitrary text.

        .. note::
            A management realm is internally identified by an OID (a 128 bit UUID) which never changes,
            but the management *name* can be changed later (though this is considered an invasive action).
            You can use the ``label``, ``description`` and ``tags`` attributes for arbitrary text.

        Here is an example to create a new management realm:

        .. code-block:: python

            import random

            async def test_create_mrealm(session):
                name = 'my_mrealm_{}'.format(random.randint(0, 1000))
                obj = {'name', name}
                mrealm = await session.call('crossbarfabriccenter.mrealm.create_mrealm', obj)
                print('new mrealm {} created: {}'.format(mrealm['oid'], mrealm))
                return mrealm

        Keep in mind that a management realm ``name`` must be unique in the whole CFC domain!

        WAMP:

        :procedure: ``crossbarfabriccenter.mrealm.create_mrealm``
        :event: ``crossbarfabriccenter.mrealm.on_mrealm_created``
        :error: ``crossbar.error.already_exists``
        :error: ``crossbar.error.invalid_configuration``

        Signature:

        :param mrealm: Creation object for management realm.
        :type mrealm: dict marshaled from :class:`cfxdb.mrealm.ManagementRealm`

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Newly created management realm, including OID generated.
        :rtype: dict marshaled from :class:`cfxdb.mrealm.ManagementRealm`
        """
        assert type(mrealm) == dict
        assert details is None or isinstance(details, CallDetails)

        arg_mrealm = ManagementRealm.parse(mrealm)
        new_mrealm = None

        self.log.info('{klass}.create_realm(name={name}, details={details})',
                      name=arg_mrealm.name,
                      klass=self.__class__.__name__,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        # check for valid mrealm name
        _check_realm_name(arg_mrealm.name)

        with self.db.begin(write=True) as txn:
            # get calling user
            user_oid = self.schema.idx_users_by_email[txn, details.caller_authid]
            if not user_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no user with authid "{}" exists'.format(details.caller_authid))

            mrealm_oid = self.schema.idx_mrealms_by_name[txn, arg_mrealm.name]
            if mrealm_oid:
                raise ApplicationError('crossbar.error.already_exists',
                                       'management realm with name "{}" already exists'.format(arg_mrealm.name))

            new_mrealm = ManagementRealm()
            new_mrealm.oid = uuid.uuid4()
            new_mrealm.label = arg_mrealm.label
            new_mrealm.description = arg_mrealm.description
            new_mrealm.tags = arg_mrealm.tags
            new_mrealm.name = arg_mrealm.name
            new_mrealm.created = datetime.utcnow()
            new_mrealm.owner = user_oid
            new_mrealm.cf_router = 'cfrouter1'
            new_mrealm.cf_container = 'cfcontainer1'  # FIXME: dynamic placement of mrealm

            # store new management realm
            self.schema.mrealms[txn, new_mrealm.oid] = new_mrealm

            # store roles for user that created the management realm
            roles = UserMrealmRole([UserRole.OWNER, UserRole.ADMIN, UserRole.USER, UserRole.GUEST])
            self.schema.users_mrealm_roles[txn, (user_oid, new_mrealm.oid)] = roles

        self.log.debug('Management realm stored:\n{mrealm}', mrealm=new_mrealm)

        mrealm_obj = new_mrealm.marshal()

        started = await self._session.config.controller.call('crossbar.activate_realm', mrealm_obj)
        self.log.info('Management realm started: \n{started}', started=started)

        await self._session.publish('crossbarfabriccenter.mrealm.on_mrealm_created',
                                    mrealm_obj,
                                    options=PublishOptions(acknowledge=True))

        self.log.debug('Management API event <on_realm_created> published:\n{mrealm_obj}', mrealm_obj=mrealm_obj)

        return mrealm_obj

    @wamp.register(None)
    def modify_mrealm(self, mrealm_oid, mrealm_diff, details=None):
        """
        Modify an existing management realm from the modification object provided with
        partially present attributes (non-empty values).

        Change attributes can include ``name``, ``label``, ``description`` and ``tags``.

        :procedure: ``crossbarfabriccenter.mrealm.modify_mrealm``
        :event: ``crossbarfabriccenter.mrealm.on_mrealm_modified``
        :error: ``crossbar.error.no_such_object``

        :param mrealm_oid: OID of management realm to modify.
        :type mrealm_oid: str

        :param mrealm_diff: modification object with partially present, changed attributes (OID of the object itself
            cannot be changed)
        :type mrealm_diff: marshaled instance of :class:`cfxdb.mrealm.ManagementRealm`

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: modification object with effectively changed attributes and values
        :rtype: marshaled instance of :class:`cfxdb.mrealm.ManagementRealm`
        """
        assert details is None or isinstance(details, CallDetails)

        raise NotImplementedError()

    @wamp.register(None)
    async def delete_mrealm(self, mrealm_oid, cascade=False, details=None):
        """
        Delete a management realm. A management realm can only be deleted by the owner of the mrealm,
        and no object (such as paired nodes or assigned users) must relate to the mrealm anymore.

        :procedure: ``crossbarfabriccenter.mrealm.delete_mrealm``
        :event: ``crossbarfabriccenter.mrealm.on_mrealm_delete``
        :error: ``crossbar.error.no_such_object``

        Here is an example of deleting a management realm:

        .. code-block:: python

            async def test_delete_mrealm(session, mrealm):
                await session.call('crossbarfabriccenter.mrealm.delete_mrealm', mrealm.oid)

        Here is an example listening for management realm deleted events:

        .. code-block:: python

            async def test_on_mrealm_deleted(session):

                def on_delete(deleted):
                    print('mrealm {} deleted'.format(deleted.oid)

                await session.subscribe(on_delete, 'crossbarfabriccenter.mrealm.on_mrealm_deleted')
                print('listening to on_mrealm_deleted ..')

        :param mrealm_oid: OID of the management realm to be deleted.
        :type mrealm_oid: str

        :param cascade: Automatically unpair (but not delete) any nodes currently paired with and
            unassign (but not delete) any users currently assigned to the management realm to be deleted.
        :type cascade: bool

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: deleted object
        :rtype: marshaled instance of :class:`cfxdb.mrealm.ManagementRealm`
        """
        self.log.info('{klass}.delete_realm(mrealm_oid={mrealm_oid}, details={details})',
                      klass=self.__class__.__name__,
                      mrealm_oid=mrealm_oid,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        if isinstance(mrealm_oid, str):
            mrealm_oid = uuid.UUID(mrealm_oid)

        with self.db.begin() as txn:
            mrealm = self.schema.mrealms[txn, mrealm_oid]
            if not mrealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no management realm with ID "{}"'.format(mrealm_oid))

            # FIXME: check access to mrealm given resource-level access control system
            # FIXME: complete cascade delete:
            paired_nodes = []
            for node_id in self.schema.idx_nodes_by_authid.select(txn,
                                                                  from_key=(mrealm_oid, ''),
                                                                  to_key=(uuid.UUID(int=mrealm_oid.int + 1), ''),
                                                                  return_keys=False):

                if not cascade:
                    raise ApplicationError(
                        'crossbar.error.dependent_objects',
                        'cannot delete management - dependent object exists and cascade not set: paired node {}'.
                        format(node_id))
                paired_nodes.append(node_id)

        # cascade delete: unpair any nodes currently paired with the mrealm being deleted
        unpaired_nodes = []
        if cascade:
            for node_id in paired_nodes:
                unpaired_node = await self.unpair_node(str(node_id), details=details)
                unpaired_nodes.append(unpaired_node)
        else:
            assert not paired_nodes

        await self._session.config.controller.call('crossbar.deactivate_realm', mrealm.marshal())

        with self.db.begin(write=True) as txn:
            del self.schema.mrealms[txn, mrealm_oid]

        deleted = {
            'oid': str(mrealm_oid),
            'name': mrealm.name,
            'created': utcstr(mrealm.created),
            'deleted': utcnow(),
            'owner': str(mrealm.owner),
            'caller': details.caller_authid,
            'unpaired': [node['oid'] for node in unpaired_nodes],
        }

        await self._session.publish('crossbarfabriccenter.mrealm.on_realm_deleted',
                                    deleted,
                                    options=PublishOptions(acknowledge=True))

        return deleted

    @wamp.register(None)
    async def delete_mrealm_by_name(self, mrealm_name, cascade=False, details=None):
        """
        Delete an existing management realm (by name).

        :param mrealm_name: Name of the management realm to be deleted.
        :type mrealm_name: str

        :param cascade: Automatically unpair (but not delete) any nodes currently paired with and
            unassign (but not delete) any users currently assigned to the management realm to be deleted.
        :type cascade: bool

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        self.log.info('{klass}.delete_mrealm_by_name(mrealm_name={mrealm_name}, cascade={cascade}, details={details})',
                      klass=self.__class__.__name__,
                      mrealm_name=mrealm_name,
                      cascade=cascade,
                      details=details)

        with self.db.begin() as txn:
            mrealm_oid = self.schema.idx_mrealms_by_name[txn, mrealm_name]

        if mrealm_oid:
            deleted = await self.delete_mrealm(mrealm_oid, cascade=cascade, details=details)
            return deleted
        else:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no management realm with name "{}"'.format(mrealm_name))

    @wamp.register(None)
    def set_roles_on_mrealm_for_user(self, mrealm_oid, user_oid, user_roles, details=None):
        """
        Set (user) roles on management realm for user. Only the owner of a management realm
        is allowed to set the roles of a user on that management realm.

        :procedure: ``crossbarfabriccenter.mrealm.set_roles_on_mrealm_for_user``

        :param mrealm_oid: OID of management realm on which to grant roles on.
        :type mrealm_oid: str

        :param user_oid: OID of user to which to grant roles to.
        :type user_oid: str

        :param roles: List of roles which to grant, from ``owner``, ``admin``, ``user``, ``guest``.
            The list of roles supplied supplied replaces any existing list of assigned roles.
            Supplying an empty list of roles (or ``None``) revokes any permissions and access for the user.
        :type roles: list[str]

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def list_nodes(self, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.list_nodes``

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def list_nodes_by_mrealm(self, mrealm_id, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.list_nodes_by_mrealm``

        :param mrealm_id:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def list_nodes_by_mrealm_name(self, mrealm_name, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.list_nodes_by_mrealm_name``

        :param mrealm_name:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def get_node(self, node_id, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.list_nodes_by_mrealm``

        :param node_id:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def modify_node(self, node_id, node_delta, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.list_nodes_by_mrealm``

        :param node_id:
        :param node_delta:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def delete_node(self, node_id, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.delete_node``

        :param node_id:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def stat_node(self, node_id, details=None):
        """

        :procedure: ``crossbarfabriccenter.mrealm.stat_node``

        :param node_id:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def get_node_by_name(self, mrealm_name, node_name, details=None):
        """

        :param mrealm_name:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        assert type(mrealm_name) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.get_mrealm_by_name(mrealm_oid={mrealm_name}, details={details})',
                      mrealm_name=mrealm_name,
                      klass=self.__class__.__name__,
                      details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        with self.db.begin() as txn:

            mrealm_oid = self.schema.idx_mrealms_by_name[txn, mrealm_name]
            if not mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no management realm with name {}'.format(mrealm_name))

            node_oid = self.schema.idx_nodes_by_name[txn, (mrealm_oid, node_name)]
            if not node_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node named {} in management realm {}'.format(node_name, mrealm_name))

            node = self.schema.nodes[node_oid]
            if node.mrealm_oid != mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node named {} in management realm {}'.format(node_name, mrealm_name))

        return node.marshal()

    @wamp.register(None)
    async def pair_node(self, pubkey, realm_name, authid, authextra=None, details=None):
        """
        Pair a user Crossbar.io node with a user management realm.

        :procedure: ``crossbarfabriccenter.mrealm.pair_node``

        :param pubkey: The public key of the node to pair (HEX encoded).
        :type pubkey: str

        :param realm_name: The realm to which to pair the node to.
        :type realm_name: str

        :param node_id: The ID for the node to pair the node as.
        :type node_id: str

        :param authextra: Optional extra information handed out to the node
            when the node authenticates at CFC.
        :type authextra: None or dict

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Node paired information.
        :rtype: dict
        """
        self.log.info(
            '{klass}.pair_node(pubkey={pubkey}, realm_name={realm_name}, authid={authid}, authextra={authextra}, details={details})',
            pubkey=pubkey,
            realm_name=realm_name,
            authid=authid,
            authextra=authextra,
            klass=self.__class__.__name__,
            details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        node = None

        with self.db.begin(write=True) as txn:
            # get calling user
            user_oid = self.schema.idx_users_by_email[txn, details.caller_authid]
            if not user_oid:
                raise Exception('no such user')

            # check that the mrealm exists
            mrealm_oid = self.schema.idx_mrealms_by_name[txn, realm_name]
            mrealm = self.schema.mrealms[txn, mrealm_oid]
            if not mrealm_oid or not mrealm:
                msg = 'no realm named "{}" exists'.format(realm_name)
                raise ApplicationError(ERROR_NO_SUCH_REALM, msg)

            # owner of the mrealm
            owner = self.schema.users[txn, mrealm.owner]

            # check authorization of the calling user
            roles = self.schema.users_mrealm_roles[txn, (user_oid, mrealm_oid)]

            if not roles:
                msg = '"{}" not authorized to pair nodes to mrealm "{}" owned by {} (no roles assigned on mrealm)'.format(
                    details.caller_authid, realm_name, owner.email)
                raise ApplicationError(ERROR_NOT_AUTHORIZED, msg)

            # FIXME: allow UserRole.SUPERUSER (depends on: https://github.com/crossbario/cfxdb/issues/52)
            elif UserRole.OWNER not in roles.roles:
                msg = '"{}" not authorized to pair nodes to mrealm "{}" owned by {} (roles assigned on mrealm: {})'.format(
                    details.caller_authid, realm_name, owner.email, roles.roles)
                raise ApplicationError(ERROR_NOT_AUTHORIZED, msg)

            node_oid = self.schema.idx_nodes_by_pubkey[txn, pubkey]
            if not node_oid:
                self.log.info('Node pubkey not found, creating new node database object ..')
                node = Node()
                node.oid = uuid.uuid4()
                node.pubkey = pubkey
            else:
                self.log.info('Node pubkey found in database and loaded')
                node = self.schema.nodes[txn, node_oid]
                if node.mrealm_oid:
                    msg = 'node with given pubkey is already paired to a realm'
                    raise ApplicationError(ERROR_NODE_ALREADY_PAIRED, msg)

            node.owner_oid = user_oid
            node.mrealm_oid = mrealm_oid
            node.authid = authid
            node.authextra = authextra

            self.schema.nodes[txn, node.oid] = node

        assert node

        node_obj = node.marshal()

        topic = 'crossbarfabriccenter.mrealm.on_node_paired'
        self.log.debug('Publishing to <{topic}>: {payload} ..', topic=topic, payload=node_obj)
        await self._session.publish(topic, node_obj, options=PublishOptions(acknowledge=True))

        return node_obj

    @wamp.register(None)
    async def unpair_node(self, node_oid, details=None):
        """
        Unpair a user Crossbar.io node from a user management realm.

        :param node_oid:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        self.log.debug('{klass}.unpair_node(node_oid={node_oid}, details={details}) ..',
                       klass=self.__class__.__name__,
                       node_oid=node_oid,
                       details=details)

        if details.caller_authrole != Authenticator.GLOBAL_USER_REALM_USER_ROLE:
            raise Exception('proc not implemented for caller role "{}"'.format(details.caller_authrole))

        node = None
        node_oid = uuid.UUID(node_oid)
        mrealm = None

        with self.db.begin(write=True) as txn:
            # get calling user
            user_oid = self.schema.idx_users_by_email[txn, details.caller_authid]
            if not user_oid:
                raise Exception('no such user')

            node = self.schema.nodes[txn, node_oid]
            if not node:
                raise ApplicationError('crossbar.error.no_such_object', 'no node with oid {}'.format(node_oid))

            # FIXME
            # if node.owner_oid != details.caller_authid:
            #    raise Exception('not authorized')

            if not node.mrealm_oid:
                raise ApplicationError(ERROR_NODE_NOT_PAIRED,
                                       'cannot unpair node: node with id {} is currently not paired'.format(node_oid))

            mrealm = self.schema.mrealms[txn, node.mrealm_oid]
            assert mrealm

            node.mrealm_oid = None
            node.authid = None
            node.authextra = None

            self.schema.nodes[txn, node_oid] = node

        assert node

        # kill any management uplink sessions from the unpaired node
        #
        killed = None
        try:
            controller_session = self._session.config.controller

            # FIXME: hard-coded "cfrouter1" worker ID
            controller_proc = 'crossbar.worker.cfrouter1.kill_by_authid'

            killed = await controller_session.call(
                controller_proc,
                str(mrealm.name),
                str(node_oid),
                reason='wamp.close.auth-changed',
                message=
                'Authentication information or permissions changed for node with authid "{}" - killing all currently active sessions for this authid'
                .format(node_oid))
        except:
            self.log.failure()

        node_obj = node.marshal()
        node_obj['mrealm_oid'] = str(mrealm.oid)
        node_obj['killed'] = killed

        topic = 'crossbarfabriccenter.mrealm.on_node_unpaired'
        self.log.debug('Publishing to <{topic}>: {payload} ..', topic=topic, payload=node_obj)
        await self._session.publish(topic, node_obj, options=PublishOptions(acknowledge=True))

        if killed:
            self.log.info('{klass}.unpair_node(node_oid={node_oid}): unpaired (killed {killed} active sessions).',
                          klass=self.__class__.__name__,
                          node_oid=node_oid,
                          killed=len(killed))
        else:
            self.log.info('{klass}.unpair_node(node_oid={node_oid}): unpaired (no active sessions).',
                          klass=self.__class__.__name__,
                          node_oid=node_oid)

        return node_obj

    @wamp.register(None)
    async def unpair_node_by_pubkey(self, pubkey, details=None):
        """

        :param pubkey:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        self.log.info('{klass}.unpair_node_by_pubkey(pubkey={pubkey}, details={details})',
                      klass=self.__class__.__name__,
                      pubkey=pubkey,
                      details=details)

        with self.db.begin() as txn:
            node_oid = self.schema.idx_nodes_by_pubkey[txn, pubkey]
        if node_oid:
            unpaired = await self.unpair_node(str(node_oid), details=details)
            return unpaired
        else:
            raise ApplicationError('crossbar.error.no_such_object', 'no node with pubkey {}'.format(pubkey))

    @wamp.register(None)
    async def unpair_node_by_name(self, realm_name, authid, details=None):
        """

        :param realm_name:
        :param authid:

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        self.log.info('{klass}.unpair_node_by_name(realm_name={realm_name}, authid={authid}, details={details})',
                      klass=self.__class__.__name__,
                      realm_name=realm_name,
                      authid=authid,
                      details=details)

        raise NotImplementedError()
