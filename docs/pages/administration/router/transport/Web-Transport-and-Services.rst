:orphan:

Web Transport and Services
==========================

Quick Links: **`Web Services <Web%20Services>`__** - **`HTTP
Bridge <HTTP%20Bridge>`__** - **`Transport
Endpoints <Transport%20Endpoints>`__**

Crossbar.io includes a full-featured WAMP router to wire up your
application components. But if you serve HTML5 Web clients from
Crossbar.io, the **static Web assets** for your frontends like HTML,
JavaScript and image files need to be hosted somewhere as well.

You can host static content on your existing Web server or a static
hosting service like Amazon S3. It does not matter if your Crossbar.io
nodes reside on different domain names from the static content. However,
you can let Crossbar.io also host the static assets. This is possible by
using a **Web Transport** with your router.

Besides hosting static content, the **Web Transport** also adds a whole
number of other features like serving WSGI, redirection, file upload or
CGI.

Configuration
-------------

A Web transport is configured as a dictionary element in the list of
``transports`` of a router (see: `Router
Configuration <Router-Configuration>`__). The Web transport dictionary
has the following configuration parameters:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | The  |
| id`` | (opt |
| **   | iona |
|      | l)   |
|      | tran |
|      | spor |
|      | t    |
|      | ID - |
|      | this |
|      | must |
|      | be   |
|      | uniq |
|      | ue   |
|      | with |
|      | in   |
|      | the  |
|      | rout |
|      | er   |
|      | this |
|      | tran |
|      | spor |
|      | t    |
|      | runs |
|      | in   |
|      | (def |
|      | ault |
|      | :    |
|      | **"t |
|      | rans |
|      | port |
|      | N"** |
|      | -    |
|      | wher |
|      | e    |
|      | N is |
|      | numb |
|      | ered |
|      | star |
|      | ting |
|      | with |
|      | 1)   |
+------+------+
| **`` | Must |
| type | be   |
| ``** | ``"w |
|      | eb"` |
|      | `    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| endp | endp |
| oint | oint |
| ``** | to   |
|      | list |
|      | en   |
|      | on   |
|      | (*re |
|      | quir |
|      | ed*) |
|      | .    |
|      | See  |
|      | `Tra |
|      | nspo |
|      | rt   |
|      | Endp |
|      | oint |
|      | s <T |
|      | rans |
|      | port |
|      | %20E |
|      | ndpo |
|      | ints |
|      | >`__ |
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
|      | (*re |
|      | quir |
|      | ed*  |
|      | -    |
|      | see  |
|      | belo |
|      | w    |
|      | and  |
|      | `Web |
|      | Serv |
|      | ices |
|      |  <We |
|      | b%20 |
|      | Serv |
|      | ices |
|      | >`__ |
|      | or   |
|      | `HTT |
|      | P    |
|      | Brid |
|      | ge < |
|      | HTTP |
|      | %20B |
|      | ridg |
|      | e>`_ |
|      | _).  |
+------+------+
| **`` | Is   |
| opti | an   |
| ons` | opti |
| `**  | onal |
|      | dict |
|      | iona |
|      | ry   |
|      | for  |
|      | addi |
|      | tion |
|      | al   |
|      | tran |
|      | spor |
|      | t    |
|      | wide |
|      | conf |
|      | igur |
|      | atio |
|      | n    |
|      | (see |
|      | belo |
|      | w).  |
+------+------+

For Web transport ``paths`` the following two requirements must be
fullfilled:

-  a ``path`` must match the regular expression
   ``^([a-z0-9A-Z_\-]+|/)$``
-  there must be a root path ``/`` set

The value mapped to in the ``paths`` dictionary is a Web Service. The
complete list of available Web services can be found here:

-  `Web Services <Web%20Services>`__
-  `HTTP Bridge <HTTP%20Bridge>`__

The Web transport ``options`` can have the following attributes:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | set  |
| acce | to   |
| ss_l | ``tr |
| og`` | ue`` |
| **   | to   |
|      | enab |
|      | le   |
|      | Web  |
|      | acce |
|      | ss   |
|      | logg |
|      | ing  |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | set  |
| disp | to   |
| lay_ | ``tr |
| trac | ue`` |
| ebac | to   |
| ks`` | enab |
| **   | le   |
|      | rend |
|      | erin |
|      | g    |
|      | of   |
|      | Pyth |
|      | on   |
|      | trac |
|      | ebac |
|      | ks   |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | set  |
| hsts | to   |
| ``** | ``tr |
|      | ue`` |
|      | to   |
|      | enab |
|      | le   |
|      | `HTT |
|      | P    |
|      | Stri |
|      | ct   |
|      | Tran |
|      | spor |
|      | t    |
|      | Secu |
|      | rity |
|      | (HST |
|      | S) < |
|      | http |
|      | ://e |
|      | n.wi |
|      | kipe |
|      | dia. |
|      | org/ |
|      | wiki |
|      | /HTT |
|      | P_St |
|      | rict |
|      | _Tra |
|      | nspo |
|      | rt_S |
|      | ecur |
|      | ity> |
|      | `__  |
|      | (onl |
|      | y    |
|      | appl |
|      | icab |
|      | le   |
|      | when |
|      | usin |
|      | g    |
|      | a    |
|      | TLS  |
|      | endp |
|      | oint |
|      | )    |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | for  |
| hsts | HSTS |
| _max | ,    |
| _age | use  |
| ``** | this |
|      | maxi |
|      | mum  |
|      | age  |
|      | (onl |
|      | y    |
|      | appl |
|      | icab |
|      | le   |
|      | when |
|      | usin |
|      | g    |
|      | a    |
|      | TLS  |
|      | endp |
|      | oint |
|      | ).   |
|      | (def |
|      | ault |
|      | :    |
|      | **31 |
|      | 5360 |
|      | 00** |
|      | )    |
+------+------+

--------------

Example
-------

Here is the basic outline of a Web Transport configuration

.. code:: javascript

    {
       "controller": {
       },
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
                         "directory": ".."
                      },
                      "ws": {
                         "type": "websocket"
                      }
                   }
                }
             ]
          }
       ]
    }

Here is an example that combines three services:

.. code:: javascript

    "paths": {
       "/": {
          "type": "static",
          "directory": ".."
       },
       "ws": {
          "type": "websocket",
       },
       "downloads": {
          "type": "static",
          "directory": "/home/someone/downloads"
       },
       "config": {
          "type": "json",
          "value": {
             "param1": "foobar",
             "param2": [1, 2, 3]
          }
       }
    }

--------------
