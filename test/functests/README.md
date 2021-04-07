Functional Tests
================

These tests perform high-level functional testing of Crossbar.io by
running a (local) crossbar router and performing end-user sorts of
tests.

We use `pytest <http://pytest.org>`_ fixtures for setting up and
tearing down the test Crossbar instance and creating WAMP sessions
joined to it.


Scope of the Tests
------------------

We test the correctness of very high-level functionality; these are
not unit-tests, and should **not** delve into the internals of
Crossbar at all. They also do not try to test at scale; they are
purely to check for correct behavior of specific, high-level features.

All tests are run against a locally-running Crossbar reactor on
``127.0.0.1:6565`` and so will fail if you happen to already be using
that TCP port.

..note::

   For "at scale" tests, use a full installation of ``CTS`` (Crossbar
   Test System) which can run multiple clients and testee sessions and
   processes on multiple machines.


Running the Tests
-----------------

To run the "crossbar tests" (test/functests/cbtests), ensure you've
installed everything in your virtualenv (e.g. local checksouts of
things) and also::

   pip install -r requirements-dev.txt
   pip install -r requirements-min.txt

Then you should be able run, from the top level::

   py.test -svx test/functests/cbtests


To run the "crossbar fabric center tests" (test/functests/cfctests),
install things as above. Additionally, set two environment-variables::

   export CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
   export CROSSBAR_FABRIC_SUPERUSER=~/.crossbarfx/default.pub

...and run the setup script:

   ./test/test_setup.py

This will create a local CFC and pair a few test nodes to it. Then you
should be able to run::

   py.test -svx test/functests/cfctests

(If the tests appear to "hang" while running the first one, something
is wrong in you setup probably. If you see any "real" CFC URLs in the
output, something is wrong).

The py.test flags, `-s` shows all output in real-time, the `-v` does
coloured output of the tests and `-x` causes the run to halt on the
first test that fails.

Other Fun Flags
~~~~~~~~~~~~~~~

You can pass `--venv /tmp/testing` (for example) to re-use the same
testing virtualenv. This will be created if it doesn't exist, but can
save a bunch of time if you're re-running the same tests soon.

Similarly `--no-install` will save more time, if you've "very
recently" created a testing environment (you must also pass `--venv
X`) -- this causes the test suite to not install anything in the
testing venv.

`--coverage` turns on test-coverage

`--slow` causes tests marked as "slow" to no longer be skipped.

`--keep` doesn't delete tempdirs created (e.g. for later analysis)

`--logdebug` turns up the logging to debug in crossbar subprocesses

Things to Keep In Mind
----------------------

 - **DO NOT** import ``twisted.internet.reactor``. If you'd like to call
   reactor methods, simply use the ``reactor`` fixture, like so::

    @pytest.inlineCallbacks
    def test_something(reactor):
        reactor.callLater(...)

 - For any ``test_*()`` method, you **MUST** use ``pytest.inlineCallbacks``
   to decorate and not the "normal" Twisted one; see the
   ``pytest-twisted`` plugin documentation for details (the named
   funcargs don't work otherwise).

 - There is just one Crossbar instance created for the whole test
   run. Play nicely. That means, for example, removing your
   subscriptions and so forth with ``try...finally``

 - Use the ``start_session`` helper to create yourself any number of
   WAMP sessions. Note they are all connected to the one Crossbar test
   instance. (If you just need a single session, there's a
   ``wamp_session`` fixture).


Layout of the Tests
-------------------

The actual tests are grouped into files starting with ``test_`` while
support code is included in ``fixtures.py`` and ``helpers.py``

pytest setup and hooks go in ``conftest.py``
