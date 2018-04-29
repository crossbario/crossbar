title: Process Environments toc: [Documentation, Administration,
Processes, Process Environments]

Process Environments
====================

Crossbar.io **Workers** (*Routers*, *Containers* and *Guests*) process
enviroments can be tuned via configuration.

Here is an example Guest process:

.. code:: json

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

The ``options.env`` dictionary has the following configuration
parameters:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | If   |
| inhe | ``Tr |
| rit` | ue`` |
| `**  | ,    |
|      | inhe |
|      | rit  |
|      | the  |
|      | comp |
|      | lete |
|      | cont |
|      | roll |
|      | er   |
|      | envi |
|      | rome |
|      | nt.  |
|      | If   |
|      | ``Fa |
|      | lse` |
|      | `,   |
|      | don' |
|      | t    |
|      | inhe |
|      | rit  |
|      | anyt |
|      | hing |
|      | .    |
|      | If a |
|      | list |
|      | ,    |
|      | only |
|      | inhe |
|      | rit  |
|      | the  |
|      | list |
|      | of   |
|      | envi |
|      | rome |
|      | nt   |
|      | vari |
|      | able |
|      | s    |
|      | give |
|      | n    |
|      | (def |
|      | ault |
|      | :    |
|      | **Tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | A    |
| vars | dict |
| ``** | iona |
|      | ry   |
|      | of   |
|      | envi |
|      | ronm |
|      | ent  |
|      | vari |
|      | able |
|      | s    |
|      | to   |
|      | set  |
|      | in   |
|      | the  |
|      | work |
|      | er,  |
|      | e.g. |
|      | ``{" |
|      | FOOB |
|      | AR": |
|      |  "bi |
|      | g"}` |
|      | `    |
|      | (def |
|      | ault |
|      | :    |
|      | **{} |
|      | **)  |
+------+------+

``options.env`` allows you to control the environment that the process
will run under.

If ``options.env.inherit`` is a ``bool``, the value determines whether
the parent's (Crossbar.io node controller) environment will be inherited
by the guest/worker.

If ``options.env.inherit`` is a ``list``, the values in the list specify
the environment variables from the parent's environment that will be
inherited:

.. code:: json

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

Finally, ``options.env.vars`` allows you to provide a dictionary (of
string-value keys and values) that provide (an additional) list of
enviroment variables to set.

    Please note that on Windows, certain restrictions apply due to
    `this <http://twistedmatrix.com/trac/ticket/1640>`__. In particular,
    you cannot empty the enviroment of a guest/worker by setting
    ``inherit == false``.
