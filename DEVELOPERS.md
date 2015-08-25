# Developer Guide

This guide is for developers of the Crossbar.io code itself, not for application developers creating Crossbar.io based applications.

## Roadmap

### 0.11.0

[Milestone for 0.11.0](https://github.com/crossbario/crossbar/milestones/0.11.0)

* Python 3
* new logging
* various improvements in error handling
* File Upload service
* various bug fixes and enhancement

### 0.12.0

[Milestone for 0.12.0](https://github.com/crossbario/crossbar/milestones/0.12.0)

* PostgreSQL integration
* RawSocket ping/pong
* Reverse Proxy service
* Web hook service
* various bug fixes and enhancement

### 0.13.0

[Milestone for 0.13.0](https://github.com/crossbario/crossbar/milestones/0.13.0)

* Timeouts at different levels (WAMP action, ..)
* Various authentication features
* Reflection, API docs generation, payload validation

### 0.14.0

[Milestone for 0.14.0](https://github.com/crossbario/crossbar/milestones/0.14.0)

* Multi-core support for routers (part 1: transport/routing service processes)


## Manhole

**Manhole** is a feature useful primarily for developers working on the Crossbar.io code base.

Manhole allows you to log into **live** running Crossbar.io *Controller* or *Native Worker* processes via SSH. You can then inspect and modify the internals while running.

> Note that Manhole applies to *Controller* and *Native Worker* (*Routers* and *Containers*) processes. It is not available for **Guest Worker** processes.

Here is how you configure a *Worker* for accepting Manhole SSH connections:

```javascript
{
   "controller": {
      // controller configuration
   },
   "workers": [
      {
         "type": "router",
         "manhole": {
            "endpoint": {
               "type": "tcp",
               "port": 6022
            },
            "users": [
               {
                  "user": "oberstet",
                  "password": "secret"
               }
            ]
         },
         // rest of router configuration
      }
   ]
}
```

**Manhole** requires 2 parameters:

* `endpoint`
* `users`

The `endpoint` parameter defines where Manhole will listen for incoming SSH connections. You can use any options for `endpoint`, for example set up a Unix domain socket endpoint, or restrict listening to an interface, e.g. loopback:

```javascript
"endpoint": {
   "type": "tcp",
   "port": 6022,
   "interface": "127.0.0.1"
}
```

The `users` parameter defines authorized users and their passwords, e.g.:

```javascript
"users": [
	{
    	"user": "oberstet",
        "password": "secret"
    }
]
```

> Caution: Obviously, storing passwords in configuration files is unsafe! A user logged into your live server can do **anything**. This feature is for development - not production. You have been warned.

Given above config, you can then log into the Worker via SSH:

```console
ssh -p 6022 oberstet@127.0.0.1
```

which will drop you into an interactive, colored Python shell:

```python
>>> dir()
['__builtins__', 'session']
>>> session
<crossbar.worker.router.RouterWorkerSession instance at 0x41fa488>
>>>
>>> session.uptime()
3066.588492
>>>
```

The `session` in this case is an instance of `crossbar.worker.router.RouterWorkerSession`.

This session is attached to the local Crossbar.io management router and is the entry point into everything happening inside the *Worker*.

You can also start Manhole in the *Controller*:

```javascript
{
   "controller": {
      "manhole": {
         "endpoint": {
            "type": "tcp",
            "port": 6022
         },
         "users": [
            {
               "user": "oberstet",
               "password": "secret"
            }
         ]
      }
   },
   "workers": [
   ]
}
```

The `session` in this case is an instance of `crossbar.controller.process.NodeControllerSession`.
