:orphan:

Resource Service
================

Allows to hook any Twisted Web resource into the service tree.

Configuration
-------------

To configure a Resource Service, attach a dictionary element to a path
in your  :doc:`Web transport <Web-Transport-and-Services>`:

+-----------+-------------------------------------------------------------------------------+
| attribute | description                                                                   |
+===========+===============================================================================+
| type      | Must be "resource".                                                           |
+-----------+-------------------------------------------------------------------------------+
| classname | Fully qualified Python class of the Twisted Web resource to expose.           |
+-----------+-------------------------------------------------------------------------------+
| extra     | Arbitrary extra data provided to the constructor of the Twisted Web resource. |
+-----------+-------------------------------------------------------------------------------+

Example
-------

Write me.
