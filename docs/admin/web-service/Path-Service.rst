Path Service
============

Provides nesting of Web path services.

Configuration
-------------

To configure a Path Service, attach a dictionary element to a path in
your `Web transport <Web%20Transport%20and%20Services>`__:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | must |
| type | be   |
| ``** | ``"p |
|      | ath" |
|      | ``   |
+------+------+
| **`` | A    |
| path | dict |
| s``* | iona |
| *    | ry   |
|      | for  |
|      | conf |
|      | igur |
|      | ing  |
|      | serv |
|      | ices |
|      | on   |
|      | subp |
|      | aths |
|      | with |
|      | keys |
|      | matc |
|      | hing |
|      | the  |
|      | regu |
|      | lar  |
|      | expr |
|      | essi |
|      | on   |
|      | ``^( |
|      | [a-z |
|      | 0-9A |
|      | -Z_\ |
|      | -]+| |
|      | /)$` |
|      | `,   |
|      | and  |
|      | with |
|      | ``/` |
|      | `    |
|      | in   |
|      | the  |
|      | set  |
|      | of   |
|      | keys |
|      | .    |
+------+------+

Example
-------

Here is an example where two subpaths are collected on a Path Service
which serves as a kind of folder:

.. code:: javascript

    {
       "workers": [
          {
             "type": "router",
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
                      "myfolder": {
                         "type": "path"
                         "paths": {
                            "download1": {
                                "type": "static",
                                "directory": "/tmp"
                             },
                             "download2": {
                                "type": "static",
                                "directory": "/data/tmp"
                             }
                         }
                      }
                   }
                }
             ]
          }
       ]
    }

--------------
