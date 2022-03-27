###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from typing import Dict, List  # noqa

import re

from txaio import make_logger

from autobahn.wamp.types import RegisterOptions, SubscribeOptions, PublishOptions
from crossbar._util import hl, hlid, hluserid

__all__ = ('RemoteApi', )


class RemoteApi(object):

    PREFIX = 'unset'

    PROCS = {'node': [], 'worker': []}  # type: Dict[str, List]

    EVENTS = {'node': [], 'worker': []}  # type: Dict[str, List]

    log = make_logger()

    def register(self, session):
        """

        :param session: MrealmController
        :return:
        """
        regs = []

        # create forwards on node_id
        #
        def create_forward_by_node(local_uri, remote_uri):
            def forward(node_oid, *args, **kwargs):
                # remove the calling origin details (do not forward those 1:1 at least - FIXME)
                kwargs.pop('details', None)

                # map the node OID (given as UUID string) to the node WAMP authid for ..
                node_authid = session.map_node_oid_to_authid(node_oid)

                # .. creating the remote URI to be used on the management uplink
                _remote_uri = remote_uri.format(node_id=node_authid)

                self.log.debug(
                    'Forwarding CFC {forward_type} on mrealm {realm} to node "{node_authid}" [node_oid={node_oid}, local=<{local_uri}>, remote=<{remote_uri}>]',
                    forward_type=hl('CALL'),
                    local_uri=hlid(local_uri),
                    remote_uri=hlid(_remote_uri),
                    node_oid=hlid(node_oid),
                    node_authid=hluserid(node_authid),
                    realm=hluserid(session._realm))
                return session.call(_remote_uri, *args, **kwargs)

            return session.register(forward, local_uri, options=RegisterOptions(details_arg='details'))

        procs_by_node = self.PROCS.get('node', [])

        for proc in procs_by_node:
            if type(proc) == tuple:
                proc, rproc = proc
            else:
                rproc = proc
            local_uri = '{prefix}{proc}'.format(prefix=self.PREFIX, proc=proc)
            remote_uri = 'crossbarfabriccenter.node.{{node_id}}.{proc}'.format(proc=rproc)
            regs.append(create_forward_by_node(local_uri, remote_uri))

        # create forwards on node_id, worker_id
        #
        def create_forward_by_worker(local_uri, remote_uri):
            def forward(node_oid, worker_id, *args, **kwargs):
                # remove the calling origin details (do not forward those 1:1 at least - FIXME)
                kwargs.pop('details', None)

                # map the node OID (given as UUID string) to the node WAMP authid for ..
                node_authid = session.map_node_oid_to_authid(node_oid)

                # .. creating the remote URI to be used on the management uplink
                _remote_uri = remote_uri.format(node_id=node_authid, worker_id=worker_id)

                self.log.debug(
                    'Forwarding CFC {forward_type} mrealm {realm} to node "{node_authid}" and worker {worker_id} [node_oid={node_oid}, local=<{local_uri}>, remote=<{remote_uri}>]',
                    forward_type=hl('CALL'),
                    local_uri=hlid(local_uri),
                    remote_uri=hlid(_remote_uri),
                    node_oid=hlid(node_oid),
                    node_authid=hluserid(node_authid),
                    worker_id=hluserid(worker_id),
                    realm=hluserid(session._realm))
                return session.call(_remote_uri, *args, **kwargs)

            return session.register(forward, local_uri, options=RegisterOptions(details_arg='details'))

        procs_by_worker = self.PROCS.get('worker', [])

        for proc in procs_by_worker:
            if type(proc) == tuple:
                proc, rproc = proc
            else:
                rproc = proc
            local_uri = '{prefix}{proc}'.format(prefix=self.PREFIX, proc=proc)
            remote_uri = 'crossbarfabriccenter.node.{{node_id}}.worker.{{worker_id}}.{proc}'.format(proc=rproc)
            regs.append(create_forward_by_worker(local_uri, remote_uri))

        return regs

    def subscribe(self, session):
        subs = []

        #
        # create forwards on node_id
        #
        def create_forward_by_node(local_uri, remote_uri, remote_uri_regex):
            pat = re.compile(remote_uri_regex)

            def forward(*args, **kwargs):
                details = kwargs.pop('details', None)
                if details:
                    match = pat.match(details.topic)
                    if match:
                        node_id = match.groups()[0]

                        # FIXME: map back from node authid (?) to node OID (as UUID string)?

                        self.log.debug(
                            'Forwarding CFC {forward_type} on mrealm {realm} from node {node_id} [local=<{local_uri}>, remote=<{remote_uri}>]',
                            forward_type=hl('EVENT'),
                            local_uri=hlid(local_uri),
                            remote_uri=hlid(details.topic),
                            node_id=hluserid(node_id),
                            realm=hluserid(session._realm))

                        return session.publish(local_uri,
                                               node_id,
                                               *args,
                                               **kwargs,
                                               options=PublishOptions(exclude_me=False))

                # should not arrive here
                session.log.warn(
                    'received unexpected event to forward for management API: local_uri={local_uri}, remote_uri={remote_uri}, remote_uri_regex={remote_uri_regex} details={details}',
                    local_uri=local_uri,
                    remote_uri=remote_uri,
                    remote_uri_regex=remote_uri_regex,
                    details=details)

            return session.subscribe(forward, remote_uri, SubscribeOptions(match='wildcard', details=True))

        topics_by_node = self.EVENTS.get('node', [])

        for topic in topics_by_node:
            if type(topic) == tuple:
                topic, rtopic = topic
            else:
                rtopic = topic
            local_uri = '{prefix}{topic}'.format(prefix=self.PREFIX, topic=topic)
            remote_uri = 'crossbarfabriccenter.node..{topic}'.format(topic=rtopic)
            remote_uri_regex = r'^crossbarfabriccenter.node.([a-z0-9][a-z0-9_\-]*).{topic}$'.format(topic=rtopic)
            subs.append(create_forward_by_node(local_uri, remote_uri, remote_uri_regex))

        #
        # create forwards on node_id, worker_id
        #
        def create_forward_by_worker(local_uri, remote_uri, remote_uri_regex):
            pat = re.compile(remote_uri_regex)

            def forward(*args, **kwargs):
                details = kwargs.pop('details', None)
                if details:
                    match = pat.match(details.topic)
                    if match:
                        node_id, worker_id = match.groups()

                        # FIXME: map back from node authid (?) to node OID (as UUID string)?

                        self.log.debug(
                            'Forwarding CFC {forward_type} on mrealm {realm} from node {node_id} and worker {worker_id} [local=<{local_uri}>, remote=<{remote_uri}>]',
                            forward_type=hl('EVENT'),
                            local_uri=hlid(local_uri),
                            remote_uri=hlid(details.topic),
                            node_id=hluserid(node_id),
                            worker_id=hluserid(worker_id),
                            realm=hluserid(session._realm))

                        return session.publish(local_uri,
                                               node_id,
                                               worker_id,
                                               *args,
                                               **kwargs,
                                               options=PublishOptions(exclude_me=False))

                # should not arrive here
                session.log.warn(
                    'received unexpected event to forward for management API: local_uri={local_uri}, remote_uri={remote_uri}, remote_uri_regex={remote_uri_regex} details={details}',
                    local_uri=local_uri,
                    remote_uri=remote_uri,
                    remote_uri_regex=remote_uri_regex,
                    details=details)

            return session.subscribe(forward, remote_uri, SubscribeOptions(match='wildcard', details=True))

        topics_by_worker = self.EVENTS.get('worker', [])

        for topic in topics_by_worker:
            if type(topic) == tuple:
                topic, rtopic = topic
            else:
                rtopic = topic
            local_uri = '{prefix}{topic}'.format(prefix=self.PREFIX, topic=topic)
            remote_uri = 'crossbarfabriccenter.node..worker..{topic}'.format(topic=rtopic)
            remote_uri_regex = r'^crossbarfabriccenter.node.([a-z0-9][a-z0-9_\-]*).worker.([a-z0-9][a-z0-9_\-]*).{topic}$'.format(
                topic=rtopic)
            subs.append(create_forward_by_worker(local_uri, remote_uri, remote_uri_regex))

        return subs
