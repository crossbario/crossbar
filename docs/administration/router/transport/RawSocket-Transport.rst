RawSocket Transport
===================

Quick Links: **`Transport Endpoints <Transport%20Endpoints>`__**

The **RawSocket Transport** implements WAMP-over-RawSocket and supports
TCP/TLS as well as Unix domain socket, each combined with JSON and
MsgPack for serialization.

"RawSocket" is an (alternative) transport for WAMP that uses
length-prefixed, binary messages - a message framing different from
WebSocket. Compared to WebSocket, "RawSocket" is extremely simple to
implement.

-  `Listening RawSocket Transport
   Configuration <#listening-transports>`__
-  `Listening RawSocket Transport
   Example <#example---listening-transport>`__

as well as **connecting transports**

-  `Connecting RawSocket Transport
   Configuration <#connecting-transports>`__
-  `Connecting RawSocket Transport
   Example <#example---connecting-transport>`__

    RawSocket can run over TCP, TLS or Unix domain socket. When run over
    TLS on a (misused) standard Web port (443), it is also able to
    traverse most locked down networking environments (unless
    Man-in-the-Middle intercepting proxies are in use). However, it does
    not support compression or automatic negotiation of WAMP
    serialization (as WebSocket allows). Perhaps most importantly,
    RawSocket cannot be used with Web browser clients.

Configuration
-------------

Crossbar.io supports both **listening** as well as **connecting**
WAMP-over-RawSocket transports.

Listening transports are used with `routers <Router%20Configuration>`__
to allow WAMP clients connect to Crossbar.io, whereas connecting
transports are used with `containers <Container%20Configuration>`__ to
allow hosted components to connect to their upstream router.

Listening Transports
~~~~~~~~~~~~~~~~~~~~

Listening transports are used with `routers <Router%20Configuration>`__
to allow WAMP clients connect to Crossbar.io. The available parameters
for RawSocket listening transports are:

+------+-------+
| Para | Descr |
| mete | iptio |
| r    | n     |
+======+=======+
| **`` | The   |
| id`` | (opti |
| **   | onal) |
|      | trans |
|      | port  |
|      | ID -  |
|      | this  |
|      | must  |
|      | be    |
|      | uniqu |
|      | e     |
|      | withi |
|      | n     |
|      | the   |
|      | route |
|      | r     |
|      | this  |
|      | trans |
|      | port  |
|      | runs  |
|      | in    |
|      | (defa |
|      | ult:  |
|      | **``" |
|      | trans |
|      | portN |
|      | "``** |
|      | where |
|      | **N** |
|      | is    |
|      | numbe |
|      | red   |
|      | start |
|      | ing   |
|      | with  |
|      | **1** |
|      | )     |
+------+-------+
| **`` | Must  |
| type | be    |
| ``** | ``"ra |
|      | wsock |
|      | et"`` |
|      | (**re |
|      | quire |
|      | d**)  |
+------+-------+
| **`` | A     |
| endp | netwo |
| oint | rk    |
| ``** | conne |
|      | ction |
|      | for   |
|      | data  |
|      | trans |
|      | missi |
|      | on    |
|      | - see |
|      | `Tran |
|      | sport |
|      | Endpo |
|      | ints  |
|      | <Tran |
|      | sport |
|      | %20En |
|      | dpoin |
|      | ts>`_ |
|      | _     |
|      | (**re |
|      | quire |
|      | d**)  |
+------+-------+
| **`` | List  |
| seri | of    |
| aliz | seria |
| ers` | lizer |
| `**  | s     |
|      | to    |
|      | use   |
|      | from  |
|      | ``"js |
|      | on"`` |
|      | or    |
|      | ``"ms |
|      | gpack |
|      | "``   |
|      | (defa |
|      | ult:  |
|      | **all |
|      | avail |
|      | able* |
|      | *)    |
+------+-------+
| **`` | Maxim |
| max_ | um    |
| mess | size  |
| age_ | in    |
| size | bytes |
| ``** | of    |
|      | incom |
|      | ing   |
|      | RawSo |
|      | cket  |
|      | messa |
|      | ges   |
|      | accep |
|      | ted.  |
|      | Must  |
|      | be    |
|      | betwe |
|      | en    |
|      | 1 and |
|      | 64MB  |
|      | (defa |
|      | ult:  |
|      | **128 |
|      | kB**) |
+------+-------+
| **`` | Authe |
| auth | ntica |
| ``** | tion  |
|      | to be |
|      | used  |
|      | for   |
|      | this  |
|      | *Endp |
|      | oint* |
|      | - see |
|      | [[Aut |
|      | henti |
|      | catio |
|      | n]]   |
+------+-------+
| **`` | Enabl |
| debu | e     |
| g``* | trans |
| *    | port  |
|      | level |
|      | debug |
|      | outpu |
|      | t.    |
|      | (defa |
|      | ult:  |
|      | **``f |
|      | alse` |
|      | `**)  |
+------+-------+

