#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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
# import unittest

from crossbar.router.role import RouterRoleStaticAuth


class Test_RouterRoleStaticAuth(unittest.TestCase):

    def setUp(self):
        pass

    def test_ruleset_empty(self):
        permissions = []
        role = RouterRoleStaticAuth(None, "testrole", permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = ['com.example.1', 'myuri', '']
        for uri in uris:
            for action in actions:
                self.assertFalse(role.authorize(None, uri, action))

    def test_ruleset_1(self):
        permissions = [
            {
                'uri': 'com.example.*',
                'call': True,
                'register': True,
                'publish': True,
                'subscribe': True
            }
        ]
        role = RouterRoleStaticAuth(None, "testrole", permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = [('com.example.1', True), ('myuri', False), ('', False)]
        for uri, allow in uris:
            for action in actions:
                self.assertEqual(role.authorize(None, uri, action), allow)

    def test_ruleset_2(self):
        permissions = [
            {
                'uri': '*',
                'call': True,
                'register': True,
                'publish': True,
                'subscribe': True
            }
        ]
        role = RouterRoleStaticAuth(None, "testrole", permissions)
        actions = ['call', 'register', 'publish', 'subscribe']
        uris = [('com.example.1', True), ('myuri', True), ('', True)]
        for uri, allow in uris:
            for action in actions:
                self.assertEqual(role.authorize(None, uri, action), allow)

if __name__ == '__main__':
    unittest.main()
