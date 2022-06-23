###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import copy
import uuid
from autobahn.util import rtime


class CmdRunResult(object):
    def __init__(self, result, duration=None):
        self.result = result
        self.duration = duration

    def __str__(self):
        return 'CmdRunResult(result={}, duration={})'.format(self.result, self.duration)


class Cmd(object):
    def __init__(self):
        self._started = None

    def _pre(self, session):
        if not session:
            raise Exception('not connected')
        self._started = rtime()

    def _post(self, session, result):
        duration = round(1000. * (rtime() - self._started), 1)
        self._started = None
        return CmdRunResult(result, duration)


class CmdGetDomainStatus(Cmd):
    """
    GLOBAL REALM or MREALM: get system status.
    """
    def __init__(self, realm=None):
        Cmd.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        if self.realm:
            result = await session.call('crossbarfabriccenter.mrealm.get_status')
        else:
            result = await session.call('crossbarfabriccenter.domain.get_status')
        return self._post(session, result)


class CmdGetDomainVersion(Cmd):
    """
    GLOBAL REALM: get domain controller software version.
    """
    def __init__(self, realm=None):
        Cmd.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.domain.get_version')
        return self._post(session, result)


class CmdGetDomainLicense(Cmd):
    """
    GLOBAL REALM: get domain software stack license.
    """
    def __init__(self, realm=None):
        Cmd.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.domain.get_license')
        return self._post(session, result)


class CmdPair(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdPairNode(CmdPair):
    """
    GLOBAL REALM: Pair a node to a management realm.
    """
    def __init__(self, realm, pubkey, node_id, authextra=None):
        CmdPair.__init__(self)
        self.realm = realm
        self.pubkey = pubkey
        self.node_id = node_id
        self.authextra = authextra

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.pair_node', self.pubkey, self.realm, self.node_id,
                                    self.authextra)
        return self._post(session, result)


class CmdUnpair(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdUnpairNode(CmdUnpair):
    """
    GLOBAL REALM: Unpair a node currently paired to a management realm.
    """
    def __init__(self, pubkey):
        CmdUnpair.__init__(self)
        self.pubkey = pubkey

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.unpair_node_by_pubkey', self.pubkey)
        return self._post(session, result)


class CmdAdd(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdAddRolePermission(CmdAdd):
    """
    MREALM: Add a permission to a role.
    """
    def __init__(self, role, uri, config):
        """

        :param role:
        :param uri:
        :param config:
        """
        CmdAdd.__init__(self)
        self.role = role
        self.uri = uri
        self.config = config

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
            role_oid = str(role_oid)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']

        result = await session.call('crossbarfabriccenter.mrealm.arealm.add_role_permission', role_oid, self.uri,
                                    self.config)

        return self._post(session, result)


class CmdAddPrincipal(CmdAdd):
    """
    MREALM: Add a principal to an application realm.
    """
    def __init__(self, arealm, principal, config=None):
        """

        :param arealm:
        :param principal:
        :param config:
        """
        CmdAdd.__init__(self)
        self.arealm = arealm
        self.config = config or {}
        self.config['authid'] = principal

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
            arealm_oid = str(arealm_oid)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']

        role = self.config.get('role', None)
        assert role is not None and type(role) == str

        try:
            role_oid = uuid.UUID(role)
            role_obj = await session.call('crossbarfabriccenter.mrealm.arealm.get_role', role_oid)
        except:
            role_obj = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', role)
            role_oid = role_obj['oid']

        config = copy.deepcopy(self.config)
        del config['role']
        config['role_oid'] = role_oid

        try:
            result = await session.call('crossbarfabriccenter.mrealm.arealm.add_principal', arealm_oid, config)
        except Exception as e:
            print(e)
            raise e

        return self._post(session, result)


class CmdAddPrincipalCredential(CmdAdd):
    """
    MREALM: Add a credential to a principal.
    """
    def __init__(self, arealm, principal, config=None):
        """

        :param arealm:
        :param principal:
        :param config:
        """
        CmdAdd.__init__(self)
        self.arealm = arealm
        self.principal = principal
        self.config = config or {}

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
            arealm_oid = str(arealm_oid)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']

        try:
            principal_oid = uuid.UUID(self.principal)
            principal_oid = str(principal_oid)
        except:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal_by_name', arealm_oid,
                                           self.principal)
            principal_oid = principal['oid']

        result = await session.call('crossbarfabriccenter.mrealm.arealm.add_principal_credential', arealm_oid,
                                    principal_oid, self.config)

        return self._post(session, result)


class CmdAddApplicationRealmRole(CmdAdd):
    """
    MREALM: Add a role to an application realm.
    """
    def __init__(self, arealm, role, config=None):
        """

        :param arealm:
        :param role:
        :param config:
        """
        CmdAdd.__init__(self)
        self.arealm = arealm
        self.role = role
        self.config = config

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
            arealm_oid = str(arealm_oid)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']

        try:
            role_oid = uuid.UUID(self.role)
            role_oid = str(role_oid)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']

        result = await session.call('crossbarfabriccenter.mrealm.arealm.add_arealm_role', arealm_oid, role_oid,
                                    self.config)

        return self._post(session, result)


class CmdAddRouterClusterWorkerGroup(CmdAdd):
    """
    MREALM: Add a workergroup to a routercluster.
    """
    def __init__(self, cluster, workergroup, config=None):
        """

        :param cluster: Router cluster name (or object ID).
        :param workergroup:  Workergroup name.
        :param config: Configuration of node cluster association.
        """
        CmdAdd.__init__(self)
        self.cluster = cluster
        self.workergroup = workergroup
        self.config = config

    async def run(self, session):
        self._pre(session)

        try:
            cluster_oid = uuid.UUID(self.cluster)
            cluster_oid = str(cluster_oid)
        except:
            routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                               self.cluster)
            cluster_oid = routercluster['oid']

        self.config['name'] = self.workergroup
        self.config['cluster_oid'] = cluster_oid

        workergroup = await session.call('crossbarfabriccenter.mrealm.routercluster.add_routercluster_workergroup',
                                         cluster_oid, self.config)
        # workergroup_oid = workergroup['oid']

        return self._post(session, workergroup)


