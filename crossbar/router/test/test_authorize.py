#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest
from twisted.internet import defer

import txaio

txaio.use_twisted()  # noqa

from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.auth import cryptosign, wampcra, ticket, tls, anonymous

from autobahn.wamp import types

from mock import Mock


class MockRealmContainer(object):
    def __init__(self, realm, roles, session):
        self._realm = realm
        self._roles = roles
        self._session = session

    def has_realm(self, realm):
        return realm == self._realm

    def has_role(self, realm, role):
        return realm == self._realm and role in self._roles

    def get_service_session(self, realm, role):
        assert realm == self._realm, 'realm must be "{}", but was "{}"'.format(self._realm, realm)
        return defer.succeed(self._session)


class TestDynamicAuth(unittest.TestCase):
    @defer.inlineCallbacks
    def test_authextra_wampcryptosign(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport.transport_details = types.TransportDetails()

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual("foo.auth_a_doodle", method)
            self.assertEqual("realm", realm)
            self.assertEqual(details["authmethod"], "cryptosign")
            self.assertEqual(details["authextra"], {"foo": "bar"})
            return defer.succeed({
                "pubkey": 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                "role": "some_role",
                "extra": {
                    "what": "authenticator-supplied authextra",
                }
            })

        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._router_factory = {
            "realm": realm,
        }
        config = {
            "type": "dynamic",
            "authenticator": "foo.auth_a_doodle",
            "authenticator-realm": "realm",
            "authenticator-role": "myauth_role"
        }
        extra = {
            "foo": "bar",
        }
        details = Mock()
        details.authextra = extra

        pending_session_id = 1
        transport_details = types.TransportDetails()
        realm_container = MockRealmContainer("realm", ["some_role", "myauth_role"], session)

        auth = cryptosign.PendingAuthCryptosign(pending_session_id, transport_details, realm_container, config)
        val = yield auth.hello("realm", details)

        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual("cryptosign", val.method)
        self.assertTrue("challenge" in val.extra)
        self.assertEqual(auth._authextra, {"what": "authenticator-supplied authextra"})

    @defer.inlineCallbacks
    def test_authextra_wampcra(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport.transport_details = types.TransportDetails()

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual("foo.auth_a_doodle", method)
            self.assertEqual("realm", realm)
            self.assertEqual(details["authmethod"], "wampcra")
            self.assertEqual(details["authextra"], {"foo": "bar"})
            return defer.succeed({
                "secret": 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                "role": "some_role",
                "extra": {
                    "what": "authenticator-supplied authextra",
                }
            })

        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = 'pending session id'
        session._router_factory = {
            "realm": realm,
        }
        config = {
            "type": "dynamic",
            "authenticator": "foo.auth_a_doodle",
            "authenticator-realm": "realm",
            "authenticator-role": "myauth_role"
        }
        extra = {
            "foo": "bar",
        }
        details = Mock()
        details.authid = 'alice'
        details.authextra = extra

        pending_session_id = 1
        transport_details = types.TransportDetails()
        realm_container = MockRealmContainer("realm", ["some_role", "myauth_role"], session)

        auth = wampcra.PendingAuthWampCra(pending_session_id, transport_details, realm_container, config)
        val = yield auth.hello("realm", details)

        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual("wampcra", val.method)
        self.assertTrue("challenge" in val.extra)
        self.assertEqual(auth._authextra, {"what": "authenticator-supplied authextra"})

    @defer.inlineCallbacks
    def test_authextra_tls(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport.transport_details = types.TransportDetails()

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual("foo.auth_a_doodle", method)
            self.assertEqual("realm", realm)
            self.assertEqual(details["authmethod"], "tls")
            self.assertEqual(details["authextra"], {"foo": "bar"})
            return defer.succeed({
                "secret": 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                "role": "some_role",
                "extra": {
                    "what": "authenticator-supplied authextra",
                }
            })

        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = 'pending session id'
        session._router_factory = {
            "realm": realm,
        }
        config = {
            "type": "dynamic",
            "authenticator": "foo.auth_a_doodle",
            "authenticator-realm": "realm",
            "authenticator-role": "myauth_role"
        }
        extra = {
            "foo": "bar",
        }
        details = Mock()
        details.authid = 'alice'
        details.authextra = extra

        pending_session_id = 1
        transport_details = types.TransportDetails(channel_id={'tls-unique': b'anything'}, peer_cert={'some': 'thing'})
        realm_container = MockRealmContainer("realm", ["some_role", "myauth_role"], session)

        auth = tls.PendingAuthTLS(pending_session_id, transport_details, realm_container, config)
        val = yield auth.hello("realm", details)

        self.assertTrue(isinstance(val, types.Accept))
        self.assertEqual(val.authmethod, "tls")
        self.assertEqual(val.authextra, {"what": "authenticator-supplied authextra"})

    @defer.inlineCallbacks
    def test_authextra_anonymous(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport.transport_details = types.TransportDetails()

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual("foo.auth_a_doodle", method)
            self.assertEqual("realm", realm)
            self.assertEqual(details["authmethod"], "anonymous")
            self.assertEqual(details["authextra"], {"foo": "bar"})
            return defer.succeed({
                "secret": 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                "role": "some_role",
                "extra": {
                    "what": "authenticator-supplied authextra",
                }
            })

        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = 'pending session id'
        session._router_factory = {
            "realm": realm,
        }
        config = {
            "type": "dynamic",
            "authenticator": "foo.auth_a_doodle",
            "authenticator-realm": "realm",
            "authenticator-role": "myauth_role"
        }
        extra = {
            "foo": "bar",
        }
        details = Mock()
        details.authid = 'alice'
        details.authextra = extra

        pending_session_id = 1
        transport_details = types.TransportDetails()
        realm_container = MockRealmContainer("realm", ["some_role", "myauth_role"], session)

        auth = anonymous.PendingAuthAnonymous(pending_session_id, transport_details, realm_container, config)
        val = yield auth.hello("realm", details)

        self.assertTrue(isinstance(val, types.Accept))
        self.assertEqual(val.authmethod, "anonymous")
        self.assertEqual(val.authextra, {"what": "authenticator-supplied authextra"})

    @defer.inlineCallbacks
    def test_authextra_ticket(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport.transport_details = types.TransportDetails()

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual("foo.auth_a_doodle", method)
            self.assertEqual("realm", realm)
            self.assertEqual(details["authmethod"], "ticket")
            self.assertEqual(details["authextra"], {"foo": "bar"})
            return defer.succeed({
                "secret": 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                "role": "some_role",
                "extra": {
                    "what": "authenticator-supplied authextra",
                }
            })

        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = 'pending session id'
        session._router_factory = {
            "realm": realm,
        }
        config = {
            "type": "dynamic",
            "authenticator": "foo.auth_a_doodle",
            "authenticator-realm": "realm",
            "authenticator-role": "myauth_role"
        }
        extra = {
            "foo": "bar",
        }
        details = Mock()
        details.authid = 'alice'
        details.authextra = extra

        pending_session_id = 1
        transport_details = types.TransportDetails()
        realm_container = MockRealmContainer("realm", ["some_role", "myauth_role"], session)

        auth = ticket.PendingAuthTicket(pending_session_id, transport_details, realm_container, config)
        val = yield auth.hello("realm", details)

        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual("ticket", val.method)
        self.assertEqual({}, val.extra)

        d = auth.authenticate("fake signature")
        self.assertTrue(isinstance(d.result, types.Accept))
        acc = d.result
        self.assertEqual(acc.authextra, {"what": "authenticator-supplied authextra"})
        self.assertEqual(acc.authid, 'alice')


class TestRouterRoleStaticAuth(unittest.TestCase):
    def test_ruleset_empty(self):
        permissions = []
        role = RouterRoleStaticAuth(None, 'testrole', permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = ['com.example.1', 'myuri', '']
        for uri in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertFalse(authorization['allow'])

    def test_ruleset_1(self):
        permissions = [{
            'uri': 'com.example.*',
            'allow': {
                'call': True,
                'register': True,
                'publish': True,
                'subscribe': True
            }
        }]
        role = RouterRoleStaticAuth(None, 'testrole', permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = [('com.example.1', True), ('myuri', False), ('', False)]
        for uri, allow in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertEqual(authorization['allow'], allow)

    def test_ruleset_2(self):
        permissions = [{'uri': '*', 'allow': {'call': True, 'register': True, 'publish': True, 'subscribe': True}}]
        role = RouterRoleStaticAuth(None, 'testrole', permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = [('com.example.1', True), ('myuri', True), ('', True)]
        for uri, allow in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertEqual(authorization['allow'], allow)


class TestRouterRoleStaticAuthWild(unittest.TestCase):
    def setUp(self):
        permissions = [{
            'uri': 'com..private',
            'match': 'wildcard',
            'allow': {
                'call': True,
                'register': False,
                'publish': False,
                'subscribe': False,
            }
        }, {
            'uri': 'com.something_specific.private',
            'match': 'exact',
            'allow': {
                'call': False,
                'register': True,
                'publish': False,
                'subscribe': False
            }
        }, {
            'uri': 'com.',
            'match': 'prefix',
            'allow': {
                'call': False,
                'register': False,
                'publish': True,
                'subscribe': False
            }
        }]
        self.role = RouterRoleStaticAuth(None, 'testrole', permissions)

    def test_exact_before_wildcard(self):
        # exact matches should always be preferred over wildcards
        self.assertEqual(False, self.role.authorize(None, 'com.something_specific.private', 'call', {})['allow'])
        self.assertEqual(True, self.role.authorize(None, 'com.something_specific.private', 'register', {})['allow'])

    def test_wildcard_before_prefix(self):
        # wildcards should be preferred over prefix
        self.assertEqual(True, self.role.authorize(None, 'com.foo.private', 'call', {})['allow'])
        self.assertEqual(False, self.role.authorize(None, 'com.foo.private', 'register', {})['allow'])
        self.assertEqual(False, self.role.authorize(None, 'com.foo.private', 'publish', {})['allow'])

    def test_prefix(self):
        # wildcards should be preferred over prefix
        self.assertEqual(False, self.role.authorize(None, 'com.whatever', 'call', {})['allow'])
        self.assertEqual(False, self.role.authorize(None, 'com.whatever', 'register', {})['allow'])
        self.assertEqual(True, self.role.authorize(None, 'com.whatever', 'publish', {})['allow'])
