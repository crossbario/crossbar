:orphan:

Resource Service
================

Allows to hook any Twisted Web resource into the service tree.

Configuration
-------------

To configure a Resource Service, attach a dictionary element to a path
in your `Web transport <Web%20Transport%20and%20Services>`__:

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