class CmdAddRouterClusterNode(CmdAdd):
    """
    MREALM: Add a node to a routercluster.
    """
    def __init__(self, routercluster, node, config=None):
        """

        :param routercluster: Router cluster name or object ID.
        :param node:  Node name or object ID.
        :param config: Configuration of node cluster association.
        """
        CmdAdd.__init__(self)
        self.routercluster = routercluster
        self.node = node
        self.config = config

    async def run(self, session):
        self._pre(session)

        try:
            routercluster_oid = uuid.UUID(self.routercluster)
            routercluster_oid = str(routercluster_oid)
        except:
            routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                               self.routercluster)
            routercluster_oid = routercluster['oid']

        if self.node == 'all' or self.node is None:
            nodes = await session.call('crossbarfabriccenter.mrealm.get_nodes')
        else:
            nodes = [x.strip() for x in self.node.split(',')]

        result = []
        for _node in nodes:
            try:
                node_oid = uuid.UUID(_node)
                node_oid = str(node_oid)
            except:
                node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
                node_oid = node['oid']

            node_added = await session.call('crossbarfabriccenter.mrealm.routercluster.add_routercluster_node',
                                            routercluster_oid, node_oid, self.config)
            result.append(node_added)
        return self._post(session, result)


class CmdAddWebClusterNode(CmdAdd):
    """
    MREALM: Add a node to a webcluster.
    """
    def __init__(self, webcluster, node, config=None):
        """

        :param webcluster: Web cluster name or object ID.
        :param node:  Node name or object ID.
        :param config: Configuration of node cluster association.
        """
        CmdAdd.__init__(self)
        self.webcluster = webcluster
        self.node = node
        self.config = config

    async def run(self, session):
        self._pre(session)

        try:
            webcluster_oid = uuid.UUID(self.webcluster)
            webcluster_oid = str(webcluster_oid)
        except:
            webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                            self.webcluster)
            webcluster_oid = webcluster['oid']

        if self.node == 'all' or self.node is None:
            nodes = await session.call('crossbarfabriccenter.mrealm.get_nodes')
        else:
            nodes = [x.strip() for x in self.node.split(',')]

        result = []
        for _node in nodes:
            try:
                node_oid = uuid.UUID(_node)
                node_oid = str(node_oid)
            except:
                node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
                node_oid = node['oid']

            node_added = await session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_node',
                                            webcluster_oid, node_oid, self.config)
            result.append(node_added)
        return self._post(session, result)


class CmdAddWebClusterService(CmdAdd):
    """
    MREALM: Add a service to a webcluster.
    """
    def __init__(self, webcluster, path, config=None):
        CmdAdd.__init__(self)
        self.webcluster = webcluster
        self.path = path
        self.config = config

    async def run(self, session):
        self._pre(session)
        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)
        result = await session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_service', webcluster['oid'],
                                    self.path, self.config)
        return self._post(session, result)


class CmdCreate(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdCreateManagementRealm(CmdCreate):
    """
    GLOBAL REALM: Create a new management realm.
    """
    def __init__(self, realm):
        CmdCreate.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        mrealm = {'name': self.realm}
        result = await session.call('crossbarfabriccenter.mrealm.create_mrealm', mrealm)
        return self._post(session, result)


class CmdCreateApplicationRealm(CmdCreate):
    """
    MREALM REALM: Create a new application realm.
    """
    def __init__(self, realm):
        CmdCreate.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.arealm.create_arealm', self.realm)
        return self._post(session, result)


class CmdCreateRole(CmdCreate):
    """
    MREALM REALM: Create a new role (for use with application realms).
    """
    def __init__(self, role):
        CmdCreate.__init__(self)
        self.role = role

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.arealm.create_role', self.role)
        return self._post(session, result)


class CmdCreateRouterCluster(CmdCreate):
    """
    MREALM: Create a routercluster.
    """
    def __init__(self, routercluster):
        CmdCreate.__init__(self)
        self.routercluster = routercluster

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.routercluster.create_routercluster',
                                    self.routercluster)
        return self._post(session, result)


class CmdCreateWebCluster(CmdCreate):
    """
    MREALM: Create a webcluster.
    """
    def __init__(self, webcluster):
        CmdCreate.__init__(self)
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.webcluster.create_webcluster', self.webcluster)
        return self._post(session, result)


class CmdCreateWebService(CmdCreate):
    """
    MREALM: Create a webservice (within a webcluster).
    """
    def __init__(self, webcluster_oid, webservice):
        CmdCreate.__init__(self)
        self.webcluster_oid = webcluster_oid
        self.webservice = webservice

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_service',
                                    self.webcluster_oid, self.webservice)

        return self._post(session, result)


