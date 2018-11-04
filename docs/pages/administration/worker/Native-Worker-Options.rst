
Native Worker Options
=====================

**Native Workers**, that is *Routers* and *Containers* can be further
configured with ``options``.

Both *Routers* and *Containers* share the following ``options``:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | The  |
| titl | work |
| e``* | er   |
| *    | proc |
|      | ess  |
|      | titl |
|      | e    |
|      | (def |
|      | ault |
|      | :    |
|      | ``"c |
|      | ross |
|      | bar- |
|      | work |
|      | er [ |
|      | rout |
|      | er]" |
|      | ``   |
|      | or   |
|      | ``"c |
|      | ross |
|      | bar- |
|      | work |
|      | er [ |
|      | cont |
|      | aine |
|      | r]"` |
|      | `)   |
+------+------+
| **`` | The  |
| pyth | Pyth |
| on`` | on   |
| **   | exec |
|      | utab |
|      | le   |
|      | to   |
|      | run  |
|      | the  |
|      | Work |
|      | er   |
|      | with |
|      | ,    |
|      | e.g. |
|      | ``/o |
|      | pt/p |
|      | ytho |
|      | n27/ |
|      | bin/ |
|      | pyth |
|      | on`` |
|      | -    |
|      | this |
|      | **mu |
|      | st** |
|      | be   |
|      | an   |
|      | abso |
|      | lute |
|      | path |
|      | (def |
|      | ault |
|      | :    |
|      | **sa |
|      | me   |
|      | as   |
|      | cont |
|      | roll |
|      | er** |
|      | )    |
+------+------+
| **`` | A    |
| pyth | list |
| onpa | of   |
| th`` | path |
| **   | s    |
|      | to   |
|      | prep |
|      | end  |
|      | to   |
|      | the  |
|      | Pyth |
|      | on   |
|      | seac |
|      | h    |
|      | path |
|      | ,    |
|      | e.g. |
|      | ``[" |
|      | ..", |
|      |  "/h |
|      | ome/ |
|      | joe/ |
|      | myst |
|      | uff" |
|      | ]``  |
|      | (def |
|      | ault |
|      | :    |
|      | **[] |
|      | **)  |
+------+------+
| **`` | The  |
| cpu_ | work |
| affi | er   |
| nity | CPU  |
| ``** | affi |
|      | nity |
|      | to   |
|      | set  |
|      | - a  |
|      | list |
|      | of   |
|      | CPU  |
|      | IDs  |
|      | (int |
|      | eger |
|      | s),  |
|      | e.g. |
|      | ``[0 |
|      | , 1] |
|      | ``   |
|      | (def |
|      | ault |
|      | :    |
|      | **un |
|      | set* |
|      | *)   |
|      | -    |
|      | curr |
|      | entl |
|      | y    |
|      | only |
|      | supp |
|      | orte |
|      | d    |
|      | on   |
|      | Linu |
|      | x    |
|      | and  |
|      | Wind |
|      | ows, |
|      | `not |
|      | on   |
|      | Free |
|      | BSD  |
|      | <htt |
|      | ps:/ |
|      | /git |
|      | hub. |
|      | com/ |
|      | giam |
|      | paol |
|      | o/ps |
|      | util |
|      | /iss |
|      | ues/ |
|      | 566> |
|      | `__  |
+------+------+
| **`` | Choo |
| reac | se   |
| tor` | the  |
| `**  | type |
|      | of   |
|      | Twis |
|      | ted  |
|      | reac |
|      | tor, |
|      | inst |
|      | ead  |
|      | of   |
|      | the  |
|      | one  |
|      | chos |
|      | en   |
|      | auto |
|      | mati |
|      | call |
|      | y.   |
|      | See  |
|      | belo |
|      | w.   |
+------+------+
| **`` | Plea |
| env` | se   |
| `**  | see  |
|      | `Pro |
|      | cess |
|      | Envi |
|      | ronm |
|      | ents |
|      |  <Pr |
|      | oces |
|      | s-En |
|      | viro |
|      | nmen |
|      | ts>` |
|      | __.  |
+------+------+

Selecting a **Twisted reactor** is platform-based: ``reactor`` takes a
dictionary as an argument, with the platform as the keys and a single
reactor per platform as the value.

Platform values which are handled are ``bsd`` (with possible prefixes),
``darwin``, ``win32`` and ``linux``, while reactor values are
``select``, ``poll``, ``epoll``, ``kqueue``, and ``iocp``.

Additionally, the **process environment** for the worker can be
determined using the option ``env`` - for more information see [[Process
Environments]].
