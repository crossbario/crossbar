###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import re

from txaio import make_logger

from autobahn.wamp.types import RegisterOptions, SubscribeOptions

__all__ = ('RemoteWampApi', )


class RemoteWampApi(object):
    """
    Exposes the WAMP meta API on a router realm from a remote node
    on CFC. This is only available if the router realm is started
    with option.bridge_meta_api == True.

    Events are published locally on the node WAMP meta API like

    [1] wamp.session.on_join
            (session_id, session_details)

    and (if bridged), on the local node management API

    [2] crossbar.worker.<worker_id>.realm.<realm_id>.root.wamp.session.on_join
            (session_id, session_details)

    which then get forward to CFC as

    [3] crossbarfabriccenter.node.<node_id>.worker.<worker_id>.realm.<realm_id>.root.
            (session_id, session_details)

    which is then republished by CFC as

    [4] crossbarfabriccenter.remote.realm.meta.wamp.session.on_join
            (node_id, worker_id, realm_id, session_id, session_details)

    For example:

    [1] wamp.session.on_join
    [2] crossbar.worker.worker-001.realm.realm-001.root.wamp.session.on_join
    [3] crossbarfabriccenter.node.cf1.worker.worker-001.realm.realm-001.root.wamp.session.on_join
    [4] crossbarfabriccenter.remote.realm.meta.wamp.session.on_join
    """

    log = make_logger()

    PREFIX = 'crossbarfabriccenter.remote.realm.meta.'

    def register(self, session):

        try:

            def forward(node_id, worker_id, realm_id, *args, **kwargs):
                details = kwargs.pop('details', None)
                proc = details.procedure[len(self.PREFIX):]
                uri = 'crossbarfabriccenter.node.{node_id}.worker.{worker_id}.realm.{realm_id}.root.{proc}'.format(
                    node_id=node_id, worker_id=worker_id, realm_id=realm_id, proc=proc)
                self.log.debug(
                    'Forwarding CFC remote WAMP meta API call <{proc}> on management realm "{mrealm}" to node_id "{node_id}", worker_id "{worker_id}", realm_id "{realm_id}"',
                    node_id=node_id,
                    worker_id=worker_id,
                    realm_id=realm_id,
                    proc=details.procedure,
                    mrealm=session._realm)
                return session.call(uri, *args, **kwargs)

            reg = session.register(forward,
                                   self.PREFIX,
                                   options=RegisterOptions(match='prefix', details_arg='details'))
            return [reg]

        except:
            self.log.failure()
            return []

    def subscribe(self, session):

        remote_uri = 'crossbarfabriccenter.node..worker..realm..root.'
        remote_uri_regex = r'^crossbarfabriccenter.node.([a-z0-9][a-z0-9_\-]*).worker.([a-z0-9][a-z0-9_\-]*).realm.([a-z0-9][a-z0-9_\-]*).root.(\S*)$'
        remote_uri_pat = re.compile(remote_uri_regex)

        def forward(*args, **kwargs):
            try:
                details = kwargs.pop('details', None)

                if details:
                    match = remote_uri_pat.match(details.topic)
                    if match and len(match.groups()) == 4:
                        node_id, worker_id, realm_id, suffix_uri = match.groups()

                        # reverse our hack: see crossbar.router.service.RouterServiceSession.publish
                        suffix_uri = suffix_uri.replace('-', '.')

                        local_uri = '{}{}'.format(self.PREFIX, suffix_uri)
                        self.log.debug('RemoteWampApi.forward("{topic}") -> "{local_uri}"',
                                       topic=details.topic,
                                       local_uri=local_uri)
                        return session.publish(local_uri, node_id, worker_id, realm_id, *args, **kwargs)

                # should not arrive here
                session.log.warn(
                    'received unexpected WAMP meta event to forward for management API: details={details}',
                    details=details)
            except:
                session.log.failure()

        sub = session.subscribe(forward, remote_uri, SubscribeOptions(match='wildcard', details=True))

        return [sub]