class CmdCreateDockerContainer(CmdCreate):
    """
    MREALM: Create a Docker container on a node.
    """
    def __init__(self, node, image, config):
        CmdCreate.__init__(self)
        self.node = node
        self.image = image
        self.config = config

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.create', node['oid'], self.image, self.config)
        return self._post(session, result)


class CmdRemove(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdRemoveRouterClusterNode(CmdRemove):
    def __init__(self, cluster, node):
        CmdRemove.__init__(self)
        self.cluster = cluster
        self.node = node

    async def run(self, session):
        self._pre(session)

        routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                           self.cluster)

        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)

        result = await session.call('crossbarfabriccenter.mrealm.routercluster.remove_routercluster_node',
                                    routercluster['oid'], node['oid'])

        return self._post(session, result)


class CmdRemoveRouterClusterWorkerGroup(CmdRemove):
    def __init__(self, cluster, workergroup):
        CmdRemove.__init__(self)
        self.cluster = cluster
        self.workergroup = workergroup

    async def run(self, session):
        self._pre(session)

        cluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                     self.cluster)

        workergroup = await session.call(
            'crossbarfabriccenter.mrealm.routercluster.get_routercluster_workergroup_by_name', self.cluster,
            self.workergroup)

        result = await session.call('crossbarfabriccenter.mrealm.routercluster.remove_routercluster_workergroup',
                                    cluster['oid'], workergroup['oid'])

        return self._post(session, result)


class CmdRemoveWebClusterService(CmdRemove):
    def __init__(self, webcluster, path):
        CmdRemove.__init__(self)
        self.webcluster = webcluster
        self.path = path

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        webservice = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_service_by_path',
                                        webcluster['oid'], self.path)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.remove_webcluster_service',
                                    webcluster['oid'], webservice['oid'])

        return self._post(session, result)


class CmdRemoveWebClusterNode(CmdRemove):
    def __init__(self, cluster, node):
        CmdRemove.__init__(self)
        self.cluster = cluster
        self.node = node

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name', self.cluster)

        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.remove_webcluster_node', webcluster['oid'],
                                    node['oid'])

        return self._post(session, result)


class CmdRemoveArealmPrincipal(CmdRemove):
    def __init__(self, arealm, principal):
        CmdRemove.__init__(self)
        self.arealm = arealm
        self.principal = principal

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            principal_oid = uuid.UUID(self.principal)
        except:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal_by_name', self.arealm)
            principal_oid = principal['oid']
        else:
            principal_oid = str(principal_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.remove_principal', arealm_oid, principal_oid)

        return self._post(session, result)


class CmdRemoveArealmPrincipalCredential(CmdRemove):
    def __init__(self, arealm, principal, credential):
        CmdRemove.__init__(self)
        self.arealm = arealm
        self.principal = principal
        self.credential = credential

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            principal_oid = uuid.UUID(self.principal)
        except:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal_by_name', self.arealm)
            principal_oid = principal['oid']
        else:
            principal_oid = str(principal_oid)

        credential_oid = uuid.UUID(self.credential)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.remove_principal_credential', arealm_oid,
                                    principal_oid, credential_oid)

        return self._post(session, result)


class CmdRemoveRolePermission(CmdRemove):
    def __init__(self, role, path):
        CmdRemove.__init__(self)
        self.role = role
        self.path = path

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        permission_oids = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_permissions_by_uri',
                                             role_oid, self.path)

        results = []
        for permission_oid in permission_oids:
            result = await session.call('crossbarfabriccenter.mrealm.arealm.remove_role_permission', role_oid,
                                        permission_oid)
            results.append(result)

        return self._post(session, result)


class CmdRemoveArealmRole(CmdRemove):
    def __init__(self, arealm, role):
        CmdRemove.__init__(self)
        self.arealm = arealm
        self.role = role

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.remove_arealm_role', arealm_oid, role_oid)

        return self._post(session, result)


class CmdDelete(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdDeleteManagementRealm(CmdDelete):
    def __init__(self, realm, cascade):
        CmdDelete.__init__(self)
        self.realm = realm
        self.cascade = cascade

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.delete_mrealm_by_name',
                                    self.realm,
                                    cascade=self.cascade)
        return self._post(session, result)


class CmdDeleteApplicationRealm(CmdDelete):
    def __init__(self, realm, cascade):
        CmdDelete.__init__(self)
        self.realm = realm
        self.cascade = cascade

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.realm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.realm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.delete_arealm', arealm_oid)
        return self._post(session, result)


class CmdDeleteRole(CmdDelete):
    def __init__(self, role):
        CmdDelete.__init__(self)
        self.role = role

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.delete_role', role_oid)
        return self._post(session, result)


class CmdDeleteRouterCluster(CmdDelete):
    """
    MREALM: delete routercluster by UUID.
    """
    def __init__(self, routercluster):
        CmdDelete.__init__(self)
        self.routercluster = routercluster

    async def run(self, session):
        self._pre(session)

        routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                           self.routercluster)

        result = await session.call('crossbarfabriccenter.mrealm.routercluster.delete_routercluster',
                                    routercluster['oid'])

        return self._post(session, result)


class CmdDeleteWebCluster(CmdDelete):
    """
    MREALM: delete webcluster by UUID.
    """
    def __init__(self, webcluster):
        CmdDelete.__init__(self)
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.delete_webcluster', webcluster['oid'])

        return self._post(session, result)


