###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import uuid

from autobahn import wamp
from autobahn.wamp.types import CallDetails, PublishOptions
from autobahn.wamp.exception import ApplicationError

from cfxdb.user import Organization


class UserManager(object):
    """
    User management API (domain-global).

    Prefix: ``crossbarfabriccenter.user.``
    """

    _PUBOPTS = PublishOptions(acknowledge=True)

    def __init__(self, session, db, schema):
        self._session = session
        self.log = session.log
        self.db = db
        self.schema = schema
        self._prefix = None

    def register(self, session, prefix, options):
        self._prefix = prefix
        return session.register(self, prefix=prefix, options=options)

    @wamp.register(None)
    def list_organizations(self, details=None):
        """
        List all organizations accessible for the calling user. An organization
        is accessible for a user when at least one role was granted.

        :procedure: ``crossbarfabriccenter.user.list_organizations``

        Here is an example:

        .. code-block:: python

            async def test_list_organizations(session):
                oids = await session.call('crossbarfabriccenter.organization.list_organizations')
                print('got organizations:', oids)
                return oids

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of OIDs of management realms
        :rtype: list[str]
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.list_organizations(details={details})', klass=self.__class__.__name__, details=details)

        with self.db.begin() as txn:
            org_oids = self.schema.organizations.select(txn, return_keys=True, return_values=False)
            if org_oids:
                # we now have a list of uuid.UUID objects: convert to strings
                return [str(oid) for oid in org_oids]
            else:
                return []

    @wamp.register(None)
    def get_organization(self, org_oid, details=None):
        """
        Return the organization definition by object OID. When no such object exists,
        an error will be returned.

        :procedure: ``crossbarfabriccenter.user.get_organization``
        :error: ``crossbar.error.no_such_object``

        Here is a typical example, fetching all organization (accessible by the user):

        .. code-block:: python

            async def test_get_all_orgs(session):
                oids = await session.call('crossbarfabriccenter.user.get_organizations')
                orgs = []
                if oids:
                    for oid in oids:
                        org = await session.call('crossbarfabriccenter.user.get_organization', oid)
                        print('got organization {}: {}'.format(org.oid, org))
                        orgs.append(org)
                return orgs

        :param org_oid: OID of the organization to get
        :type org_oid: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: The organization database object (marshaled instance)
        :rtype: :class:`cfxdb.user.Organization`
        """
        assert type(org_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.get_organization(org_oid={org_oid}, details={details})',
                      org_oid=org_oid,
                      klass=self.__class__.__name__,
                      details=details)

        org_oid = uuid.UUID(org_oid)

        with self.db.begin() as txn:

            org = self.schema.organizations[txn, org_oid]
            if org:
                self.log.info('Organization loaded:\n{org}', org=org)
                return org.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no organization with oid {}'.format(org_oid))

    @wamp.register(None)
    async def create_organization(self, organization, details=None):
        """
        Create and store a new organization.

        :param organization:
        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(organization) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.create_organization(organization={organization}, details={details})',
                      klass=self.__class__.__name__,
                      organization=organization,
                      details=details)

        obj = Organization.parse(organization)
        obj.oid = uuid.uuid4()

        with self.db.begin(write=True) as txn:
            self.schema.organizations[txn, obj.oid] = obj

        self.log.info('new Organization object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}on_organization_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_organization_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None)
    async def modify_organization(self, org_oid, org_delta, details=None):
        """
        Modify an existing organization.

        :param org_oid:
        :param org_delta:
        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    async def delete_organization(self, org_oid, cascade=False, details=None):
        """
        Delete an organization.

        :param org_oid:
        :param cascade:
        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(org_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.delete_organization(details={details})', klass=self.__class__.__name__, details=details)

        try:
            oid = uuid.UUID(org_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            obj = self.schema.organizations[txn, oid]
            if obj:
                del self.schema.organizations[txn, oid]
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no object with oid {} found'.format(oid))

        self.log.info('Organization object deleted from database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}on_organization_deleted'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None)
    def get_user(self, user_id, details=None):
        """
        Get a particular user by OID.

        :param user_id: OID of the user object to retrieve.
        :type user_id: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(user_id) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.get_user(user_id={user_id}, details={details})',
                      user_id=user_id,
                      klass=self.__class__.__name__,
                      details=details)

        user_id = uuid.UUID(user_id)

        with self.db.begin() as txn:

            user = self.schema.users[txn, user_id]
            if user:
                return user.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no user with oid {}'.format(user_id))

    @wamp.register(None)
    def get_user_by_pubkey(self, pubkey, details=None):
        """
        Get a user by public key.

        :param pubkey: Public key of the user to retrieve.
        :type pubkey: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(pubkey) == str
        assert details is None or isinstance(details, CallDetails)

        with self.db.begin() as txn:
            user_id = self.schema.idx_users_by_pubkey[txn, pubkey]
            if user_id:
                user = self.schema.users[txn, user_id]
                assert user
                return user.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no user with pubkey {}'.format(pubkey))

    @wamp.register(None)
    def get_user_by_email(self, email, details=None):
        """

        :param email: Email (name) of the user to retrieve.

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(email) == str
        assert details is None or isinstance(details, CallDetails)

        with self.db.begin() as txn:
            user_id = self.schema.idx_users_by_email[txn, email]
            if user_id:
                user = self.schema.users[txn, user_id]
                assert user
                return user.marshal()
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no user with email "{}"'.format(email))

    @wamp.register(None)
    async def modify_user(self, user_id, user_delta, details=None):
        """
        Modify an existing user.

        :procedure: ``crossbarfabriccenter.user.modify_user``
        :event: ``crossbarfabriccenter.user.on_user_modified``
        :error: ``crossbar.error.no_such_object``

        :param user_id: The user object to modify.
        :type user_id: str

        :param user_delta: The modification object with attributes present for values to be modified.
        :type user_delta: marshaled instance of :class:`cfxdb.user.User`

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: A change object which with attributes and values present the reflect
            the actual modification that was made.
        :rtype: marshaled instance of :class:`cfxdb.user.User`
        """
        raise NotImplementedError()

    @wamp.register(None)
    def list_users(self, details=None):
        """
        List users.

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{klass}.list_users(details={details})', klass=self.__class__.__name__, details=details)

        with self.db.begin() as txn:
            users = [str(user_id) for user_id in self.schema.users.select(txn, return_values=False)]
            return users

    @wamp.register(None)
    async def list_users_by_organization(self, org_id, details=None):
        """
        List users with at least one role assigned on an organization.

        :param org_id: The organization to list users for.
        :type org_id: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    async def list_organizations_by_user(self, user_id, details=None):
        """
        List organizations with roles assigned for a given user.

        :param user_id: The user to list organizations for.
        :type user_id: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    async def set_roles_on_organization_for_user(self, org_id, user_id, roles, details=None):
        """
        Set roles for a user on an organization.

        :param org_id:
        :type org_id: str

        :param user_id:
        :type user_id: str

        :param roles:
        :type roles: list[str]

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        raise NotImplementedError()

    @wamp.register(None)
    async def get_roles_on_organization_for_user(self, org_id, user_id, details=None):
        """
        Get roles for a user on an organization.

        :param org_id:
        :type org_id: str

        :param user_id:
        :type user_id: str

        :param details: Call details
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Roles a user currently has on the organization.
        :rtype: list[str]
        """
        raise NotImplementedError()
