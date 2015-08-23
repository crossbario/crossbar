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