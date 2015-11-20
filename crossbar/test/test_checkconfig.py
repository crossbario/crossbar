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

from twisted.trial.unittest import TestCase

from crossbar.common import checkconfig

import json


class CheckDictArgsTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_dict_args}.
    """
    def test_notDict(self):
        """
        A non-dict passed in as the config will raise a
        L{checkconfig.InvalidConfigException}.
        """
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_dict_args({}, [], "msghere")

        self.assertEqual("msghere - invalid type for configuration item - expected dict, got list",
                         str(e.exception))

    def test_wrongType(self):
        """
        The wrong type (as defined in the spec) passed in the config will raise
        a L{checkconfig.InvalidConfigException}.
        """
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_dict_args({"foo": (False, [list, set])},
                                        {"foo": {}}, "msghere")

        self.assertEqual(("msghere - invalid type dict encountered for "
                          "attribute 'foo', must be one of (list, set)"),
                         str(e.exception))


class CheckTlsTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_container}.
    """
    def test_missing_dhparams(self):
        cfg = dict(
            key=u'/invalid',
            certificate=u'/invalid',
            dhparam=u'/invalid',
            ciphers=u'/invalid',
        )

        with self.assertRaises(checkconfig.InvalidConfigException) as err:
            checkconfig.check_listening_endpoint_tls(cfg)

        self.assertTrue("doesn't exist" in str(err.exception))


class CheckContainerTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_container}.
    """
    def test_validTemplate_hello(self):
        """
        The config provided by the hello:python template should validate
        successfully.
        """
        config = json.loads('''{
            "type": "container",
            "options": {
                "pythonpath": [".."]
            },
            "components": [
                {
                    "type": "class",
                    "classname": "hello.hello.AppSession",
                    "realm": "realm1",
                    "transport": {
                        "type": "websocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "127.0.0.1",
                            "port": 8080
                        },
                        "url": "ws://127.0.0.1:8080/ws"
                    }
                }
            ]
        }''')
        checkconfig.check_container(config)

    def test_extraKeys(self):
        """
        A component with extra keys will fail.
        """
        config = json.loads('''{
            "type": "container",
            "options": {
                "pythonpath": [".."]
            },
            "components": [
                {
                    "type": "class",
                    "classname": "hello.hello.AppSession",
                    "realm": "realm1",
                    "woooooo": "bar",
                    "transport": {
                        "type": "websocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "127.0.0.1",
                            "port": 8080
                        },
                        "url": "ws://127.0.0.1:8080/ws"
                    }
                }
            ]
        }''')
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_container(config)

        self.assertIn("encountered unknown attribute 'woooooo'",
                      str(e.exception))

    def test_requiredKeys(self):
        """
        A component with missing keys fails.
        """
        config = json.loads('''{
            "type": "container",
            "options": {
                "pythonpath": [".."]
            },
            "components": [
                {
                    "type": "class",
                    "classname": "hello.hello.AppSession",
                    "realm": "realm1"
                }
            ]
        }''')
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_container(config)

        self.assertIn("invalid component configuration - missing mandatory attribute 'transport'",
                      str(e.exception))
