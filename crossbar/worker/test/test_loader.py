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

from __future__ import absolute_import, division, print_function

from autobahn.wamp.exception import ApplicationError

from crossbar.test import TestCase
from crossbar.worker import _appsession_loader


class AppSessionLoaderTests(TestCase):
    """
    Tests for C{_appsession_loader}.
    """

    def test_unknown_types(self):
        """
        An unknown type will raise an exception.
        """
        config = {
            "type": "kjdfgdbfls",
        }

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(
            ("invalid component type 'kjdfgdbfls'"),
            str(e.exception.args[0]))

    def test_class_standard(self):
        """
        You can load a standard class.
        """
        config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.goodclass.AppSession"
        }

        klass = _appsession_loader(config)

        from .examples.goodclass import AppSession
        self.assertIs(klass, AppSession)

    def test_class_non_applicationsession(self):
        """
        Loading a class which does not subclass AppSession fails.
        """
        config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.badclass.AppSession"
        }

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(
            ("session not derived of ApplicationSession"),
            str(e.exception.args[0]))

    def test_class_importerror(self):
        """
        Loading a class which has an import error upon import raises that
        error.
        """
        config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.importerror.AppSession"
        }

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(
            ("Failed to import class 'crossbar.worker.test.examples.importerr"
             "or.AppSession'"),
            str(e.exception.args[0]))

        s = str(e.exception.args[0])
        self.assertTrue('ImportError' in s or 'ModuleNotFoundError' in s)

    def test_class_syntaxerror(self):
        """
        Loading a class which has a SyntaxError raises that up.
        """
        config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.syntaxerror.AppSession"
        }

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(
            ("Failed to import class 'crossbar.worker.test.examples.syntaxerr"
             "or.AppSession'"),
            str(e.exception.args[0]))
        self.assertIn(
            ("SyntaxError"),
            str(e.exception.args[0]))
