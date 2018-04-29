title: Flash Policy Transport toc: [Documentation, Administration,
Router Transports, Flash Policy Transport]

Flash Policy Transport
======================

Quick Links: **`Transport Endpoints <Transport%20Endpoints>`__**

Old Web browsers like IE8 and IE9 do no support WebSocket natively.
*One* option to work around is using
`web-socket-js <https://github.com/gimite/web-socket-js>`__, a WebSocket
implementation written in Adobe Flash.

When using Adobe Flash to open a TCP socket, Flash will only allow the
(outgoing) TCP connection *after* checking for a so called *Flash policy
file* on the target server. And this policy file needs to be served on
TCP port 843.

Crossbar.io includes a *pseudo transport* for serving a Flash policy
file. It is a *pseudo* transport, since in itself, it does not provide a
WAMP transport, but its only purpose is to serve the Flash policy.

    The `Crossbar.io examples
    repository <https://github.com/crossbario/crossbarexamples>`__
    contains a `working
    example <https://github.com/crossbario/crossbarexamples/tree/master/flash>`__
    for this.

Configuration
-------------

In the configuration (``.crossbar/config.json``), you'll find:

.. code:: json

    {
       "workers": [
          {
             "type": "router",
             "transports": [
                {
                   "type": "flashpolicy",
                   "allowed_domain": "*",
                   "allowed_ports": [8080],
                   "endpoint": {
                      "type": "tcp",
                      "port": 843
                   }
                }
             ]
          }
       ]
    }

--------------

Usage
-----

The only difference client side (in the HTML) versus a standard client
is that you now include the Flash implementation *before* AutobahnJS:

.. code:: html

    <!-- Adobe Flash implementation of WebSocket: https://github.com/gimite/web-socket-js -->
    <script>
       WEB_SOCKET_SWF_LOCATION = "WebSocketMain.swf";
       // set the following to false for production, otherwise
       // it _always_ uses Flash
       WEB_SOCKET_FORCE_FLASH = true;
       WEB_SOCKET_DEBUG = true;
    </script>
    <script src="swfobject.js"></script>
    <script src="web_socket.js"></script>

    <!-- AutobahnJS -->
    <script src="autobahn.min.js"></script>

--------------

Configuration
-------------

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | ID   |
| id`` | of   |
| **   | the  |
|      | tran |
|      | spor |
|      | t    |
|      | with |
|      | in   |
|      | the  |
|      | runn |
|      | ing  |
|      | node |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | tran |
|      | spor |
|      | t<N> |
|      | ``** |
|      | wher |
|      | e    |
|      | ``N` |
|      | `    |
|      | is   |
|      | numb |
|      | ered |
|      | auto |
|      | mati |
|      | call |
|      | y    |
|      | star |
|      | ting |
|      | from |
|      | ``1` |
|      | `)   |
+------+------+
| **`` | Type |
| type | of   |
| ``** | tran |
|      | spor |
|      | t    |
|      | -    |
|      | must |
|      | be   |
|      | ``"f |
|      | lash |
|      | "``. |
+------+------+
| **`` | List |
| endp | enin |
| oint | g    |
| ``** | endp |
|      | oint |
|      | for  |
|      | tran |
|      | spor |
|      | t.   |
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
|      | for  |
|      | conf |
|      | igur |
|      | atio |
|      | n    |
+------+------+
| **`` | Doma |
| allo | in   |
| wed_ | (a   |
| doma | stri |
| in`` | ng)  |
| **   | clie |
|      | nts  |
|      | shou |
|      | ld   |
|      | be   |
|      | allo |
|      | wed  |
|      | to   |
|      | conn |
|      | ect  |
|      | to   |
|      | or   |
|      | ``nu |
|      | ll`` |
|      | to   |
|      | allo |
|      | w    |
|      | any  |
|      | doma |
|      | in   |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | null |
|      | ``** |
|      | )    |
+------+------+
| **`` | List |
| allo | of   |
| wed_ | port |
| port | s    |
| s``* | (a   |
| *    | list |
|      | of   |
|      | inte |
|      | gers |
|      | from |
|      | ``[1 |
|      | , 65 |
|      | 535] |
|      | ``)  |
|      | clie |
|      | nts  |
|      | shou |
|      | ld   |
|      | be   |
|      | allo |
|      | wed  |
|      | to   |
|      | conn |
|      | ect  |
|      | to   |
|      | or   |
|      | ``nu |
|      | ll`` |
|      | to   |
|      | allo |
|      | w    |
|      | any  |
|      | port |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | null |
|      | ``** |
|      | )    |
+------+------+
| **`` | Turn |
| debu | on   |
| g``* | debu |
| *    | g    |
|      | logg |
|      | ing  |
|      | for  |
|      | this |
|      | tran |
|      | spor |
|      | t    |
|      | inst |
|      | ance |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | fals |
|      | e``* |
|      | *).  |
+------+------+

--------------
