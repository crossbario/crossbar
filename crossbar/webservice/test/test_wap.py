#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from twisted.trial.unittest import TestCase

from werkzeug.routing import Map, Rule
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template

from crossbar.webservice.wap import WapResource


class WapTestCase(TestCase):
    """
    Tests for :class:`crossbar.webservice.wap.WapResource`.
    """

    _WAP1 = {
        "type":
        "wap",
        "templates":
        "../templates",
        "sandbox":
        True,
        "routes": [{
            "path": "/greeting/<name>",
            "method": "GET",
            "call": "com.example.greeting",
            "render": "greeting.html"
        }, {
            "path": "/product/<int:product_id>/<report>/<int:year>/<int:month>",
            "method": "GET",
            "call": "com.example.get_product_report",
            "render": "product_report.html"
        }],
        "wamp": {
            "realm": "realm1",
            "authrole": "anonymous"
        }
    }

    def setUp(self):
        self._templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self._jinja_env = Environment(loader=FileSystemLoader(self._templates_dir), autoescape=True)

    def test_map_adapter(self):
        # https://werkzeug.palletsprojects.com/en/2.1.x/routing/#werkzeug.routing.MapAdapter.match
        test_map = Map()
        url = '/reports/product/<int:product_id>/<report>/<int:year>/<int:month>'
        endpoint = 'endpoint1'
        rule = Rule(url, methods=['GET'], endpoint=endpoint)
        test_map.add(rule)
        test_adapter = test_map.bind('localhost', '/')

        test_url = '/reports/product/123/total/2016/12'
        test_data = {'product_id': 123, 'report': 'total', 'year': 2016, 'month': 12}

        _endpoint, _kwargs = test_adapter.match(test_url, method='GET', query_args={})

        self.assertEqual(_endpoint, endpoint)
        self.assertEqual(_kwargs, test_data)

    def test_map_adapter_factory(self):

        map_adapter = WapResource._create_map_adapter(self._jinja_env, self._WAP1, 'localhost', 'reports')

        test_url = '/reports/product/123/total/2016/12'
        test_data = {'product_id': 123, 'report': 'total', 'year': 2016, 'month': 12}
        _endpoint, _kwargs = map_adapter.match(test_url, method='GET', query_args={})

        # ('com.example.get_product_report', <Template 'product_report.html'>) != 'localhost'

        self.assertEqual(_endpoint[0], 'com.example.get_product_report')
        self.assertIsInstance(_endpoint[1], Template)
        self.assertEqual(_kwargs, test_data)