class CmdList(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdListManagementRealms(CmdList):
    """
    GLOBAL REALM: Get list of management realms.
    """
    def __init__(self, names=None):
        CmdList.__init__(self)
        self.names = names

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.list_mrealms', return_names=self.names)
        return self._post(session, result)


class CmdListNodes(CmdList):
    """
    GLOBAL REALM: Get list of nodes in management realms.
    """
    def __init__(self, online=None, offline=None, names=None):
        CmdList.__init__(self)
        self.online = online
        self.offline = offline
        self.names = names

    async def run(self, session):
        self._pre(session)
        status = None
        if self.online is not None or self.offline is not None:
            if self.online:
                status = 'online'
            elif self.offline:
                status = 'offline'
        result = await session.call('crossbarfabriccenter.mrealm.get_nodes', status, return_names=self.names)
        return self._post(session, result)


class CmdListWorkers(CmdList):
    """
    MREALM: Get list of workers on a node.
    """
    def __init__(self, node):
        CmdList.__init__(self)
        self.node = node

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.node.get_workers', node['oid'])
        return self._post(session, result)


class CmdListRouterRealms(CmdList):
    def __init__(self, node, worker):
        CmdList.__init__(self)
        self.node = node
        self.worker = worker

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.router.get_router_realms', self.node, self.worker)
        return self._post(session, result)


class CmdListRouterTransports(CmdList):
    def __init__(self, node, worker):
        CmdList.__init__(self)
        self.node = node
        self.worker = worker

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.router.get_router_transports', self.node, self.worker)
        return self._post(session, result)


class CmdListARealms(CmdList):
    """
    MREALM: Get list of application realms defined on a mrealm.
    """
    def __init__(self, names=False):
        CmdList.__init__(self)
        self.names = names

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_arealms', return_names=self.names)
        return self._post(session, result)


class CmdListARealmRoles(CmdList):
    """
    MREALM: Get list of roles associated with the given application realm defined on a mrealm.
    """
    def __init__(self, arealm, names=False):
        CmdList.__init__(self)
        self.arealm = arealm
        self.names = names

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_arealm_roles',
                                    arealm_oid,
                                    return_names=self.names)
        return self._post(session, result)


class CmdListRoles(CmdList):
    """
    MREALM: Get list of roles defined on a mrealm.
    """
    def __init__(self, names=False):
        CmdList.__init__(self)
        self.names = names

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_roles', return_names=self.names)
        return self._post(session, result)


class CmdListRolePermissions(CmdList):
    """
    MREALM: Get list of permissions defined for a role.
    """
    def __init__(self, role):
        CmdList.__init__(self)
        self.role = role

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_role_permissions', role_oid)
        return self._post(session, result)


class CmdListPrincipals(CmdList):
    """
    MREALM: Get list of principals defined on a mrealm.
    """
    def __init__(self, arealm, names=False):
        CmdList.__init__(self)
        self.arealm = arealm
        self.names = names

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_principals',
                                    arealm_oid,
                                    return_names=self.names)
        return self._post(session, result)


class CmdListPrincipalCredentials(CmdList):
    """
    MREALM: Get list of credentials of a principal.
    """
    def __init__(self, arealm, principal):
        CmdList.__init__(self)
        self.arealm = arealm
        self.principal = principal

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            principal_oid = uuid.UUID(self.principal)
        except:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal_by_name', arealm_oid,
                                           self.principal)
            principal_oid = principal['oid']
        else:
            principal_oid = str(principal_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.list_principal_credentials', arealm_oid,
                                    principal_oid)

        return self._post(session, result)


class CmdListRouterClusters(CmdList):
    """
    MREALM: Get list of webclusters defined on a mrealm.
    """
    def __init__(self, names=False):
        CmdList.__init__(self)
        self.names = names

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.routercluster.list_routerclusters',
                                    return_names=self.names)
        return self._post(session, result)


class CmdListRouterClusterNodes(CmdList):
    """
    MREALM: Get list of nodes associated with a routercluster.
    """
    def __init__(self, cluster, names=None, filter_status=None):
        CmdList.__init__(self)
        self.cluster = cluster
        self.names = names
        self.filter_status = filter_status

    async def run(self, session):
        self._pre(session)
        cluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                     self.cluster)
        result = await session.call('crossbarfabriccenter.mrealm.routercluster.list_routercluster_nodes',
                                    cluster['oid'],
                                    return_names=self.names,
                                    filter_by_status=self.filter_status)
        return self._post(session, result)


class CmdListRouterClusterWorkerGroups(CmdList):
    """
    MREALM: Get list of workergroups running in a routercluster.
    """
    def __init__(self, cluster, names=None, filter_status=None):
        CmdList.__init__(self)
        self.cluster = cluster
        self.names = names
        self.filter_status = filter_status

    async def run(self, session):
        self._pre(session)

        try:
            cluster_oid = str(uuid.UUID(self.cluster))
        except:
            cluster_obj = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                             self.cluster)
            cluster_oid = cluster_obj['oid']

        workergroups = await session.call('crossbarfabriccenter.mrealm.routercluster.list_routercluster_workergroups',
                                          cluster_oid,
                                          return_names=self.names,
                                          filter_by_status=self.filter_status)

        return self._post(session, workergroups)


class CmdListWebClusters(CmdList):
    """
    MREALM: Get list of webclusters defined on a mrealm.
    """
    def __init__(self, names=False):
        CmdList.__init__(self)
        self.names = names

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.mrealm.webcluster.list_webclusters', return_names=self.names)
        return self._post(session, result)


