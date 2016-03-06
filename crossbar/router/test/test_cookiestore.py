from crossbar.router.cookiestore import CookieStoreFileBacked
import json
import tempfile
import unittest


class TestCookieStore(unittest.TestCase):

    def test_purge_on_startup(self):

        original = b"""{"id":"thisIsAnID","created":"2016-03-02T20:23:00.000Z","max_age":604800,"authid":"example.authid","authrole":"example.authrole","authmethod":"example.authmethod"}
{"id":"thisIsAnotherID","created":"2016-03-02T20:23:30.000Z","max_age":604800,"authid":"example.other.authid","authrole":"example.other.authrole","authmethod":"example.other.authmethod"}
{"id":"thisIsAnID","modified":"2016-03-02T20:24:00.000Z","max_age":604800,"authid":"example.second.authid","authrole":"example.second.authrole","authmethod":"example.second.authmethod"}
"""
        expected = [
            {
                "id": "thisIsAnID",
                "created": "2016-03-02T20:23:00.000Z",
                "max_age": 604800,
                "authid": "example.second.authid",
                "authrole": "example.second.authrole",
                "authmethod": "example.second.authmethod"
            },
            {
                "id": "thisIsAnotherID",
                "created": "2016-03-02T20:23:30.000Z",
                "max_age": 604800,
                "authid": "example.other.authid",
                "authrole": "example.other.authrole",
                "authmethod": "example.other.authmethod"
            }
        ]

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(original)
            fp.flush()

            config = {
                'store': {
                    'type': 'file',
                    'filename': fp.name,
                    'purge_on_startup': True
                }
            }

            CookieStoreFileBacked(fp.name, config)

            fp.seek(0)
            actual = list()
            for line in fp.readlines():
                cookie = json.loads(line.decode('utf-8'))
                actual.append(cookie)

            actual.sort(key=lambda x: x['id'])
            self.assertEqual(actual, expected)

    def test_purge_on_startup_default_is_false(self):

        original = b"""{"id":"thisIsAnID","created":"2016-03-02T20:23:00.000Z","max_age":604800,"authid":"example.authid","authrole":"example.authrole","authmethod":"example.authmethod"}
{"id":"thisIsAnotherID","created":"2016-03-02T20:23:30.000Z","max_age":604800,"authid":"example.other.authid","authrole":"example.other.authrole","authmethod":"example.other.authmethod"}
{"id":"thisIsAnID","modified":"2016-03-02T20:24:00.000Z","max_age":604800,"authid":"example.second.authid","authrole":"example.second.authrole","authmethod":"example.second.authmethod"}
"""

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(original)
            fp.flush()

            config = {
                'store': {
                    'type': 'file',
                    'filename': fp.name
                }
            }

            CookieStoreFileBacked(fp.name, config)

            fp.seek(0)
            self.assertEqual(fp.read(), original)
