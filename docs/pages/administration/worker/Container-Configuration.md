title: Container Configuration
toc: [Documentation, Administration, Processes, Container Configuration]

# Container Configuration

**Containers** are worker processes spawned by Crossbar.io which *directly* host application classes written in Python deriving from `autobahn.twisted.wamp.ApplicationSession`.

This relieves the application programmer from any boilerplate code for hooking up application components into Crossbar.io via WAMP.

For example, here is a **Python Component** configuration that will load the application class `timeservice.TimeService` in a worker process, connecting to the specified router (router config part omitted):

```javascript
{
   "controller": {
   },
   "workers": [
      ...
      {
         "type": "container",
         "options": {
            "pythonpath": [".."]
         },
         "components": [
            {
               "type": "class",
               "classname": "hello.hello.AppSession",
               "realm": "realm1",
               "transport": {
                  "type": "websocket",
                  "endpoint": {
                     "type": "tcp",
                     "host": "127.0.0.1",
                     "port": 8080
                  },
                  "url": "ws://127.0.0.1:8080/ws"
               }
            }
         ]
      }
   ]
}
```

The worker itself has the options

1. `type`: must be `"container"`(*required*)
2. `options`: a dictionary of configuration options
3. `components`: a list Python components to run in the container (*required*)

`options` are those [shared by Native Workers](Native Worker Options)

For a `component`, the `type` is *required* and may be either `class` or `wamplet`.

Both types share the following options:

1. `id`: The ID of the node
2. `realm`: The realm to connect to (*required*)
3. `transport`: the data for connecting to the router (*required*)
4. `extra`: Optional data provided to the class when instantiating

For the type `class`, you need to set

* `classname`: the Python WAMP application class, a module/classname of a class derived from `autobahn.twisted.wamp.ApplicationSession` (*required*)

For the type `wamplet`, you need to set

1. `package`: The name of the installed Python package (*required*)
2. `entrypoint`: The name of the file within the package to execute (*required*)


## Failures

A number of failures can happen starting your component:

* module not found
* syntax error in module
* class not found
* class could not be instantiated
* object throws an exception

Further, what is happening when you leave the realm or disconnect the transport from the session?


## Configuration

parameter | description
---|---
**`id`** | Optional container ID (default: `"container<N>"`)
**`type`** | Must be `"container"`.
**`options`** | Please see [Native Worker Options](Native Worker Options).
**`components`** | A list of components. Please see below.
**`connections`** | Not yet implemented.

Container components are either **plain Python classes**:

parameter | description
---|---
**`id`** | Optional component ID (default: `"component<N>"`)
**`type`** | Must be `"class"`.
**`realm`** | The realm to join with the component.
**`transport`** | The configured connecting transport.
**`classname`** | The fully qualified Python classname to use.
**`extra`** | Arbitrary custom data forwarded to the class ctonstructor.

Another option for Container components are **WAMPlets**:

parameter | description
---|---
**`id`** | Optional component ID (default: `"component<N>"`)
**`type`** | Must be `"wamplet"`.
**`realm`** | The realm to join with the component.
**`transport`** | The configured connecting transport.
**`package`** | The name of the package to look for.
**`entrypoint`** | The entrypoint within packages to look at.
**`extra`** | Arbitrary custom data forwarded to the class constructor.
