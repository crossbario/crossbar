:orphan:

Node Info Service
=================

The **Node Info Service** is configured on a subpath of a :doc:`Web
transport <Web-Transport-and-Services>` and allows you to expose
a HTML information page about the node.

The page is rendered dynamically by Crossbar.io and includes information
such as:

-  Release ``Crossbar.io COMMUNITY 17.4.1``
-  Node Started ``2017-04-15T22:33:13.578Z``
-  Node Controller PID ``31043``
-  Running Workers ``1``
-  Node Public Key
   ``42c1e06fb527d041ba5f9b14166153d95fcb6123353fad4265a7fd469b269f42``
-  Served for ``127.0.0.1:41788`` from Crossbar.io router worker with
   PID ``31048``.

The node public key is useful eg for secure pairing with a management
platform. The software release version and PID allows to verify basic
operation.

While a node info page does not expose secure information per-se, it
does expose software versions and public key material, which can expose
the identity of the originator of information (though it will still
preserve confidentiality).

**Because of this, running this in production, listening on a public
internet facing endpoint, is NOT recommended!**

Configuration
-------------

To configure a node info service, attach a dictionary element to a path
in your :doc:`Web transport <Web-Transport-and-Services>`:

+----------------+--------------------------+
| attribute      | description              |
+================+==========================+
| **``type``**   | must be ``"nodeinfo"``   |
+----------------+--------------------------+

Example
-------

**See
`here <https://github.com/crossbario/crossbar-examples/tree/master/nodeinfo>`__
for the complete example.**

A **Web Transport** configuration that includes a **Node Info Service**
on the subpath ``info``:

.. code:: javascript

     {
         "type": "web",
         "endpoint": {
             "type": "tcp",
             "port": 8080
         },
         "web": {
             "paths": {
                 "/": {
                     "type": "static",
                     "directory": "../web"
                 },
                 "info": {
                     "type": "nodeinfo"
                 }
             }
         }
     }

When you open http://localhost:8080/info in your browser, you should get
a HTML node information page rendered with data like the node public key
and software release string.

