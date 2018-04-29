title: Reverse Proxy Service toc: [Documentation, Administration, Web
Services, Reverse Proxy Service]

Reverse Proxy Service
=====================

Configuration
-------------

To configure a Web Reverse Proxy Service, attach a dictionary element to
a path in your `Web transport <Web%20Transport%20and%20Services>`__:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | must |
| type | be   |
| ``** | ``"r |
|      | ever |
|      | sepr |
|      | oxy" |
|      | ``   |
+------+------+
| **`` | the  |
| host | host |
| ``** | of   |
|      | the  |
|      | web  |
|      | serv |
|      | er   |
|      | to   |
|      | prox |
|      | y,   |
|      | e.g. |
|      | ``"w |
|      | ww.e |
|      | xamp |
|      | le.c |
|      | om"` |
|      | `.   |
+------+------+
| **`` | the  |
| port | port |
| ``** | of   |
|      | the  |
|      | web  |
|      | serv |
|      | er   |
|      | to   |
|      | prox |
|      | y    |
|      | (def |
|      | ault |
|      | :    |
|      | ``80 |
|      | ``)  |
+------+------+
| **`` | the  |
| path | base |
| ``** | path |
|      | to   |
|      | fetc |
|      | h    |
|      | data |
|      | from |
|      | with |
|      | no   |
|      | trai |
|      | ling |
|      | slas |
|      | hes  |
|      | (def |
|      | ault |
|      | :    |
|      | ``"" |
|      | ``)  |
+------+------+

Example
-------

Here is how you define a **Web Transport** that do reverse proxy to
``example.com/my_path``:

.. code:: javascript

    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 80
       },
       "paths": {
          "/": {
             "type": "reverseproxy",
             "host": "example.com",
             "path": "/my_path"
          }
       }
    }

    In this example, an incoming request ``POST /login`` would be
    proxied to domain ``example.com`` as ``POST /my_path/login``

--------------
