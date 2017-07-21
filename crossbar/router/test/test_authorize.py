#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

from twisted.trial import unittest
from twisted.internet import defer

from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.auth import cryptosign, wampcra, ticket, tls, anonymous

from autobahn.wamp import types

from mock import Mock


class TestDynamicAuth(unittest.TestCase):

    def test_authextra_wampcryptosign(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport._transport_info = {}

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual(u"foo.auth_a_doodle", method)
            self.assertEqual(u"realm", realm)
            self.assertEqual(details[u"authmethod"], u"cryptosign")
            self.assertEqual(details[u"authextra"], {u"foo": u"bar"})
            return defer.succeed({
                u"pubkey": u'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                u"role": u"some_role",
                u"extra": {
                    u"what": u"authenticator-supplied authextra",
                }
            })
        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._router_factory = {
            u"realm": realm,
        }
        config = {
            u"type": u"dynamic",
            u"authenticator": u"foo.auth_a_doodle",
        }
        extra = {
            u"foo": u"bar",
        }
        details = Mock()
        details.authextra = extra

        auth = cryptosign.PendingAuthCryptosign(session, config)
        reply = auth.hello(u"realm", details)

        val = reply.result
        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual(u"cryptosign", val.method)
        self.assertTrue(u"challenge" in val.extra)
        self.assertEqual(auth._authextra, {u"what": u"authenticator-supplied authextra"})

    def test_authextra_wampcra(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport._transport_info = {}

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual(u"foo.auth_a_doodle", method)
            self.assertEqual(u"realm", realm)
            self.assertEqual(details[u"authmethod"], u"wampcra")
            self.assertEqual(details[u"authextra"], {u"foo": u"bar"})
            return defer.succeed({
                u"secret": u'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                u"role": u"some_role",
                u"extra": {
                    u"what": u"authenticator-supplied authextra",
                }
            })
        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = u'pending session id'
        session._router_factory = {
            u"realm": realm,
        }
        config = {
            u"type": u"dynamic",
            u"authenticator": u"foo.auth_a_doodle",
        }
        extra = {
            u"foo": u"bar",
        }
        details = Mock()
        details.authid = u'alice'
        details.authextra = extra

        auth = wampcra.PendingAuthWampCra(session, config)
        reply = auth.hello(u"realm", details)

        val = reply.result
        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual(u"wampcra", val.method)
        self.assertTrue(u"challenge" in val.extra)
        self.assertEqual(auth._authextra, {u"what": u"authenticator-supplied authextra"})

    def test_authextra_tls(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport._transport_info = {}

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual(u"foo.auth_a_doodle", method)
            self.assertEqual(u"realm", realm)
            self.assertEqual(details[u"authmethod"], u"tls")
            self.assertEqual(details[u"authextra"], {u"foo": u"bar"})
            return defer.succeed({
                u"secret": u'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                u"role": u"some_role",
                u"extra": {
                    u"what": u"authenticator-supplied authextra",
                }
            })
        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = u'pending session id'
        session._router_factory = {
            u"realm": realm,
        }
        config = {
            u"type": u"dynamic",
            u"authenticator": u"foo.auth_a_doodle",
        }
        extra = {
            u"foo": u"bar",
        }
        details = Mock()
        details.authid = u'alice'
        details.authextra = extra

        auth = tls.PendingAuthTLS(session, config)
        reply = auth.hello(u"realm", details)

        val = reply.result
        self.assertTrue(isinstance(val, types.Accept))
        self.assertEqual(val.authmethod, u"tls")
        self.assertEqual(val.authextra, {u"what": u"authenticator-supplied authextra"})

    def test_authextra_anonymous(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport._transport_info = {}

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual(u"foo.auth_a_doodle", method)
            self.assertEqual(u"realm", realm)
            self.assertEqual(details[u"authmethod"], u"anonymous")
            self.assertEqual(details[u"authextra"], {u"foo": u"bar"})
            return defer.succeed({
                u"secret": u'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                u"role": u"some_role",
                u"extra": {
                    u"what": u"authenticator-supplied authextra",
                }
            })
        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = u'pending session id'
        session._router_factory = {
            u"realm": realm,
        }
        config = {
            u"type": u"dynamic",
            u"authenticator": u"foo.auth_a_doodle",
        }
        extra = {
            u"foo": u"bar",
        }
        details = Mock()
        details.authid = u'alice'
        details.authextra = extra

        auth = anonymous.PendingAuthAnonymous(session, config)
        reply = auth.hello(u"realm", details)

        val = reply.result
        self.assertTrue(isinstance(val, types.Accept))
        self.assertEqual(val.authmethod, u"anonymous")
        self.assertEqual(val.authextra, {u"what": u"authenticator-supplied authextra"})

    def test_authextra_ticket(self):
        """
        We pass along the authextra to a dynamic authenticator
        """
        session = Mock()
        session._transport._transport_info = {}

        def fake_call(method, *args, **kw):
            realm, authid, details = args
            self.assertEqual(u"foo.auth_a_doodle", method)
            self.assertEqual(u"realm", realm)
            self.assertEqual(details[u"authmethod"], u"ticket")
            self.assertEqual(details[u"authextra"], {u"foo": u"bar"})
            return defer.succeed({
                u"secret": u'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                u"role": u"some_role",
                u"extra": {
                    u"what": u"authenticator-supplied authextra",
                }
            })
        session.call = Mock(side_effect=fake_call)
        realm = Mock()
        realm._realm.session = session
        session._pending_session_id = u'pending session id'
        session._router_factory = {
            u"realm": realm,
        }
        config = {
            u"type": u"dynamic",
            u"authenticator": u"foo.auth_a_doodle",
        }
        extra = {
            u"foo": u"bar",
        }
        details = Mock()
        details.authid = u'alice'
        details.authextra = extra

        auth = ticket.PendingAuthTicket(session, config)
        val = auth.hello(u"realm", details)

        self.assertTrue(isinstance(val, types.Challenge))
        self.assertEqual(u"ticket", val.method)
        self.assertEqual({}, val.extra)

        d = auth.authenticate(u"fake signature")
        self.assertTrue(isinstance(d.result, types.Accept))
        acc = d.result
        self.assertEqual(acc.authextra, {u"what": u"authenticator-supplied authextra"})
        self.assertEqual(acc.authid, u'alice')


class TestRouterRoleStaticAuth(unittest.TestCase):

    def test_ruleset_empty(self):
        permissions = []
        role = RouterRoleStaticAuth(None, u'testrole', permissions)
        actions = [u'call', u'register', u'publish', u'subscribe']
        uris = [u'com.example.1', u'myuri', u'']
        for uri in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertFalse(authorization[u'allow'])

    def test_ruleset_1(self):
        permissions = [
            {
                u'uri': u'com.example.*',
                u'allow': {
                    u'call': True,
                    u'register': True,
                    u'publish': True,
                    u'subscribe': True
                }
            }
        ]
        role = RouterRoleStaticAuth(None, u'testrole', permissions)
        actions = [u'call', u'register', u'publish', u'subscribe']
        uris = [(u'com.example.1', True), (u'myuri', False), (u'', False)]
        for uri, allow in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertEqual(authorization[u'allow'], allow)

    def test_ruleset_2(self):
        permissions = [
            {
                u'uri': u'*',
                u'allow': {
                    u'call': True,
                    u'register': True,
                    u'publish': True,
                    u'subscribe': True
                }
            }
        ]
        role = RouterRoleStaticAuth(None, u'testrole', permissions)
        actions = [u'call', u'register', u'publish', u'subscribe']
        uris = [(u'com.example.1', True), (u'myuri', True), (u'', True)]
        for uri, allow in uris:
            for action in actions:
                authorization = role.authorize(None, uri, action, {})
                self.assertEqual(authorization[u'allow'], allow)


class TestRouterRoleStaticAuthWild(unittest.TestCase):

    def setUp(self):
        permissions = [
            {
                u'uri': u'com..private',
                u'match': 'wildcard',
                u'allow': {
                    u'call': True,
                    u'register': False,
                    u'publish': False,
                    u'subscribe': False,
                }
            },
            {
                u'uri': u'com.something_specific.private',
                u'match': 'exact',
                u'allow': {
                    u'call': False,
                    u'register': True,
                    u'publish': False,
                    u'subscribe': False
                }
            },
            {
                u'uri': u'com.',
                u'match': 'prefix',
                u'allow': {
                    u'call': False,
                    u'register': False,
                    u'publish': True,
                    u'subscribe': False
                }
            }
        ]
        self.role = RouterRoleStaticAuth(None, u'testrole', permissions)

    def test_exact_before_wildcard(self):
        # exact matches should always be preferred over wildcards
        self.assertEqual(
            False,
            self.role.authorize(None, u'com.something_specific.private', 'call', {})[u'allow']
        )
        self.assertEqual(
            True,
            self.role.authorize(None, u'com.something_specific.private', 'register', {})[u'allow']
        )

    def test_wildcard_before_prefix(self):
        # wildcards should be preferred over prefix
        self.assertEqual(
            True,
            self.role.authorize(None, u'com.foo.private', 'call', {})[u'allow']
        )
        self.assertEqual(
            False,
            self.role.authorize(None, u'com.foo.private', 'register', {})[u'allow']
        )
        self.assertEqual(
            False,
            self.role.authorize(None, u'com.foo.private', 'publish', {})[u'allow']
        )

    def test_prefix(self):
        # wildcards should be preferred over prefix
        self.assertEqual(
            False,
            self.role.authorize(None, u'com.whatever', 'call', {})[u'allow']
        )
        self.assertEqual(
            False,
            self.role.authorize(None, u'com.whatever', 'register', {})[u'allow']
        )
        self.assertEqual(
            True,
            self.role.authorize(None, u'com.whatever', 'publish', {})[u'allow']
        )
