Testing with Autobahn|Python Examples
======================================

.. contents:: :local:

Overview
--------

Crossbar.io includes integration tests that run the comprehensive Autobahn|Python example suite to verify compatibility and functionality between the router and client library implementations.

These tests execute 28 WAMP examples covering both **Twisted** (14 examples) and **asyncio** (14 examples) backends, testing **PubSub** and **RPC** patterns across both **WebSocket** and **RawSocket** transports. The test suite provides detailed categorization and reporting with pass/fail statistics.

Running the Tests
-----------------

Local Development
~~~~~~~~~~~~~~~~~

To run the integration tests locally:

.. code-block:: bash

   # From the crossbar repository
   cd ~/work/wamp/crossbar
   just test-integration-ab-examples cpy311

**Requirements:**

* Port 8080 must be available (no other crossbar instance running)
* Autobahn|Python repository accessible (defaults to ``../autobahn-python``)

**Path Configuration (3 methods):**

1. **Default (sibling directory)**:

   .. code-block:: bash

      cd ~/work/wamp
      git clone https://github.com/crossbario/autobahn-python.git
      git clone https://github.com/crossbario/crossbar.git
      cd crossbar
      just test-integration-ab-examples cpy311

2. **Environment variable**:

   .. code-block:: bash

      export AB_PYTHON_PATH=/path/to/autobahn-python
      just test-integration-ab-examples cpy311

3. **Recipe parameter**:

   .. code-block:: bash

      just test-integration-ab-examples cpy311 /path/to/autobahn-python

Test Output
~~~~~~~~~~~

The test provides comprehensive pass/fail output with detailed categorization:

