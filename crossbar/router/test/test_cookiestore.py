from crossbar.router.cookiestore import CookieStoreFileBacked
import json
import tempfile
import unittest
import time
from datetime import datetime
from autobahn import util


class TestCookieStore(unittest.TestCase):

    def write_cookies_to_file(self, cookies, file):
        for cookie in cookies:
            file.write((json.dumps(cookie) + '\n').encode('utf-8'))
        file.flush()

    def read_cookies_from_file(self, file):
        file.seek(0)
        cookies = list(map(lambda x: json.loads(x.decode('utf-8')), file.readlines()))
        cookies.sort(key=lambda x: x['id'])
        return cookies

    def test_purge_on_startup(self):

        created_time = util.utcnow()

        original = [
            {
                "id": "thisIsAnID",
                "created": created_time,
                "max_age": 604800,
                "authid": "example.authid",
                "authrole": "example.authrole",
                "authrealm": "example.authrealm",
                "authmethod": "example.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnotherID",
                "created": created_time,
                "max_age": 604800,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authrealm": "example.other.authrealm",
                "authmethod": "example.other.authmethod",
                "authextra": {"a": "b"},
            },
            {
                "id": "thisIsAnID",
                "modified": created_time,
                "max_age": 604800,
                "authid": "example.second.authid",
                "authrole": "example.second.authrole",
                "authrealm": "example.second.authrealm",
                "authmethod": "example.second.authmethod",
                "authextra": {},
            }
        ]

        expected = [
            {
                "id": "thisIsAnID",
                "created": created_time,
                "max_age": 604800,
                "authid": "example.second.authid",
                "authrole": "example.second.authrole",
                "authrealm": "example.second.authrealm",
                "authmethod": "example.second.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnotherID",
                "created": created_time,
                "max_age": 604800,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authrealm": "example.other.authrealm",
                "authmethod": "example.other.authmethod",
                "authextra": {"a": "b"},
            }
        ]

        with tempfile.NamedTemporaryFile() as fp:
            self.write_cookies_to_file(original, fp)

            config = {
                'store': {
                    'type': 'file',
                    'filename': fp.name,
                    'purge_on_startup': True
                }
            }

            CookieStoreFileBacked(fp.name, config)

            actual = self.read_cookies_from_file(fp)
            self.assertEqual(actual, expected)

    def test_purge_on_startup_default_is_false(self):

        original = [
            {
                "id": "thisIsAnID",
                "created": "2016-03-02T20:23:00.000Z",
                "max_age": 604800,
                "authid": "example.authid",
                "authrole": "example.authrole",
                "authrealm": "example.authrealm",
                "authmethod": "example.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnID",
                "modified": "2016-03-02T20:24:00.000Z",
                "max_age": 604800,
                "authid": "example.second.authid",
                "authrole": "example.second.authrole",
                "authrealm": "example.second.authrealm",
                "authmethod": "example.second.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnotherID",
                "created": "2016-03-02T20:23:30.000Z",
                "max_age": 604800,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authrealm": "example.other.authrealm",
                "authmethod": "example.other.authmethod",
                "authextra": {},
            }
        ]

        with tempfile.NamedTemporaryFile() as fp:
            self.write_cookies_to_file(original, fp)

            config = {
                'store': {
                    'type': 'file',
                    'filename': fp.name
                }
            }

            CookieStoreFileBacked(fp.name, config)

            actual = self.read_cookies_from_file(fp)

            self.assertEqual(actual, original)

    def test_purge_on_startup_delete_expired_cookies(self):
        max_age = 300
        now = time.time()
        valid_time = util.utcstr(datetime.fromtimestamp(now))
        expired_time = util.utcstr(datetime.fromtimestamp(now - max_age - 10))

        original = [
            {
                "id": "thisIsAnID",
                "created": expired_time,
                "max_age": max_age,
                "authid": "example.authid",
                "authrole": "example.authrole",
                "authrealm": "example.authrealm",
                "authmethod": "example.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnotherID",
                "created": valid_time,
                "max_age": max_age,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authrealm": "example.other.authrealm",
                "authmethod": "example.other.authmethod",
                "authextra": {},
            },
            {
                "id": "thisIsAnID",
                "modified": valid_time,
                "max_age": max_age,
                "authid": "example.second.authid",
                "authrole": "example.second.authrole",
                "authrealm": "example.second.authrealm",
                "authmethod": "example.second.authmethod",
                "authextra": {},
            }
        ]

        expected = [
            {
                "id": "thisIsAnotherID",
                "created": valid_time,
                "max_age": max_age,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authrealm": "example.other.authrealm",
                "authmethod": "example.other.authmethod",
                "authextra": {},
            },
        ]

        with tempfile.NamedTemporaryFile() as fp:
            self.write_cookies_to_file(original, fp)

            config = {
                'store': {
                    'type': 'file',
                    'filename': fp.name,
                    'purge_on_startup': True
                }
            }

            CookieStoreFileBacked(fp.name, config)

            actual = self.read_cookies_from_file(fp)
            self.assertEqual(actual, expected)
