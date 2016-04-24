[Documentation](.) > [Administration](Administration) > Processes

# Processes

Crossbar.io has a multi-process architecture. There is one node controller process per node

* [**Controller** Configuration](Controller Configuration)

and multiple worker processes of these types

* [**Router** Configuration](Router Configuration)
* [**Container** Configuration](Container Configuration)
* [**Guest** Configuration](Guest Configuration)

Processes can be further configured with

* [Process Environments](Process Environments)
* [Native Worker Options](Native Worker Options)

For Crossbar.io developers, there is also

* [Manhole](Manhole)

## Configuration

The **controller** is configured in the node's configuration like here

```javascript
{
    "controller": {
        // controller configuration
    }
}
```

Read more in [**Controller** Configuration](Controller Configuration).

**Workers** are configured in a node's local configuration like this

```javascript
{
    "workers": [
        {
            "type": "..."
        }
    ]
}
```

There are valid values for the `type` of worker:

* `"router"` - see [Router Configuration](Router Configuration)
* `"container"` - see [Container Configuration](Container Configuration)
* `"guest"` - see [Guest Configuration](Guest Configuration)

---
