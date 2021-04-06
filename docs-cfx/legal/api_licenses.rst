API Licenses
============

Overview of the different API namespaces available in Crossbar.io
OSS, Crossbar.io Fabric and Crossbar.io Fabric Center, and the
respective API licenses that apply

--------------

The open source Crossbar.io router and the software for Crossbar.io
Fabric provide multiple APIs.

APIs may be protected by copyright in some jurisdictions (e.g. it is
overwhelmingly likely that this is the case in the USA). Where this is
the case, Crossbar.io GmbH holds the copyright in the APIs.

We provide different licensing for different APIs. The APIs are structured
into namespaces, i.e. which API a call or event depends on is indicated by
its respective URI prefix:

-  **wamp.** - The WAMP meta API as defined by the WAMP RFC draft. Like
   the RFC draft itself, this is under a free license for anybody to
   use. This includes modifications and extensions.
-  **crossbar-wamp.** - Extensions to the WAMP meta API which are
   specific to the open source Crossbar.io router. This, naturally, can
   be used by anybody using this software. No changes to this are
   allowed.
-  **crossbar.** - The internal management API of the Crossbar.io
   router. This may not be called or otherwise used by code outside of
   the router.
-  **crossbarfabric-wamp.** - Extensions to the WAMP meta API specific
   to the Crossbar.io Fabric router. This API can only be used with a
   commercial license.
-  **crossbarfabric.** - The internal management API of the Crossbar.io
   Fabric router. This can only be used with a commercial license.
-  **crossbarfabriccenter.** - The public API of the (online)
   Crossbar.io Fabric Center. This can only be used with a commercial
   license.

    Users should only interact with the application-level APIs within
    the 'wamp.', 'crossbar-wamp.', 'crossbariofabric-wamp.' and
    'crossbarfabriccenter.' namespaces.

The necessary commercial licenses for the use of the 'crossbariofabric'
APIs are granted to all legal Crossbar.io Fabric service users. They are
contained in the Crossbar.io Fabric Commercial License and the
Crossbar.io Fabric Center Terms of Use (which can be found in the
`Crossbar.io Fabric public GitHub
repository <https://github.com/crossbario/crossbar-fabric-public/tree/master/legal>`__).