.. code-block:: none

   ========================================================================
   Crossbar Integration Test: Autobahn|Python Examples
   ========================================================================
   Crossbar venv: cpy311
   Autobahn|Python path: /home/user/work/wamp/autobahn-python

   ✓ Found run-all-examples.py and router configuration

   ========================================================================
   Test 1: RawSocket Transport (rs://127.0.0.1:8080)
   ========================================================================
   Note: run-all-examples.py starts its own crossbar instance

   [... individual example execution output ...]

   ================================================================================
   Test Results Summary
   ================================================================================

   Individual Examples:
   --------------------------------------------------------------------------------
   ✓ twisted  overview ./twisted/wamp/overview
   ✓ twisted  pubsub   ./twisted/wamp/pubsub/basic/
   ✓ twisted  pubsub   ./twisted/wamp/pubsub/complex/
   ✓ twisted  pubsub   ./twisted/wamp/pubsub/decorators/
   ✓ twisted  pubsub   ./twisted/wamp/pubsub/options/
   ✓ twisted  pubsub   ./twisted/wamp/pubsub/unsubscribe/
   ✓ twisted  rpc      ./twisted/wamp/rpc/timeservice/
   ✓ twisted  rpc      ./twisted/wamp/rpc/slowsquare/
   ✓ twisted  rpc      ./twisted/wamp/rpc/progress/
   ✓ twisted  rpc      ./twisted/wamp/rpc/options/
   ✓ twisted  rpc      ./twisted/wamp/rpc/errors/
   ✓ twisted  rpc      ./twisted/wamp/rpc/decorators/
   ✓ twisted  rpc      ./twisted/wamp/rpc/complex/
   ✓ twisted  rpc      ./twisted/wamp/rpc/arguments/
   ✓ asyncio  overview ./asyncio/wamp/overview
   ✓ asyncio  pubsub   ./asyncio/wamp/pubsub/unsubscribe/
   ✓ asyncio  pubsub   ./asyncio/wamp/pubsub/options/
   ✓ asyncio  pubsub   ./asyncio/wamp/pubsub/decorators/
   ✓ asyncio  pubsub   ./asyncio/wamp/pubsub/complex/
   ✓ asyncio  pubsub   ./asyncio/wamp/pubsub/basic/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/timeservice/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/slowsquare/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/progress/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/options/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/errors/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/decorators/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/complex/
   ✓ asyncio  rpc      ./asyncio/wamp/rpc/arguments/

   By Backend:
   --------------------------------------------------------------------------------
   ✓ twisted : 14/14 passed, 0 failed
   ✓ asyncio : 14/14 passed, 0 failed

   By WAMP Feature:
   --------------------------------------------------------------------------------
   ✓ overview: 2/2 passed, 0 failed
   ✓ pubsub  : 10/10 passed, 0 failed
   ✓ rpc     : 16/16 passed, 0 failed

   ================================================================================
   ✓ ALL TESTS PASSED
     Total: 28/28 examples completed successfully
   ================================================================================

   ✓ RawSocket transport tests passed

   ========================================================================
   Test 2: WebSocket Transport (ws://127.0.0.1:8080/ws)
   ========================================================================
   Note: run-all-examples.py starts its own crossbar instance

   [... similar detailed output for WebSocket transport ...]

   ✓ WebSocket transport tests passed

   ========================================================================
   Summary
   ========================================================================
   ✅ ALL INTEGRATION TESTS PASSED
      - RawSocket transport: PASS
      - WebSocket transport: PASS

Examples Tested
---------------

Twisted Examples (14 total)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The test suite covers 14 Twisted examples: 1 overview, 5 pubsub (TLS skipped on RawSocket), and 8 RPC examples.

**WAMP Overview**

.. code-block:: none

   ./twisted/wamp/overview

Basic WAMP client demonstrating connection, pub/sub, and RPC.

**PubSub Patterns** (5 examples tested)

.. code-block:: none

   ./twisted/wamp/pubsub/basic/
   ./twisted/wamp/pubsub/complex/
   ./twisted/wamp/pubsub/decorators/
   ./twisted/wamp/pubsub/options/
   ./twisted/wamp/pubsub/tls/
   ./twisted/wamp/pubsub/unsubscribe/

* **basic**: Simple publish/subscribe
* **complex**: Pattern-based subscriptions, wildcards
* **decorators**: Using ``@subscribe`` decorator patterns
* **options**: Publisher/subscriber options (exclude, eligible, etc.)
* **tls**: Secure WebSocket connections
* **unsubscribe**: Dynamic subscription management

**RPC Patterns** (8 examples)

.. code-block:: none

   ./twisted/wamp/rpc/timeservice/
   ./twisted/wamp/rpc/slowsquare/
   ./twisted/wamp/rpc/progress/
   ./twisted/wamp/rpc/options/
   ./twisted/wamp/rpc/errors/
   ./twisted/wamp/rpc/decorators/
   ./twisted/wamp/rpc/complex/
   ./twisted/wamp/rpc/arguments/

* **timeservice**: Simple RPC call/register
* **slowsquare**: Asynchronous RPC with delays
* **progress**: Progressive call results
* **options**: Caller/callee options (disclose caller, timeout, etc.)
* **errors**: Custom error handling
* **decorators**: Using ``@register`` decorator patterns
* **complex**: Advanced RPC patterns
* **arguments**: Positional and keyword arguments

Asyncio Examples (14 total)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The test suite covers 14 asyncio examples: 1 overview, 5 pubsub (TLS skipped on RawSocket), and 8 RPC examples.

**WAMP Overview**

.. code-block:: none

   ./asyncio/wamp/overview

Basic WAMP client demonstrating connection, pub/sub, and RPC using asyncio.

**PubSub Patterns** (5 examples tested)

.. code-block:: none

   ./asyncio/wamp/pubsub/basic/
   ./asyncio/wamp/pubsub/complex/
   ./asyncio/wamp/pubsub/decorators/
   ./asyncio/wamp/pubsub/options/
   ./asyncio/wamp/pubsub/tls/
   ./asyncio/wamp/pubsub/unsubscribe/

Same patterns as Twisted, but using asyncio/await syntax.

**RPC Patterns** (8 examples)

.. code-block:: none

   ./asyncio/wamp/rpc/timeservice/
   ./asyncio/wamp/rpc/slowsquare/
   ./asyncio/wamp/rpc/progress/
   ./asyncio/wamp/rpc/options/
   ./asyncio/wamp/rpc/errors/
   ./asyncio/wamp/rpc/decorators/
   ./asyncio/wamp/rpc/complex/
   ./asyncio/wamp/rpc/arguments/

Same patterns as Twisted, but using asyncio/await syntax.

Test Architecture
-----------------

Test Flow
~~~~~~~~~

1. **Router Startup**: The ``run-all-examples.py`` script starts its own Crossbar.io instance from ``autobahn-python/examples/router/.crossbar/``

2. **Example Execution**: For each example directory:

   * Start backend.py (registers procedures, subscribes to topics)
   * Wait 1 second
   * Start frontend.py (calls procedures, publishes events)
   * Run for 3 seconds
   * Terminate both processes

3. **Transport Testing**: The entire suite runs twice:

   * First with RawSocket transport (``rs://127.0.0.1:8080``)
   * Then with WebSocket transport (``ws://127.0.0.1:8080/ws``)

4. **Router Shutdown**: Crossbar.io is stopped and restarted between transport tests

Router Configuration
~~~~~~~~~~~~~~~~~~~~

The test uses ``autobahn-python/examples/router/.crossbar/config.json`` which provides:

* **Realm**: ``crossbardemo`` with anonymous authentication
* **Transports**:

  * MQTT on port 1883
  * Universal transport on port 8080 (both RawSocket and WebSocket)
  * WebSocket with TLS on port 8083
  * Unix socket transport

* **Features**:

  * Event history
  * Multiple authentication methods (WAMP-CRA, SCRAM, Cryptosign)
  * Dynamic authorization via authorizer component
  * Web status interface

Coverage
--------

The integration tests verify:

**WAMP Features**

* ✓ Basic publish/subscribe
* ✓ Pattern-based subscriptions
* ✓ Subscriber options (exclude, eligible)
* ✓ Publisher options (exclude, eligible, acknowledge)
* ✓ Basic RPC (call/register)
* ✓ Progressive call results
* ✓ Caller/callee options
* ✓ Custom error handling
* ✓ Argument passing (positional and keyword)
* ✓ Decorator syntax (``@subscribe``, ``@register``)

**Transports**

* ✓ WebSocket (``ws://``)
* ✓ RawSocket (``rs://``)
* ✓ TLS/SSL connections

**Backends**

* ✓ Twisted (callback-based)
* ✓ Asyncio (async/await)

**Serializers**

The router supports multiple serializers tested by the examples:

* CBOR
* MessagePack
* UBJson
* JSON

Known Issues
------------

time.clock() Deprecation
~~~~~~~~~~~~~~~~~~~~~~~~~

Some examples may show warnings about ``time.clock()`` being deprecated in Python 3.8+:

.. code-block:: none

   AttributeError: module 'time' has no attribute 'clock'

This is a minor issue in the Autobahn|Python examples (not Crossbar.io) and doesn't affect test results. The examples will be updated in a future Autobahn|Python release to use ``time.perf_counter()`` instead.

CI/CD Integration
-----------------

For GitHub Actions workflows, the test can be configured with:

.. code-block:: yaml

   - name: Checkout autobahn-python
     uses: actions/checkout@v4
     with:
       repository: crossbario/autobahn-python
       path: autobahn-python

   - name: Run integration tests
     run: |
       export AB_PYTHON_PATH=${{ github.workspace }}/autobahn-python
       just test-integration-ab-examples cpy311

Alternatively, use the default sibling directory layout:

.. code-block:: yaml

   - name: Checkout crossbar
     uses: actions/checkout@v4
     with:
       repository: crossbario/crossbar
       path: crossbar

   - name: Checkout autobahn-python
     uses: actions/checkout@v4
     with:
       repository: crossbario/autobahn-python
       path: autobahn-python

   - name: Run integration tests
     working-directory: crossbar
     run: just test-integration-ab-examples cpy311

Benefits for Users
------------------

**Confidence**: These tests provide confidence that Crossbar.io correctly implements the WAMP protocol and works with real-world client applications.

**Examples**: The Autobahn|Python examples serve as reference implementations for common WAMP patterns.

**Compatibility**: Running the full example suite ensures compatibility between router and client library versions.

**Regression Detection**: The tests catch regressions in WAMP feature support across releases.

**Documentation**: The examples demonstrate best practices for WAMP application development.

See Also
--------

* :doc:`Getting-Started` - Getting started with Crossbar.io
* :doc:`Programming-Guide` - WAMP programming patterns
* `Autobahn|Python Examples <https://github.com/crossbario/autobahn-python/tree/master/examples>`_ - Full example source code
* `WAMP Specification <https://wamp-proto.org/>`_ - WAMP protocol details
