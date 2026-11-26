#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json
from collections.abc import Sequence

import crossbar
from crossbar.common import checkconfig
from crossbar.test import TestCase

_DEFAULT_PERSONALITY_CLASS = crossbar.personalities()["standalone"]


class CheckDictArgsTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_dict_args}.
    """

    def test_sequence_string(self):
        """
        A Sequence should not imply we accept strings
        """
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_dict_args(
                {"foo": (True, [Sequence])}, {"foo": "not really a Sequence"}, "Nice message for the user"
            )
        self.assertEqual(
            "Nice message for the user - invalid type str encountered for attribute 'foo', must be one of (Sequence)",
            str(e.exception),
        )

    def test_sequence_list(self):
        """
        A Sequence should accept list
        """
        checkconfig.check_dict_args(
            {"foo": (True, [Sequence])}, {"foo": ["a", "real", "sequence"]}, "Nice message for the user"
        )
        # should work, with no exceptions

    def test_notDict(self):
        """
        A non-dict passed in as the config will raise a
        L{checkconfig.InvalidConfigException}.
        """
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_dict_args({}, [], "msghere")

        self.assertEqual("msghere - invalid type for configuration item - expected dict, got list", str(e.exception))

    def test_wrongType(self):
        """
        The wrong type (as defined in the spec) passed in the config will raise
        a L{checkconfig.InvalidConfigException}.
        """
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            checkconfig.check_dict_args({"foo": (False, [list, set])}, {"foo": {}}, "msghere")

        self.assertEqual(
            ("msghere - invalid type dict encountered for attribute 'foo', must be one of (list, set)"),
            str(e.exception),
        )


class CheckListeningEndpointTlsTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_listening_endpoint_tls} 'min_version' (#2037).
    """

    _BASE = {"key": "server.key", "certificate": "server.crt"}

    def test_min_version_13_accepted(self):
        checkconfig.check_listening_endpoint_tls({**self._BASE, "min_version": "1.3"})

    def test_min_version_12_accepted(self):
        checkconfig.check_listening_endpoint_tls({**self._BASE, "min_version": "1.2"})

    def test_min_version_invalid_rejected(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_listening_endpoint_tls({**self._BASE, "min_version": "1.1"})


class CheckContainerTests(TestCase):
    """
    Tests for L{crossbar.common.checkconfig.check_container}.
    """

    def setUp(self):
        self.personality = _DEFAULT_PERSONALITY_CLASS
        return super(TestCase, self).setUp()

    def test_validTemplate_hello(self):
        """
        The config provided by the hello:python template should validate
        successfully.
        """
        config = json.loads("""{
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
        }""")
        self.personality.check_container(self.personality, config)

    def test_extraKeys(self):
        """
        A component with extra keys will fail.
        """
        config = json.loads("""{
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
        }""")
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            self.personality.check_container(self.personality, config)

        self.assertIn("encountered unknown attribute 'woooooo'", str(e.exception))

    def test_requiredKeys(self):
        """
        A component with missing keys fails.
        """
        config = json.loads("""{
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
        }""")
        with self.assertRaises(checkconfig.InvalidConfigException) as e:
            self.personality.check_container(self.personality, config)

        self.assertIn("invalid component configuration - missing mandatory attribute 'transport'", str(e.exception))


class CheckEndpointTests(TestCase):
    """
    check_listening_endpoint and check_connecting_endpoint
    """

    def setUp(self):
        self.personality = _DEFAULT_PERSONALITY_CLASS
        return super(TestCase, self).setUp()

    def test_twisted_client_error(self):
        config = {
            "type": "twisted",
            "client_string": 1000,
        }

        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_connecting_endpoint(self.personality, config)
        self.assertTrue("in Twisted endpoint must be str" in str(ctx.exception))

    def test_twisted_server_error(self):
        config = {
            "type": "twisted",
            "server_string": 1000,
        }

        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_listening_endpoint(self.personality, config)
        self.assertTrue("in Twisted endpoint must be str" in str(ctx.exception))

    def test_twisted_server_missing_arg(self):
        config = {"type": "twisted"}

        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_listening_endpoint(self.personality, config)
        self.assertTrue("mandatory attribute 'server_string'" in str(ctx.exception))

    def test_twisted_client_missing_arg(self):
        config = {"type": "twisted"}

        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_connecting_endpoint(self.personality, config)
        self.assertTrue("mandatory attribute 'client_string'" in str(ctx.exception))


class CheckWebsocketTests(TestCase):
    def setUp(self):
        self.personality = _DEFAULT_PERSONALITY_CLASS
        return super(TestCase, self).setUp()

    def test_tiny_timeout_auto_ping(self):
        options = dict(auto_ping_timeout=12)

        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options(options)

        self.assertTrue("'auto_ping_timeout' is in milliseconds" in str(ctx.exception))

    #
    # WebSocket compression options (#2250). check_websocket_compression() was an
    # empty stub, so malformed compression config was silently accepted. The
    # permissible deflate values mirror autobahn's PerMessageDeflateMixin:
    # window bits 9..15 (plus 0 = "not requested" for request_max_window_bits)
    # and memory level 1..9.
    #

    def test_compression_must_be_dict(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": "nope"}})
        self.assertIn("deflate", str(ctx.exception))

    def test_compression_unknown_codec(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"bogus": {}}})
        self.assertIn("bogus", str(ctx.exception))

    def test_compression_deflate_unknown_attribute(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": {"bogus": 1}}})
        self.assertIn("bogus", str(ctx.exception))

    def test_compression_deflate_bad_attribute_type(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": {"no_context_takeover": "yes"}}})
        self.assertIn("no_context_takeover", str(ctx.exception))

    def test_compression_deflate_bad_max_window_bits(self):
        # 8 is not a permissible deflate window size (9..15)
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": {"max_window_bits": 8}}})
        self.assertIn("max_window_bits", str(ctx.exception))

    def test_compression_deflate_bad_request_max_window_bits(self):
        # 16 is out of range; 0 ("not requested") and 9..15 are the valid values
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": {"request_max_window_bits": 16}}})
        self.assertIn("request_max_window_bits", str(ctx.exception))

    def test_compression_deflate_bad_memory_level(self):
        # 10 is out of range (1..9)
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            checkconfig.check_websocket_options({"compression": {"deflate": {"memory_level": 10}}})
        self.assertIn("memory_level", str(ctx.exception))

    def test_compression_deflate_valid(self):
        # a fully-specified, valid deflate block is accepted
        checkconfig.check_websocket_options(
            {
                "compression": {
                    "deflate": {
                        "request_no_context_takeover": True,
                        "request_max_window_bits": 11,
                        "no_context_takeover": False,
                        "max_window_bits": 15,
                        "memory_level": 4,
                    }
                }
            }
        )

    def test_compression_deflate_request_max_window_bits_zero(self):
        # 0 means "do not request a window size" and must be accepted
        checkconfig.check_websocket_options({"compression": {"deflate": {"request_max_window_bits": 0}}})

    def test_compression_deflate_empty(self):
        # an empty deflate block (all defaults) is valid
        checkconfig.check_websocket_options({"compression": {"deflate": {}}})

    #
    # max_frame_size range validation (#2253). It was type-checked only, so a
    # negative value was accepted — and autobahn only enforces frames with
    # ``0 < maxFramePayloadSize < length``, so a negative value silently
    # DISABLES the limit rather than tightening it.
    #

    def test_max_frame_size_negative_rejected(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_websocket_options({"max_frame_size": -1})

    def test_max_frame_size_over_range_rejected(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_websocket_options({"max_frame_size": 64 * 1024 * 1024 + 1})

    def test_max_frame_size_zero_allowed(self):
        # 0 is the documented "unlimited" spelling
        checkconfig.check_websocket_options({"max_frame_size": 0})

    def test_max_frame_size_positive_allowed(self):
        checkconfig.check_websocket_options({"max_frame_size": 65536})

    def test_max_message_size_zero_allowed(self):
        # 0 is the documented "unlimited" spelling for WebSocket max_message_size
        # and a valid autobahn value; the validator must accept it (#2254).
        checkconfig.check_websocket_options({"max_message_size": 0})

    def test_max_message_size_negative_rejected(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_websocket_options({"max_message_size": -1})


class CheckRealmTests(TestCase):
    """
    Tests for check_router_realm, check_router_realm_role
    """

    def setUp(self):
        self.personality = _DEFAULT_PERSONALITY_CLASS
        return super(TestCase, self).setUp()

    def test_dynamic_authorizer(self):
        config_realm = {"name": "realm1", "roles": [{"name": "dynamic", "authorizer": "com.example.foo"}]}

        self.personality.check_router_realm(self.personality, config_realm)

    def test_static_permissions(self):
        config_realm = {
            "name": "realm1",
            "roles": [
                {
                    "name": "backend",
                    "permissions": [
                        {"uri": "*", "allow": {"publish": True, "subscribe": True, "call": True, "register": True}}
                    ],
                }
            ],
        }

        self.personality.check_router_realm(self.personality, config_realm)

    def test_static_permissions_invalid_uri(self):
        config_realm = {
            "name": "realm1",
            "roles": [
                {
                    "name": "backend",
                    "permissions": [
                        {
                            "uri": "foo bar 666",
                            "allow": {"publish": True, "subscribe": True, "call": True, "register": True},
                        }
                    ],
                }
            ],
        }

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )

    def test_static_permissions_and_authorizer(self):
        config_realm = {
            "name": "realm1",
            "roles": [
                {
                    "name": "backend",
                    "authorizer": "com.example.foo",
                    "permissions": [],
                }
            ],
        }

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )

    def test_static_permissions_isnt_list(self):
        config_realm = {
            "name": "realm1",
            "roles": [
                {
                    "name": "backend",
                    "permissions": {},
                }
            ],
        }

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )

    def test_static_permissions_not_dict(self):
        config_realm = {"name": "realm1", "roles": [{"name": "backend", "permissions": ["not a dict"]}]}

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )

    def test_static_permissions_lacks_uri(self):
        config_realm = {
            "name": "realm1",
            "roles": [
                {
                    "name": "backend",
                    "permissions": [{"allow": {"publish": True, "subscribe": True, "call": True, "register": True}}],
                }
            ],
        }

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )

    def test_static_permissions_uri_not_a_string(self):
        config_realm = {"name": "realm1", "roles": [{"name": "backend", "permissions": [{"uri": {}}]}]}

        self.assertRaises(
            checkconfig.InvalidConfigException,
            self.personality.check_router_realm,
            self.personality,
            config_realm,
        )