--------------

Connecting Transports
~~~~~~~~~~~~~~~~~~~~~

Connecting transports are used with
`containers <Container%20Configuration>`__ to allow hosted components to
connect to their upstream router. The available parameters for RawSocket
connecting transports are:

+------+-------+
| Para | Descr |
| mete | iptio |
| r    | n     |
+======+=======+
| **`` | The   |
| id`` | (opti |
| **   | onal) |
|      | trans |
|      | port  |
|      | ID -  |
|      | this  |
|      | must  |
|      | be    |
|      | uniqu |
|      | e     |
|      | withi |
|      | n     |
|      | the   |
|      | route |
|      | r     |
|      | this  |
|      | trans |
|      | port  |
|      | runs  |
|      | in    |
|      | (defa |
|      | ult:  |
|      | **``" |
|      | trans |
|      | portN |
|      | "``** |
|      | where |
|      | **N** |
|      | is    |
|      | numbe |
|      | red   |
|      | start |
|      | ing   |
|      | with  |
|      | **1** |
|      | )     |
+------+-------+
| **`` | Must  |
| type | be    |
| ``** | ``"ra |
|      | wsock |
|      | et"`` |
|      | (**re |
|      | quire |
|      | d**)  |
+------+-------+
| **`` | A     |
| endp | netwo |
| oint | rk    |
| ``** | conne |
|      | ction |
|      | for   |
|      | data  |
|      | trans |
|      | missi |
|      | on    |
|      | - see |
|      | `Tran |
|      | sport |
|      | Endpo |
|      | ints  |
|      | <Tran |
|      | sport |
|      | %20En |
|      | dpoin |
|      | ts>`_ |
|      | _     |
|      | (**re |
|      | quire |
|      | d**)  |
+------+-------+
| **`` | The   |
| seri | seria |
| aliz | lizer |
| er`` | to    |
| **   | use:  |
|      | ``"js |
|      | on"`` |
|      | or    |
|      | ``"ms |
|      | gpack |
|      | "``   |
|      | (**re |
|      | quire |
|      | d**)  |
+------+-------+
| **`` | Enabl |
| debu | e     |
| g``* | trans |
| *    | port  |
|      | level |
|      | debug |
|      | outpu |
|      | t.    |
|      | (defa |
|      | ult:  |
|      | **``f |
|      | alse` |
|      | `**)  |
+------+-------+

--------------

Example
-------

Example - Listening Transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example *Transport* that will run WAMP-over-RawSocket on a
Unix domain socket using MsgPack serialization:

.. code:: javascript

    {
       "type": "rawsocket",
       "serializers": ["json", "msgpack"],
       "endpoint": {
          "type": "unix",
          "path": "/tmp/mysocket1"
       }
    }

--------------

Example - Connecting Transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Write me.

--------------
