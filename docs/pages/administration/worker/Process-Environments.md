[Documentation](.) > [Administration](Administration) > [Processes](Processes) > Process Environments

# Process Environments

Crossbar.io **Workers** (*Routers*, *Containers* and *Guests*) process enviroments can be tuned via configuration.

Here is an example Guest process:


```json
{
   "workers": [
      {
         "type": "guest",
         "executable": "/usr/bin/env",
         "options": {
            "env": {
               "inherit": false,
               "vars": {
                  "AWESOME": "sure"
               }
            }
         }
      }
   ]
}
```

The `options.env` dictionary has the following configuration parameters:

option | description
---|---
**`inherit`** | If `True`, inherit the complete controller enviroment. If `False`, don't inherit anything. If a list, only inherit the list of enviroment variables given (default: **True**)
**`vars`** | A dictionary of environment variables to set in the worker, e.g. `{"FOOBAR": "big"}` (default: **{}**)


`options.env` allows you to control the environment that the process will run under.

If `options.env.inherit` is a `bool`, the value determines whether the parent's (Crossbar.io node controller) environment will be inherited by the guest/worker.

If `options.env.inherit` is a `list`, the values in the list specify the environment variables from the parent's environment that will be inherited:

```json
{
   "workers": [
      {
         "type": "guest",
         "executable": "/usr/bin/env",
         "options": {
            "env": {
               "inherit": ["HOME", "JAVA_HOME"],
               "vars": {
                  "AWESOME": "sure"
               }
            }
         }
      }
   ]
}
```

Finally, `options.env.vars` allows you to provide a dictionary (of string-value keys and values) that provide (an additional) list of enviroment variables to set.

> Please note that on Windows, certain restrictions apply due to [this](http://twistedmatrix.com/trac/ticket/1640). In particular, you cannot empty the enviroment of a guest/worker by setting `inherit == false`.
