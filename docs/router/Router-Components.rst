:orphan:

Router Components
=================

*Routers* can run WAMP application components written in Python
*side-by-side*, i.e. within the same system process.

Here's an example configuration:

.. code:: javascript

    {
       "controller": {
       },
       "workers": [
          {
             "type": "router",
             "options": {
                "pythonpath": [".."]
             },
             "components": [
                {
                   "type": "class",
                   "realm": "realm1",
                   "classname": "hello.MySession"
                }
             ],
             // ... rest of router configuration ...
          }
       ]
    }

The common parameters for components are:

+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
| parameter | description                                                                                                                                             |
+===========+=========================================================================================================================================================+
| id        | The (optional) component ID - this must be unique within the router this components runs in (default: "componentN" where N is numbered starting with 1) |
+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
| type      | The type of component, must be "class" (required)                                                                                                       |
+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
| realm     | The realm on the router to attach this component to, e.g. "realm1" (required)                                                                           |
+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
| role      | The (optional) role for which the component is authenticated, e.g. "role1", if none give authentication is as "anonymous"                               |
+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
| extra     | Optional data provided to the class when instantiating.                                                                                                 |
+-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------+


For components of ``type == "class"``, the following parameters must be provided:


+-----------+-----------------------------------------------------------------------------------------------------+
| parameter | description                                                                                         |
+===========+=====================================================================================================+
| classname | The (fully qualified) class name of a class that derives from ``ApplicationSession`` (**required**) |
+-----------+-----------------------------------------------------------------------------------------------------+

