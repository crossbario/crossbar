title: Starting and Stopping Crossbar.io
toc: [Documentation, Programming Guide, Starting and Stopping Crossbario]

# Starting and Stopping Crossbar.io

When Crossbar.io forms part of your application, there are four approaches of starting Crossbar.io:

1. Start Crossbar.io from a startup script
2. Start Crossbar.io from within your application
3. Start you application from Crossbar.io
4. Start Crossbar.io externally

## Starting Crossbar.io from a startup script

You can create a startup script for your application that first start a Crossbar.io node and then starts everything else needed for your application (like WAMP application components or other parts of your app).

## Starting Crossbar.io from within your application

To start a Crossbar.io node from within your application, simply run the Crossbar.io executable using the usual language specific facilities.

E.g in Python, you can start Crossbar.io

```python
import subprocess
p = subprocess.Popen(["/home/oberstet/python278/bin/crossbar",
   "start", "--cbdir", "/home/oberstet/node1/.crossbar"])
```

> Note that you need to specifiy fully qualified paths here.

To stop Crossbar.io

```python
p.terminate()
p.wait()
```

## Starting you application from Crossbar.io

Crossbar.io is able to start, monitor and host application components. Please see the respective documentation about container and guest workers.

## Starting Crossbar.io externally

You can have Crossbar.io be started from OS level startup facilities (like Linux **rc.d scripts** or **systemd**). You actual application might also be started by the same facility and then depend on the Crossbar.io service having started already earlier.


# Startup and Shutdown Behavior

When running from a configuration file (as opposed to connecting to a management uplink), Crossbar will start all components (whether in their own Container or running inside a Router) exactly once. When such a component shuts down or disconnects, it is gone. Individual components can exit cleanly, or with errors. When all components in a container shut down, the container itself shuts down (with error, if any component errored). A "worker" refers to any container or router process.

This table summarizes the cases:

| container type | component exit status |  crossbar behavior
| ---------------|-----------------------|---------------------------------
| container      |  clean                | if last, shutdown container cleanly
| container      |  fail                 | if last, shutdown container with error
| router         |  clean                | nothing
| router         |  fail                 | shutdown router with error


The behavior of the crossbar process iteself is dependent upon configuration options. The default is `shutdown_on_worker_exit`.

 - `shutdown_on_worker_exit`: if any worker exits, crossbar itself will shutdown
 - `shutdown_on_worker_exit_with_error`: if any worker exits with an error, crossbar itself will shutdown
 - `shutdown_on_last_worker_exit`: when *all* workers exit, crossbar itself will shutdown
 - `shutdown_on_shutdown_requested`: only exit if requested to via the management API

In the configuration, this option is specified inside the `controller`, like this:

```javascript
    "controller": {
        "options": {
            "shutdown": "shutdown_on_worker_exit_with_error"
        }
    }
```
