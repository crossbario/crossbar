[Documentation](.) > [Administration](Administration) > [Processes](Processes) >[Router Configuration](Router Configuration) > Router Components
# Router Components

*Routers* can run WAMP application components written in Python *side-by-side*, i.e. within the same system process.

Here's an example configuration:

```javascript
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
```

The common parameters for components are:

parameter | description
---|---
**`id`** | The (optional) component ID - this must be unique within the router this components runs in (default: **"componentN"** where N is numbered starting with 1)
**`type`** | The type of component, must be one of `"class"` or `"wamplet"` (**required**)
**`realm`** | The realm on the router to attach this component to, e.g. "realm1" (**required**)
**`role`** | The (optional) role for which the component is authenticated, e.g. "role1", if none give authentication is as "anonymous"
**`extra`** | Optional data provided to the class when instantiating.

For components of `type == "class"`, the following parameters must be provided:

parameter | description
---|---
**`classname`** | The (fully qualified) class name of a class that derives from `ApplicationSession` (**required**)


For components of `type == "wamplet"`, the following parameters must be provided:

parameter | description
---|---
**`package`** | The name of the Python package ("distribution") containing the WAMPlet (**required**)
**`entrypoint`** | The factory entry point within the package (**required**)

