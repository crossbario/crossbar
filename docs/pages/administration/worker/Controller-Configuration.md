[Documentation](.) > [Administration](Administration) > [Processes](Processes) > Controller Configuration

# Controller Configuration

When a Crossbar.io node starts, initially only a single process is started: the **node controller**.

The node controller is the master process of everything. At each time, there is exactly one node controller process running. When the node controller process has ended, the Crossbar.io node is down.

The node controller can be configured using the `controller` item in the node's configuration:

```json
{
   "controller": {
      "id": "mynode1",
      "options": {
         "title": "mycontroller"
      }
   }
}
```

The available parameters in the `controller` dictionary are:

option | description
---|---
**`id`** | The ID of the node (default: **hostname** of machine)
**`options`** | Controller process options - see below (default: **`{}`**).
**`manager`** | Uplink Crossbar.io management application (**upcoming**).
**`manhole`** | [Manhole](Manhole) into the controller.

The available `options` are:

option | description
---|---
**`title`** | The controller process title (default: **`"crossbar-controller"`**)

---
