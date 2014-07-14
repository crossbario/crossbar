###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

from twisted.trial import unittest
#import unittest

from crossbar.router.session import CrossbarRouterRoleStaticAuth


class Test_RouterRoleStaticAuth(unittest.TestCase):

   def setUp(self):
      pass


   def test_ruleset_empty(self):
      permissions = []
      role = CrossbarRouterRoleStaticAuth(None, "testrole", permissions)
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
      role = CrossbarRouterRoleStaticAuth(None, "testrole", permissions)
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
      role = CrossbarRouterRoleStaticAuth(None, "testrole", permissions)
      actions = ['call', 'register', 'publish', 'subscribe']
      uris = [('com.example.1', True), ('myuri', True), ('', True)]
      for uri, allow in uris:
         for action in actions:
            self.assertEqual(role.authorize(None, uri, action), allow)

if __name__ == '__main__':
   unittest.main()
