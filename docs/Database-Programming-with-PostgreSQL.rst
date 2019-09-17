:orphan:


Database Programming with PostgreSQL
====================================

This chapter covers `PostgreSQL <http://www.postgresql.org/>`__ database
programming from WAMP application components written in Python.

You will need some Python packages to do so. Depending on the Python
implementation and the underlying network framework you plan to use,
this is what we recommend:

+---------------------------------------------+---------------------------------------------------------------------------------------------------------------------------+-----------------------------------------------------------------------------------------------------------------+
| Python / Networking Framework               | `Twisted <http://www.twistedmatrix.com/>`__                                                                               | `asyncio <https://docs.python.org/3/library/asyncio.html>`__                                                    |
+=============================================+===========================================================================================================================+=================================================================================================================+
|   `CPython <https://www.python.org/>`__     | `psycopg2 <https://pypi.python.org/pypi/psycopg2>`__ + `txpostgres <https://pypi.python.org/pypi/txpostgres>`__           | `psycopg2 <https://pypi.python.org/pypi/psycopg2>`__ + `aiopg <https://pypi.python.org/pypi/aiopg>`__           |
+---------------------------------------------+---------------------------------------------------------------------------------------------------------------------------+-----------------------------------------------------------------------------------------------------------------+
|   `PyPy <http://pypy.org/>`__               | `psycopg2cffi <https://pypi.python.org/pypi/psycopg2cffi>`__ + `txpostgres <https://pypi.python.org/pypi/txpostgres>`__   | `psycopg2cffi <https://pypi.python.org/pypi/psycopg2cffi>`__ + `aiopg <https://pypi.python.org/pypi/aiopg>`__   |
+---------------------------------------------+---------------------------------------------------------------------------------------------------------------------------+-----------------------------------------------------------------------------------------------------------------+

Above libraries provide a classic cursor and SQL based API to the
database (like Python DBI 2.0).

If you are looking for an object-relational database adapter, there
obviously is SQLAlchemy. However, the latter is exposing a synchronous
API and does not blend well with the asynchronous frameworks. However,
there is `Twistar <http://findingscience.com/twistar/>`__, a completely
new project for Twisted which can be used with any Twisted supported
relational database and provides a object-relational API.

Drivers
-------

To access PostgreSQL from Python, you will need a **database driver**.
There are multiple drivers (e.g. see
`here <https://wiki.python.org/moin/PostgreSQL>`__ and
`here <https://wiki.postgresql.org/wiki/Python>`__), however, the most
commonly used is `Psycopg <http://initd.org/psycopg/>`__.

**Psycopg** can be used to access PostgreSQL from WAMP application
components written in Python, and running under Twisted or asyncio.

    **Psycopg** wraps the native PostgreSQL C client library
    `libpq <http://www.postgresql.org/docs/devel/static/libpq.html>`__
    as a Python module. It is written as a so-called CPython extension.
    This Python extension system has issues when running on PyPy, which
    is the reason for a variant
    `Psycopg2cffi <https://github.com/chtd/psycopg2cffi>`__. You
    probably should use this on PyPy. It is using
    `CFFI <https://cffi.readthedocs.org/>`__, which is the recommended
    way to access C libraries from PyPy.

Asyncio
-------

Psycopg can be used under asyncio via
`aiopg <https://github.com/aio-libs/aiopg>`__, a wrapper which builds on
Psycopg, exposing an asynchronous interface to the database. For an
introduction, please see the `aiopg
documentation <http://aiopg.readthedocs.org/>`__.

    aiopg will run the underlying PostgreSQL database connection in
    "asynchronous connection mode" and hence does NOT run a background
    thread pool (since it doesn't need to overcome the blocking nature
    of PostgreSQL connection which do not run in asynchronous mode). It
    is comparable to **txpostgres** - which is for Twisted.

Twisted
-------

This chapter describes accessing PostgreSQL databases from
Python/Twisted-based WAMP application components.

Approaches
~~~~~~~~~~

Assuming you have settled on
`psycopg2 <https://pypi.python.org/pypi/psycopg2>`__ (or
`Psycopg2cffi <https://github.com/chtd/psycopg2cffi>`__ when running on
PyPy) as your underlying database driver, there are two options with
Twisted:

1. `twisted.enterprise.adbapi <http://twistedmatrix.com/documents/current/core/howto/rdbms.html>`__
2. `txpostgres <https://pypi.python.org/pypi/txpostgres>`__

The first one is running (blocking) database connections on a background
thread pool and exposes an asynchronous API to applications. It is very
stable, has been around forever and comes built into Twisted. However,
it is using threads.

The second one is running PostgreSQL database connections in
"asynchronous mode". Note that the word "asynchronous" in this case
refers to a PostgreSQL client library / database protocol feature. This
means there will be no threads! Which is great. Less overhead, less
stuff that can go wield.

Twisted adbapi
~~~~~~~~~~~~~~

