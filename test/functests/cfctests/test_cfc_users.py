###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import txaio
txaio.use_twisted()

from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep
from autobahn.wamp.types import SubscribeOptions

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *


@inlineCallbacks
def test_organizations_crud(cfx_master):

    mrealm = None

    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    result = {
        'on_organization_created': None,
        'on_organization_deleted': None,
    }

    def on_created(org, details=None):
        print(hl('Event received on "cfc.user.on_organization_created"', bold=True),
              hl(org, bold=True),
              hl(details, bold=True))
        result['on_organization_created'] = True

    yield management_session.subscribe(on_created,
                                       'crossbarfabriccenter.user.on_organization_created',
                                       options=SubscribeOptions(match='exact', details=True))

    def on_deleted(org, details=None):
        print(hl('Event received on "cfc.user.on_organization_deleted"', bold=True),
              hl(org, bold=True),
              hl(details, bold=True))
        result['on_organization_deleted'] = True

    yield management_session.subscribe(on_deleted,
                                       'crossbarfabriccenter.user.on_organization_deleted',
                                       options=SubscribeOptions(match='exact', details=True))

    org_oids_initial = yield management_session.call('crossbarfabriccenter.user.list_organizations')
    print(hl(org_oids_initial, bold=True))

    yield sleep(.1)

    org_config = {
        'name': 'my_organization_1',
    }
    org_created = yield management_session.call('crossbarfabriccenter.user.create_organization', org_config)
    print(hl(org_created, bold=True))
    yield sleep(.1)

    org_oids = yield management_session.call('crossbarfabriccenter.user.list_organizations')
    print(hl(org_oids, bold=True))
    assert len(org_oids) == len(org_oids_initial) + 1

    org_deleted = yield management_session.call('crossbarfabriccenter.user.delete_organization', org_created['oid'])
    print(hl(org_deleted, bold=True))

    org_oids = yield management_session.call('crossbarfabriccenter.user.list_organizations')
    print(hl(org_oids, bold=True))
    assert len(org_oids) == len(org_oids_initial)

    print(hl(result, bold=True))
    assert result['on_organization_created']
    assert result['on_organization_deleted']

    user_oids = yield management_session.call('crossbarfabriccenter.user.list_users')
    print(hl(user_oids, bold=True))

    for user_oid in user_oids:
        user = yield management_session.call('crossbarfabriccenter.user.get_user', user_oid)
        # {'oid': 'e8ffabe0-80ff-4a0a-b1b7-643b5521985f', 'email': 'superuser', 'registered': 1560673549717857, 'pubkey': None}
        print(user)

        if user['pubkey']:
            _user = yield management_session.call('crossbarfabriccenter.user.get_user_by_pubkey', user['pubkey'])
            assert _user and _user['oid'] == user['oid']

        if user['email']:
            _user = yield management_session.call('crossbarfabriccenter.user.get_user_by_email', user['email'])
            assert _user and _user['oid'] == user['oid']

    yield management_session.leave()