class CmdListWebClusterNodes(CmdList):
    """
    MREALM: Get list of nodes associated with a webcluster.
    """
    def __init__(self, cluster, names=None, filter_status=None):
        CmdList.__init__(self)
        self.cluster = cluster
        self.names = names
        self.filter_status = filter_status

    async def run(self, session):
        self._pre(session)
        cluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name', self.cluster)
        result = await session.call('crossbarfabriccenter.mrealm.webcluster.list_webcluster_nodes',
                                    cluster['oid'],
                                    return_names=self.names,
                                    filter_by_status=self.filter_status)
        return self._post(session, result)


class CmdListWebClusterWebService(CmdList):
    """
    MREALM: Get list of webcluster-webservices defined on a webcluster.
    """
    def __init__(self, webcluster):
        CmdList.__init__(self)
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.list_webcluster_services',
                                    webcluster['oid'])
        return self._post(session, result)


class CmdListDockerImages(CmdList):
    """
    MREALM: Get list of Docker images available on a node.
    """
    def __init__(self, node):
        CmdList.__init__(self)
        self.node = node

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.get_images', node['oid'])
        return self._post(session, result)


class CmdListDockerContainers(CmdList):
    """
    MREALM: Get list of Docker containers on a node.
    """
    def __init__(self, node):
        CmdList.__init__(self)
        self.node = node

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.get_containers', node['oid'])
        return self._post(session, result)


class CmdShow(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdShowFabric(CmdShow):
    def __init__(self):
        CmdShow.__init__(self)

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.show_fabric')
        return self._post(session, result)


class CmdShowManagementRealm(CmdShow):
    def __init__(self, realm):
        CmdShow.__init__(self)
        self.realm = realm

    async def run(self, session):
        self._pre(session)

        list_all = False
        if self.realm == 'all' or self.realm is None:
            mrealms = await session.call('crossbarfabriccenter.mrealm.list_mrealms')
        else:
            mrealms = [x.strip() for x in self.realm.split(',')]

        result = []
        for mrealm in mrealms:
            try:
                mrealm_oid = uuid.UUID(mrealm)
            except:
                mrealm_obj = await session.call('crossbarfabriccenter.mrealm.get_mrealm_by_name', mrealm)
            else:
                mrealm_obj = await session.call('crossbarfabriccenter.mrealm.get_mrealm', str(mrealm_oid))
            result.append(mrealm_obj)

        if list_all:
            return self._post(session, result)
        else:
            return self._post(session, result[0])


class CmdShowNode(CmdShow):
    def __init__(self, node=None):
        """
        Get node metadata object.

        :param node: Node ID (a UUID string) or node name or `None`
            to get metadata for all nodes (paired) in the management realm.
        :type node: str

        :returns: List of node metadata objects.
        :rtype: list
        """
        CmdShow.__init__(self)
        self.node = node

    async def run(self, session):
        self._pre(session)

        list_all = False
        if self.node == 'all' or self.node is None:
            nodes = await session.call('crossbarfabriccenter.mrealm.get_nodes')
        else:
            nodes = [x.strip() for x in self.node.split(',')]

        result = []
        for node in nodes:
            try:
                node_oid = uuid.UUID(node)
            except:
                node_obj = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', node)
            else:
                node_obj = await session.call('crossbarfabriccenter.mrealm.get_node', str(node_oid))
            result.append(node_obj)

        if list_all:
            return self._post(session, result)
        else:
            return self._post(session, result[0])


class CmdShowDockerImage(CmdShow):
    def __init__(self, node, image):
        CmdShow.__init__(self)
        self.node = node
        self.image = image

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.get_image', node['oid'], self.image)
        return self._post(session, result)


class CmdShowDockerContainer(CmdShow):
    def __init__(self, node, container):
        CmdShow.__init__(self)
        self.node = node
        self.container = container

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.get_container', node['oid'], self.container)
        return self._post(session, result)


class CmdShowDocker(CmdShow):
    def __init__(self, node, status=True):
        CmdShow.__init__(self)
        self.node = node
        self.status = status

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)

        info = await session.call('crossbarfabriccenter.remote.docker.get_info', node['oid'])
        version = await session.call('crossbarfabriccenter.remote.docker.get_version', node['oid'])

        result = {
            'info': info,
            'version': version,
        }
        if self.status:
            result_ping = await session.call('crossbarfabriccenter.remote.docker.get_ping', node['oid'])
            result_df = await session.call('crossbarfabriccenter.remote.docker.get_df', node['oid'])
            result['status'] = {
                'ping': result_ping,
                'df': result_df,
            }
        return self._post(session, result)


class CmdShowWorker(CmdShow):
    def __init__(self, node, worker):
        CmdShow.__init__(self)
        self.node = node
        self.worker = worker

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.show_worker', self.node, self.worker)
        return self._post(session, result)


class CmdShowTransport(CmdShow):
    def __init__(self, node, worker, transport):
        CmdShow.__init__(self)
        self.node = node
        self.worker = worker
        self.transport = transport

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.show_transport', self.node, self.worker, self.transport)
        return self._post(session, result)


class CmdShowRealm(CmdShow):
    def __init__(self, node, worker, realm):
        CmdShow.__init__(self)
        self.node = node
        self.worker = worker
        self.realm = realm

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.show_realm', self.node, self.worker, self.realm)
        return self._post(session, result)


class CmdShowComponent(CmdShow):
    def __init__(self, node, worker, component):
        CmdShow.__init__(self)
        self.node = node
        self.worker = worker
        self.component = component

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.show_component', self.node, self.worker, self.component)
        return self._post(session, result)


