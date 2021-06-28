#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

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

        self.assertIn(("invalid component type 'kjdfgdbfls'"), str(e.exception.args[0]))

    def test_class_standard(self):
        """
        You can load a standard class.
        """
        config = {"type": "class", "classname": "crossbar.worker.test.examples.goodclass.AppSession"}

        klass = _appsession_loader(config)

        from .examples.goodclass import AppSession
        self.assertIs(klass, AppSession)

    def test_class_non_applicationsession(self):
        """
        Loading a class which does not subclass AppSession fails.
        """
        config = {"type": "class", "classname": "crossbar.worker.test.examples.badclass.AppSession"}

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(("session not derived of ApplicationSession"), str(e.exception.args[0]))

    def test_class_importerror(self):
        """
        Loading a class which has an import error upon import raises that
        error.
        """
        config = {"type": "class", "classname": "crossbar.worker.test.examples.importerror.AppSession"}

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(("Failed to import class 'crossbar.worker.test.examples.importerr"
                       "or.AppSession'"), str(e.exception.args[0]))

        s = str(e.exception.args[0])
        self.assertTrue('ImportError' in s or 'ModuleNotFoundError' in s)

    def test_class_syntaxerror(self):
        """
        Loading a class which has a SyntaxError raises that up.
        """
        config = {"type": "class", "classname": "crossbar.worker.test.examples.syntaxerror.AppSession"}

        with self.assertRaises(ApplicationError) as e:
            _appsession_loader(config)

        self.assertIn(("Failed to import class 'crossbar.worker.test.examples.syntaxerr"
                       "or.AppSession'"), str(e.exception.args[0]))
        self.assertIn(("SyntaxError"), str(e.exception.args[0]))
