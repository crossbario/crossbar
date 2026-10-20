#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from types import SimpleNamespace

from twisted.internet.defer import Deferred
from twisted.trial import unittest

from crossbar.edge.worker.xbr._marketmaker import MarketMaker
from crossbar.node.controller import NodeController


class GetWorkersFilterTypesTests(unittest.TestCase):
    """
    ``NodeController.get_workers()`` checks ``filter_types``: ``None`` or a list of str (#2290).
    """

    def setUp(self):
        self.controller = SimpleNamespace(
            _workers={"worker001": SimpleNamespace(TYPE="router"), "worker002": SimpleNamespace(TYPE="container")}
        )

    def test_valid(self):
        self.assertEqual(NodeController.get_workers(self.controller), ["worker001", "worker002"])
        self.assertEqual(NodeController.get_workers(self.controller, filter_types=None), ["worker001", "worker002"])
        self.assertEqual(NodeController.get_workers(self.controller, filter_types=["router"]), ["worker001"])

    def test_non_str_element_rejected(self):
        self.assertRaises(AssertionError, NodeController.get_workers, self.controller, filter_types=["router", 23])

    def test_non_list_rejected(self):
        self.assertRaises(AssertionError, NodeController.get_workers, self.controller, filter_types="router")


class PlaceOfferCategoriesTests(unittest.TestCase):
    """
    ``MarketMaker.place_offer()`` checks ``categories``: ``None`` or a dict with str keys and str
    values (#2290).
    """

    def _place_offer(self, categories):
        # all other arguments are valid, so the categories check is the first one that can fail
        coro = MarketMaker.place_offer(
            None,
            os.urandom(16),
            os.urandom(16),
            "com.example.data",
            0,
            os.urandom(20),
            os.urandom(65),
            categories=categories,
        )
        return self.assertFailure(Deferred.fromCoroutine(coro), AssertionError)

    def _check_rejected(self, categories):
        d = self._place_offer(categories)
        d.addCallback(lambda e: self.assertIn("invalid categories", str(e)))
        return d

    def test_non_dict_rejected(self):
        return self._check_rejected(["fruit"])

    def test_non_str_key_rejected(self):
        return self._check_rejected({23: "apple"})

    def test_non_str_value_rejected(self):
        return self._check_rejected({"fruit": 23})