class CmdShowApplicationRealm(CmdShow):
    """
    MREALM: show application realm by UUID or name.
    """
    def __init__(self, arealm):
        CmdShow.__init__(self)
        self.arealm = arealm

    async def run(self, session):
        self._pre(session)

        show_many = False
        if self.arealm == 'all' or self.arealm is None:
            arealms = await session.call('crossbarfabriccenter.mrealm.arealm.list_arealms')
            show_many = True
        else:
            if ',' in self.arealm:
                arealms = [x.strip() for x in self.arealm.split(',')]
            else:
                arealms = [self.arealm]

        result = []
        for arealm in arealms:
            try:
                arealm_oid = uuid.UUID(arealm)
            except:
                arealm_obj = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', arealm)
            else:
                arealm_obj = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm', str(arealm_oid))

            result.append(arealm_obj)

        if show_many:
            return self._post(session, result)
        else:
            return self._post(session, result[0])


class CmdShowPrincipal(CmdShow):
    """
    MREALM: show principal on an application realm role.
    """
    def __init__(self, arealm, principal):
        CmdShow.__init__(self)
        self.arealm = arealm
        self.principal = principal

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            principal_oid = uuid.UUID(self.principal)
        except:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal_by_name', arealm_oid,
                                           self.principal)
        else:
            principal = await session.call('crossbarfabriccenter.mrealm.arealm.get_principal', arealm_oid,
                                           str(principal_oid))

        return self._post(session, principal)


class CmdShowRole(CmdShow):
    """
    MREALM: show role by UUID or name.
    """
    def __init__(self, role):
        CmdShow.__init__(self)
        self.role = role

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.get_role', role_oid)

        return self._post(session, result)


class CmdShowRolePermission(CmdShow):
    """
    MREALM: show role permission by role UUID or name, and optionally URI
    """
    def __init__(self, role, uri):
        CmdShow.__init__(self)
        self.role = role
        self.uri = uri

    async def run(self, session):
        self._pre(session)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_permissions_by_uri', role_oid,
                                    self.uri)

        return self._post(session, result)


class CmdShowARealmRole(CmdShow):
    """
    MREALM: show application realm role association.
    """
    def __init__(self, arealm, role):
        CmdShow.__init__(self)
        self.arealm = arealm
        self.role = role

    async def run(self, session):
        self._pre(session)

        try:
            arealm_oid = uuid.UUID(self.arealm)
        except:
            arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)
            arealm_oid = arealm['oid']
        else:
            arealm_oid = str(arealm_oid)

        try:
            role_oid = uuid.UUID(self.role)
        except:
            role = await session.call('crossbarfabriccenter.mrealm.arealm.get_role_by_name', self.role)
            role_oid = role['oid']
        else:
            role_oid = str(role_oid)

        association = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_role', arealm_oid, role_oid)

        return self._post(session, association)


class CmdShowRouterCluster(CmdShow):
    """
    MREALM: show webcluster by UUID or name.
    """
    def __init__(self, cluster):
        CmdShow.__init__(self)
        self.cluster = cluster

    async def run(self, session):
        self._pre(session)

        show_many = False
        if self.cluster == 'all' or self.cluster is None:
            clusters = await session.call('crossbarfabriccenter.mrealm.routercluster.list_routerclusters')
            show_many = True
        else:
            if ',' in self.cluster:
                clusters = [x.strip() for x in self.cluster.split(',')]
                show_many = True
            else:
                clusters = [self.cluster]

        result = []
        for cluster in clusters:
            try:
                cluster_oid = uuid.UUID(cluster)
            except:
                cluster_obj = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                                 cluster)
            else:
                cluster_oid = str(cluster_oid)
                cluster_obj = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster',
                                                 cluster_oid)

            result.append(cluster_obj)

        if show_many:
            return self._post(session, result)
        else:
            return self._post(session, result[0])


class CmdShowRouterClusterNode(CmdShow):
    """
    MREALM: show routercluster-node by (UUID, UUID).
    """
    def __init__(self, cluster, node):
        CmdShow.__init__(self)
        self.cluster = cluster
        self.node = node

    async def run(self, session):
        self._pre(session)

        try:
            cluster_oid = uuid.UUID(self.cluster)
        except:
            cluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                         self.cluster)
            cluster_oid = cluster['oid']
        else:
            cluster_oid = str(cluster_oid)

        if self.node == 'all' or self.node is None:
            nodes = await session.call('crossbarfabriccenter.mrealm.routercluster.list_routercluster_nodes',
                                       cluster_oid)
        else:
            nodes = [x.strip() for x in self.node.split(',')]

        result = []
        for node in nodes:
            try:
                node_oid = uuid.UUID(node)
            except:
                node_obj = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', node)
                node_oid = node_obj['oid']
            else:
                node_oid = str(node_oid)

            rc_node = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_node',
                                         cluster_oid, node_oid)
            result.append(rc_node)

        return self._post(session, result)


class CmdShowRouterClusterWorkerGroup(CmdShow):
    """
    MREALM: show routercluster workergroup by UUID or name.
    """
    def __init__(self, cluster, workergroup):
        CmdShow.__init__(self)
        self.cluster = cluster
        self.workergroup = workergroup

    async def run(self, session):
        self._pre(session)

        workergroup = await session.call(
            'crossbarfabriccenter.mrealm.routercluster.get_routercluster_workergroup_by_name', self.cluster,
            self.workergroup)

        return self._post(session, workergroup)


