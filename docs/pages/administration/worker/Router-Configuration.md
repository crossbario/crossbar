title: Router Configuration
toc: [Documentation, Administration, Processes, Router Configuration]

# Router Configuration

*Routers* are the core facilities of Crossbar.io, responsible for routing WAMP remote procedure calls between *Callers* and *Callees*, as well as routing WAMP publish-subscribe events between *Publishers* and *Subscribers*.

A Crossbar.io instance will usually be running at least one *Router*, unless is used solely to run application components in *Workers* or *Guests*.

A *Router* is configured as a *Worker*, more precisely a *Native Worker*, process of `type == "router"`:

```javascript
{
   "workers": [
      {
         "type": "router",
         "options": {
            // router options go here
         },
         "realms": [
            // realms managed by this router
         ],
         "transports": [
            // transports run by this router
         ],
         "components": [
            // app components running side-by-side with this router
         ]
      }
   ]
}
```

For the available `options` with *Routers*, please see

* [[Native Worker Options]]
* [[Process Environments]]

For configuration of `realms`, `transports` and `components`, have a look here

* [[Router Realms]]
* [[Router Transports]]
* [[Router Components]]


## Configuration

parameter | description
---|---
**`id`** | Optional router ID (default: `"router<N>"`)
**`type`** | Must be `"router"`.
**`options`** | Please see [Native Worker Options](Native Worker Options).
**`realms`** | Please see [Router Realms](Router Realms).
**`transports`** | Please see [Router Transports](Router Transports).
**`components`** | A list of components. Please see below.
**`connections`** | Not yet implemented.

Router components are either **plain Python classes**:

parameter | description
---|---
**`id`** | Optional component ID (default: `"component<N>"`)
**`type`** | Must be `"class"`.
**`realm`** | The realm to join with the component.
**`role`** | The atuhrole under which to attach the component.
**`references`** | Please see below.
**`classname`** | The fully qualified Python classname to use.
**`extra`** | Arbitrary custom data forwarded to the class ctonstructor.

Another option for Router components are **WAMPlets**:

parameter | description
---|---
**`id`** | Optional component ID (default: `"component<N>"`)
**`type`** | Must be `"wamplet"`.
**`realm`** | The realm to join with the component.
**`role`** | The atuhrole under which to attach the component.
**`references`** | Please see below.
**`package`** | The name of the package to look for.
**`entrypoint`** | The entrypoint within packages to look at.
**`extra`** | Arbitrary custom data forwarded to the class constructor.