-  `Twisted RDBMS support <http://twistedmatrix.com/documents/current/core/howto/rdbms.html>`__
-  `twisted.enterprise.adbapi.ConnectionPool <https://twistedmatrix.com/documents/current/api/twisted.enterprise.adbapi.ConnectionPool.html>`__

You'll be interacting with the database via a database connection from
the database connection pool created by Twisted, and run on a background
pool of worker threads. Ther three main functions to use are:

1. `runQuery  <https://twistedmatrix.com/documents/current/api/twisted.enterprise.adbapi.ConnectionPool.html#runQuery>`__:
   Use this to run a single SQL query and get the result.

2.  `runOperation  <https://twistedmatrix.com/documents/current/api/twisted.enterprise.adbapi.ConnectionPool.html#runOperation>`__:
Use this to run a single SQL statement that does not return anything  (such as an ``INSERT``, ``DELETE`` or ``UPDATE`` ).

3.  `runInteraction  <https://twistedmatrix.com/documents/current/api/twisted.enterprise.adbapi.ConnectionPool.html#runInteraction>`__:
Use this to run a series of SQL statements in one SQL transaction.  Any modifications done from within the interaction will be part of  the (single) transaction, and either be committed or rolled back   completely.

A adbapi based database component
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This example uses Twisted adbapi. Name it hello.py remembering that whatever you name it, both the filename and the derived class within must match exactly the value of "classname" dict, a required option of "components" under the "container" section of config.json.

.. code:: python

    import psycopg2

    from twisted.enterprise import adbapi
    from twisted.internet.defer import inlineCallbacks, returnValue

    from autobahn import wamp
    from autobahn.twisted.wamp import ApplicationSession


    class MyDatabaseComponent(ApplicationSession):

       @inlineCallbacks
       def onJoin(self, details):

          ## create a new database connection pool. connections are created lazy (as needed)
          ##
          def onPoolConnectionCreated(conn):
             ## callback fired when Twisted adds a new database connection to the pool.
             ## use this to do any app specific configuration / setup on the connection
             pid = conn.get_backend_pid()
             print("New DB connection created (backend PID {})".format(pid))

          pool = adbapi.ConnectionPool("psycopg2",
                                        host = '127.0.0.1',
                                        port = 5432,
                                        database = 'test',
                                        user = 'testuser',
                                        password = 'testuser',
                                        cp_min = 3,
                                        cp_max = 10,
                                        cp_noisy = True,
                                        cp_openfun = onPoolConnectionCreated,
                                        cp_reconnect = True,
                                        cp_good_sql = "SELECT 1")

          ## we'll be doing all database access via this database connection pool
          ##
          self.db = pool

          ## register all procedures on this class which have been
          ## decorated to register them for remoting.
          ##
          regs = yield self.register(self)
          print("registered {} procedures".format(len(regs)))


       @wamp.register(u'com.example.now.v1')
       def get_dbnow(self):
          ## this variant demonstrates basic usage for running queries

          d = self.db.runQuery("SELECT now()")

          def got(rows):
             res = "{0}".format(rows[0][0])
             return res

          d.addCallback(got)
          return d


       @wamp.register(u'com.example.now.v2')
       @inlineCallbacks
       def get_dbnow_inline(self):
          ## this variant is using inline callbacks which makes code "look synchronous",
          ## nevertheless run asynchronous under the hood

          rows = yield self.db.runQuery("SELECT now()")
          res = "{0}".format(rows[0][0])
          returnValue(res)


       @wamp.register(u'com.example.now.v3')
       def get_dbnow_interaction(self):
          ## this variant runs the query inside a transaction (which might do more,
          ## and still be atomically committed/rolled back)

          def run(txn):
             txn.execute("SELECT now()")
             rows = txn.fetchall()
             res = "{0}".format(rows[0][0])
             return res

          return self.db.runInteraction(run)



    if __name__ == '__main__':
       from autobahn.twisted.wamp import ApplicationRunner

       runner = ApplicationRunner(url = "ws://127.0.0.1:8080/ws", realm = "realm1")
       runner.run(MyDatabaseComponent)

For testing the database component, use the following AutobahnJS
based WAMP client and name it "index.htm". Make sure to place "index.htm" in a folder named "web" alongside your ".crossbar" folder. The example config.json will then find and serve index.htm and call all procedures of component. When
running, you should see the current database time printed to the
JavaScript console three times.

.. code:: html

    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
    </head>
       <body>
       <h1>Hello, my fair database</h1
          <!-- library can be found at https://github.com/crossbario/autobahn-js-browser -->
          <script src="shared/autobahn.min.js">
          </script>
          <script>
             var connection = new autobahn.Connection({
                url: "ws://127.0.0.1:8080/ws",
                realm: "realm1"
             });

             connection.onopen = function (session, details) {
                console.log("Connected");

                for (var i = 1; i < 4; ++i) {
                   (function (_i) {
                      session.call("com.example.now.v" + _i).then(
                         function (res) {
                            console.log("result " + _i, res);
                         },
                         function (err) {
                            console.log("error " + _i, err);
                         }
                      );
                   })(i);
                }
             };

             connection.onclose = function (reason, details) {
                console.log("Connection lost: " + reason);
             }

             connection.open();
          </script>
       </body>
    </html>