class CmdShowWebCluster(CmdShow):
    """
    MREALM: show webcluster by UUID or name.
    """
    def __init__(self, cluster):
        CmdShow.__init__(self)
        self.cluster = cluster

    async def run(self, session):
        self._pre(session)

        list_all = False
        if self.cluster == 'all' or self.cluster is None:
            clusters = await session.call('crossbarfabriccenter.mrealm.webcluster.list_webclusters')
            list_all = True
        else:
            clusters = [x.strip() for x in self.cluster.split(',')]

        result = []
        for cluster in clusters:
            try:
                cluster_oid = uuid.UUID(cluster)
            except:
                cluster_obj = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                                 cluster)
            else:
                cluster_oid = str(cluster_oid)
                cluster_obj = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster', cluster_oid)

            result.append(cluster_obj)

        if list_all:
            return self._post(session, result)
        else:
            return self._post(session, result[0])


class CmdShowWebClusterWebService(CmdShow):
    """
    MREALM: show webcluster-webservice by (UUID, UUID).
    """
    def __init__(self, cluster, path):
        CmdShow.__init__(self)
        self.cluster = cluster
        self.path = path

    async def run(self, session):
        self._pre(session)

        try:
            cluster_oid = uuid.UUID(self.cluster)
        except:
            cluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name', self.cluster)
            cluster_oid = cluster['oid']
        else:
            cluster_oid = str(cluster_oid)

        webservice = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_service_by_path',
                                        cluster_oid, self.path)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_service', cluster_oid,
                                    webservice['oid'])

        return self._post(session, result)


class CmdShowWebClusterNode(CmdShow):
    """
    MREALM: show webcluster-node by (UUID, UUID).
    """
    def __init__(self, cluster, node):
        CmdShow.__init__(self)
        self.cluster = cluster
        self.node = node

    async def run(self, session):
        self._pre(session)

        try:
            cluster_oid = uuid.UUID(self.cluster)
        except:
            cluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name', self.cluster)
            cluster_oid = cluster['oid']
        else:
            cluster_oid = str(cluster_oid)

        if self.node == 'all' or self.node is None:
            nodes = await session.call('crossbarfabriccenter.mrealm.webcluster.list_webcluster_nodes', cluster_oid)
        else:
            nodes = [x.strip() for x in self.node.split(',')]

        result = []
        for node in nodes:
            try:
                node_oid = uuid.UUID(node)
            except:
                node_obj = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', node)
                node_oid = node_obj['oid']
            else:
                node_oid = str(node_oid)

            cluster_node = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_node',
                                              cluster_oid, node_oid)
            result.append(cluster_node)

        return self._post(session, result)


class CmdStart(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdStartDockerContainer(CmdStart):
    def __init__(self, node, container):
        CmdStart.__init__(self)
        self.node = node
        self.container = container

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.start', node['oid'], self.container)
        return self._post(session, result)


class CmdStartWorker(CmdStart):
    def __init__(self, node_id, worker_id, worker_type, worker_options=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.worker_options = worker_options

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.node.start_worker',
                                    node_id=self.node_id,
                                    worker_id=self.worker_id,
                                    worker_type=self.worker_type,
                                    worker_options=self.worker_options)
        return self._post(session, result)


class CmdStartContainerWorker(CmdStart):
    def __init__(self, node_id, worker_id, process_title=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.process_title = process_title

    async def run(self, session):
        self._pre(session)

        options = {}
        if self.process_title:
            options['title'] = self.process_title

        result = await session.call('crossbarfabriccenter.remote.node.start_worker',
                                    node_id=self.node_id,
                                    worker_id=self.worker_id,
                                    worker_type='container',
                                    worker_options=options)
        return self._post(session, result)


class CmdStartContainerComponent(CmdStart):
    def __init__(self, node_id, worker_id, component_id, config=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.component_id = component_id

        if config:
            self.config = config
        else:
            self.config = {
                'type': 'class',
                'transport': {
                    'type': None,
                    'endpoint': {
                        'type': 'websocket',
                        'url': 'ws://localhost:8080/ws'
                    }
                }
            }

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.remote.container.start_component',
                                    node_id=self.node_id,
                                    worker_id=self.worker_id,
                                    component_id=self.component_id,
                                    config=self.config)
        return self._post(session, result)


class CmdStartRouterWorker(CmdStart):
    def __init__(self, node_id, worker_id, process_title=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.process_title = process_title

    async def run(self, session):
        self._pre(session)

        options = {}
        if self.process_title:
            options['title'] = self.process_title

        result = await session.call('crossbarfabriccenter.remote.node.start_worker',
                                    node_id=self.node_id,
                                    worker_id=self.worker_id,
                                    worker_type='router',
                                    worker_options=options)
        return self._post(session, result)


class CmdStartRouterRealm(CmdStart):
    def __init__(self, node_id, worker_id, realm_id, config=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.realm_id = realm_id

        if config:
            self.config = config
        else:
            self.config = {
                "options": {
                    "enable_meta_api": True,
                    "bridge_meta_api": False
                },
                "roles": [{
                    "name":
                    "anonymous",
                    "permissions": [{
                        "uri": "",
                        "match": "prefix",
                        "allow": {
                            "call": True,
                            "register": True,
                            "publish": True,
                            "subscribe": True
                        },
                        "disclose": {
                            "caller": False,
                            "publisher": False
                        },
                        "cache": True
                    }]
                }]
            }

        if 'name' not in self.config:
            self.config['name'] = self.realm_id

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.remote.router.start_router_realm', self.node_id,
                                    self.worker_id, self.realm_id, self.config)
        return self._post(session, result)


class CmdStartRouterTransport(CmdStart):
    def __init__(self, node_id, worker_id, transport_id, config=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.transport_id = transport_id
        if config:
            self.config = config
        else:
            self.config = {
                "type": "universal",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080
                },
                "rawsocket": {},
                "websocket": {
                    "ws": {
                        "type": "websocket"
                    }
                },
                "web": {
                    "paths": {
                        "/": {
                            "type": "nodeinfo"
                        }
                    }
                }
            }

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.remote.router.start_router_transport', self.node_id,
                                    self.worker_id, self.transport_id, self.config)
        return self._post(session, result)


class CmdStartWebTransportService(CmdStart):
    def __init__(self, node_id, worker_id, transport_id, path, config=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.transport_id = transport_id
        self.path = path
        if config:
            self.config = config
        else:
            self.config = {
                "type": "info",
            }

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.remote.router.start_web_transport_service', self.node_id,
                                    self.worker_id, self.transport_id, self.path, self.config)
        return self._post(session, result)


class CmdStartGuestWorker(CmdStart):
    def __init__(self, node_id, worker_id, config=None):
        CmdStart.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        if config:
            self.config = config
        else:
            self.config = {
                "type": "guest",
                "executable": "/bin/date",
                "arguments": [],
                "options": {
                    "workdir": "..",
                    "env": {
                        "inherit": True
                    }
                }
            }

    async def run(self, session):
        self._pre(session)

        result = await session.call('crossbarfabriccenter.remote.node.start_worker', self.node_id, self.worker_id,
                                    'guest', self.config)
        return self._post(session, result)


class CmdStartRouterCluster(CmdStart):
    def __init__(self, routercluster):
        CmdStart.__init__(self)
        self.routercluster = routercluster

    async def run(self, session):
        self._pre(session)

        routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                           self.routercluster)

        result = await session.call('crossbarfabriccenter.mrealm.routercluster.start_routercluster',
                                    routercluster['oid'])
        return self._post(session, result)


class CmdStartApplicationRealm(CmdStart):
    def __init__(self, arealm, routercluster, workergroup, webcluster):
        CmdStart.__init__(self)
        self.arealm = arealm
        self.routercluster = routercluster
        self.workergroup = workergroup
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)

        arealm = await session.call('crossbarfabriccenter.mrealm.arealm.get_arealm_by_name', self.arealm)

        workergroup = await session.call(
            'crossbarfabriccenter.mrealm.routercluster.get_routercluster_workergroup_by_name', self.routercluster,
            self.workergroup)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        result = await session.call('crossbarfabriccenter.mrealm.arealm.start_arealm', arealm['oid'],
                                    workergroup['oid'], webcluster['oid'])
        return self._post(session, result)


