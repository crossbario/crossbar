title: JSON Value Service toc: [Documentation, Administration, Web
Services, JSON Value Service]

JSON Value Service
==================

The **JSON Value Service** is configured on a subpath of a `Web
transport <Web%20Transport%20and%20Services>`__ and allows you to expose
a custom JSON value from your node configuration dynamically over
HTTP(S).

This can be useful to have custom parameters accessible from JavaScript
running in browsers or other Web clients.

Configuration
-------------

To configure a JSON Value ervice, attach a dictionary element to a path
in your `Web transport <Web%20Transport%20and%20Services>`__:

+-------------------+---------------------------------------+
| attribute         | description                           |
+===================+=======================================+
| **``type``**      | must be ``"json"``                    |
+-------------------+---------------------------------------+
| **``value``**     | any valid JSON value                  |
+-------------------+---------------------------------------+
| **``options``**   | dictionary with options (see below)   |
+-------------------+---------------------------------------+

where ``options`` is a dictionary:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | a    |
| pret | bool |
| tify | ean  |
| ``** | that |
|      | cont |
|      | rols |
|      | when |
|      | to   |
|      | pret |
|      | tify |
|      | the  |
|      | rend |
|      | ered |
|      | JSON |
|      | (def |
|      | ault |
|      | :    |
|      | ``tr |
|      | ue`` |
|      | )    |
+------+------+
| **`` | a    |
| allo | bool |
| w_cr | ean, |
| oss_ | allo |
| orig | w    |
| in`` | cros |
| **   | s-or |
|      | igin |
|      | requ |
|      | ests |
|      | (COR |
|      | S)   |
|      | (def |
|      | ault |
|      | :    |
|      | ``fa |
|      | lse` |
|      | `)   |
+------+------+
| **`` | a    |
| disc | bool |
| oura | ean, |
| ge_c | set  |
| achi | head |
| ng`` | ers  |
| **   | to   |
|      | disc |
|      | oura |
|      | ge   |
|      | cach |
|      | ing  |
|      | of   |
|      | the  |
|      | resp |
|      | onse |
|      | (def |
|      | ault |
|      | :    |
|      | ``fa |
|      | lse` |
|      | `)   |
+------+------+

Example
-------

Here is an example **Web Transport** configuration that includes a
**JSON Value Service** on the subpath ``config``:

.. code:: javascript

    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "paths": {
          "/": {
             "type": "static",
             "directory": ".."
          },
          "ws": {
             "type": "websocket",
             "url": "ws://localhost:8080/ws"
          },
          "config": {
             "type": "json",
             "value": {
                "param1": "foobar",
                "param2": [1, 2, 3],
                "param3": {
                   "awesome": true,
                   "nifty": "yes"
                }
             }
          }
       }

When you open ``http://localhost:8080/config`` in your browser, you
should get

.. code:: javascript

    {
       "param1": "foobar",
       "param2": [
          1,
          2,
          3
       ],
       "param3": {
          "awesome": true,
          "nifty": "yes"
       }
    }

Crossbar.io will serve the JSON value with the correct MIME type
(``application/json``), but prettify the output for convenience when
access by a human.

You can now retrieve above JSON e.g. by issueing an
`XMLHttpRequest <http://www.w3.org/TR/XMLHttpRequest/>`__ from
JavaScript and use the custom parameter values to control some aspect in
your application frontend.

--------------