txpostgres
~~~~~~~~~~

A txpostgres based database component
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This example is using txpostgres, but provides the same functionality as
the Twisted adbapi example component. You can use the same AutobahnJS
based client "index.htm" from above but change "...for (var i = 1; i < 4; ++i) {..." to "...for (var i = 1; i < 5; ++i) {..." as it has a bonus procedure! Name it hello.py so config.json can find it (detailed reasons discussed in the adbabi example above).

.. code:: python

    from txpostgres import txpostgres

    from twisted.internet.defer import inlineCallbacks, returnValue

    from autobahn import wamp
    from autobahn.twisted.wamp import ApplicationSession



    class MyDatabaseComponent(ApplicationSession):

       @inlineCallbacks
       def onJoin(self, details):

          ## create a new database connection pool. connections are created lazy (as needed)
          ## see: https://twistedmatrix.com/documents/current/api/twisted.enterprise.adbapi.ConnectionPool.html
          ##
          pool = txpostgres.ConnectionPool(None,
                                           host = '127.0.0.1',
                                           port = 5432,
                                           database = 'test',
                                           user = 'testuser',
                                           password = 'testuser')

          yield pool.start()
          print("DB connection pool started")

          ## we'll be doing all database access via this database connection pool
          ##
          self.db = pool

          ## register all procedures on this class which have been
          ## decorated to register them for remoting.
          ##
          regs = yield self.register(self)
          print("registered {} procedures".format(len(regs)))


       @wamp.register(u'com.example.now.v1')
       def get_dbnow(self):
          ## this variant demonstrates basic usage for running queries

          d = self.db.runQuery("SELECT now()")

          def got(rows):
             res = "{0}".format(rows[0][0])
             return res

          d.addCallback(got)
          return d


       @wamp.register(u'com.example.now.v2')
       @inlineCallbacks
       def get_dbnow_inline(self):
          ## this variant is using inline callbacks which makes code "look synchronous",
          ## nevertheless run asynchronous under the hood

          rows = yield self.db.runQuery("SELECT now()")
          res = "{0}".format(rows[0][0])
          returnValue(res)


       @wamp.register(u'com.example.now.v3')
       def get_dbnow_interaction(self):
          ## this variant runs the query inside a transaction (which might do more,
          ## and still be atomically committed/rolled back)

          def run(txn):
             d = txn.execute("SELECT now()")

             def on_cursor_ready(cur):
                rows = cur.fetchall()
                res = "{0}".format(rows[0][0])
                return res
             d.addCallback(on_cursor_ready)

             return d

          return self.db.runInteraction(run)


       @wamp.register(u'com.example.now.v4')
       def get_dbnow_interaction_coroutine(self):
          ## this variant runs the query inside a transaction (which might do more,
          ## and still be atomically committed/rolled back). Further, we are using
          ## a co-routine based coding style here.

          @inlineCallbacks
          def run(txn):
             cur = yield txn.execute("SELECT now()")
             rows = cur.fetchall()
             res = "{0}".format(rows[0][0])
             returnValue(res)

          return self.db.runInteraction(run)



    if __name__ == '__main__':
       from autobahn.twisted.wamp import ApplicationRunner

       runner = ApplicationRunner(url = "ws://127.0.0.1:8080/ws", realm = "realm1")
       runner.run(MyDatabaseComponent)

Test config.json assumes your local copy of autobahn.min.js resides in "/srv/_shared-web-resources/autobahn":

.. code:: javascript


    {
       "version": 2,
       "controller": {
       },
       "workers": [
          {
             "type": "router",
             "realms": [
                {
                   "name": "realm1",
                   "roles": [
                      {
                         "name": "anonymous",
                         "permissions": [
                            {
                               "uri": "com.",
                               "match":"prefix",
                               "allow": {
                                  "call": true,
                                  "register": true,
                                  "publish": true,
                                  "subscribe": true
                               },
                               "disclose": {
                                  "caller": false,
                                  "publisher": false
                               },
                               "cache": true
                            }
                         ]
                      }
                   ]
                }
             ],
             "transports": [
                {
                   "type": "web",
                   "endpoint": {
                      "type": "tcp",
                      "port": 8080
                   },
                   "paths": {
                      "/": {
                         "type": "static",
                         "directory": "../web"
                      },
                      "shared": {
                         "type": "static",
                         "directory": "/srv/_shared-web-resources/autobahn"
                      "ws": {
                         "type": "websocket",
                         "debug": true
                      }
                   }
                }
             ]
          },
          {
             "type": "container",
             "options": {
                "pythonpath": [".."]
             },
             "components": [
                {
                   "type": "class",
                   "classname": "hello.MyDatabaseComponent",
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
          }
       ]
    }