class CheckOnion(TestCase):
    def setUp(self):
        self.personality = _DEFAULT_PERSONALITY_CLASS
        return super(TestCase, self).setUp()

    def test_unknown_attr(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_listening_endpoint_onion(
                self.personality,
                {
                    "type": "onion",
                    "foo": 42,
                },
            )
        self.assertIn("unknown attribute", str(ctx.exception))

    def test_success(self):
        self.personality.check_listening_endpoint_onion(
            self.personality,
            {
                "type": "onion",
                "private_key_file": "something",
                "port": 1234,
                "tor_control_endpoint": {
                    "type": "unix",
                    "path": "/dev/null",
                },
            },
        )

    def test_port_wrong_type(self):
        with self.assertRaises(checkconfig.InvalidConfigException) as ctx:
            self.personality.check_listening_endpoint_onion(
                self.personality,
                {
                    "type": "onion",
                    "port": "1234",
                },
            )
        self.assertIn("invalid type", str(ctx.exception))
        self.assertIn("encountered for attribute 'port'", str(ctx.exception))


class CheckRawsocketTests(TestCase):
    """
    RawSocket ``max_message_size`` must be validated over the range the WAMP
    RawSocket protocol can actually negotiate — [512, 16 MB] — not the wider
    [1, 64 MB] shared with WebSocket. A value in the gap passes ``crossbar
    check`` but then makes autobahn's factory ``AssertionError`` at transport
    start (crossbar #2252).
    """

    def test_rejects_below_512(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_rawsocket_options({"max_message_size": 100})

    def test_rejects_just_below_512(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_rawsocket_options({"max_message_size": 511})

    def test_rejects_above_16mb(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_rawsocket_options({"max_message_size": 32000000})

    def test_rejects_just_above_16mb(self):
        with self.assertRaises(checkconfig.InvalidConfigException):
            checkconfig.check_rawsocket_options({"max_message_size": 2**24 + 1})

    def test_accepts_min_512(self):
        # boundary: exactly the RawSocket minimum (2**9) is valid
        checkconfig.check_rawsocket_options({"max_message_size": 512})

    def test_accepts_max_16mb(self):
        # boundary: exactly the RawSocket maximum (2**24) is valid
        checkconfig.check_rawsocket_options({"max_message_size": 2**24})

    def test_websocket_range_unaffected(self):
        # the RawSocket split must not narrow WebSocket, which still allows up to
        # 64 MB (a value invalid for RawSocket but valid for WebSocket).
        checkconfig.check_websocket_options({"max_message_size": 32 * 1024 * 1024})
