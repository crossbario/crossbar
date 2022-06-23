###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function

from autobahn.twisted.wamp import ApplicationSession

# these are helper-components for various tests.

# they are *not* in the test_*.py files because those don't import in
# the test-system unless we install py.test, pytest-cov,
# pytest-twitsed and enable at least the Twisted plugin so that
# "pytest.inlineCallbacks" is available (for import)


class EmptyComponent(ApplicationSession):
    """
    A component that does nothing.
    """


class ErrorComponent(ApplicationSession):
    """
    A component that throws on construction.
    """
    def __init__(self, *args, **kw):
        raise RuntimeError("ErrorComponent always fails")