class CmdStartWebCluster(CmdStart):
    def __init__(self, webcluster):
        CmdStart.__init__(self)
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.start_webcluster', webcluster['oid'])
        return self._post(session, result)


class CmdStop(Cmd):
    def __init__(self):
        Cmd.__init__(self)


class CmdStopDockerContainer(CmdStop):
    def __init__(self, node, container):
        CmdStop.__init__(self)
        self.node = node
        self.container = container

    async def run(self, session):
        self._pre(session)
        node = await session.call('crossbarfabriccenter.mrealm.get_node_by_authid', self.node)
        result = await session.call('crossbarfabriccenter.remote.docker.stop', node['oid'], self.container)
        return self._post(session, result)


class CmdStopWorker(CmdStop):
    def __init__(self, node_id, worker_id):
        CmdStop.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.node.stop_worker',
                                    node_id=self.node_id,
                                    worker_id=self.worker_id)
        return self._post(session, result)


class CmdStopRouterRealm(CmdStop):
    def __init__(self, node_id, worker_id, realm_id):
        CmdStop.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.realm_id = realm_id

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.router.stop_router_realm', self.node_id,
                                    self.worker_id, self.realm_id)
        return self._post(session, result)


class CmdStopRouterTransport(CmdStop):
    def __init__(self, node_id, worker_id, transport_id):
        CmdStop.__init__(self)
        self.node_id = node_id
        self.worker_id = worker_id
        self.transport_id = transport_id

    async def run(self, session):
        self._pre(session)
        result = await session.call('crossbarfabriccenter.remote.router.stop_router_transport', self.node_id,
                                    self.worker_id, self.transport_id)
        return self._post(session, result)


class CmdStopRouterCluster(CmdStop):
    def __init__(self, routercluster):
        CmdStop.__init__(self)
        self.routercluster = routercluster

    async def run(self, session):
        self._pre(session)

        routercluster = await session.call('crossbarfabriccenter.mrealm.routercluster.get_routercluster_by_name',
                                           self.routercluster)

        result = await session.call('crossbarfabriccenter.mrealm.routercluster.stop_routercluster',
                                    routercluster['oid'])

        return self._post(session, result)


class CmdStopWebCluster(CmdStop):
    def __init__(self, webcluster):
        CmdStop.__init__(self)
        self.webcluster = webcluster

    async def run(self, session):
        self._pre(session)

        webcluster = await session.call('crossbarfabriccenter.mrealm.webcluster.get_webcluster_by_name',
                                        self.webcluster)

        result = await session.call('crossbarfabriccenter.mrealm.webcluster.stop_webcluster', webcluster['oid'])

        return self._post(session, result)
