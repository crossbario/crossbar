WebSocket Options
=================

Crossbar.io is built on an advanced and complete WebSocket
implementation that exposes various options and tunables you might be
interested in, especially if you take your server to production.

    For options related to WebSocket compression, please see
    `here <WebSocket%20Compression>`__.

To set options on a WebSocket transport, add an ``options`` dictionary
to the transport configuration part. Here is an example:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "url": "ws://localhost:8080",
       "options": {
          "enable_webstatus": false
       }
    }

Above will run a WebSocket transport, but disable the automatic
rendering of a server status page when the WebSocket server is accessed
from a regular Web client that does not upgrade to WebSocket.

Available Options
-----------------

The available options are:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | A    |
| allo | list |
| wed_ | of   |
| orig | allo |
| ins` | wed  |
| `**  | WebS |
|      | ocke |
|      | t    |
|      | orig |
|      | ins  |
|      | -    |
|      | can  |
|      | use  |
|      | ``*` |
|      | `    |
|      | as a |
|      | wild |
|      | card |
|      | char |
|      | acte |
|      | r,   |
|      | e.g. |
|      | ``[" |
|      | http |
|      | s:// |
|      | *.ta |
|      | vend |
|      | o.co |
|      | m",  |
|      | "htt |
|      | p:// |
|      | loca |
|      | lhos |
|      | t:80 |
|      | 80"] |
|      | ``   |
+------+------+
| **`` | The  |
| exte | *ext |
| rnal | erna |
| _por | l*   |
| t``* | visi |
| *    | ble  |
|      | port |
|      | this |
|      | serv |
|      | ice  |
|      | be   |
|      | reac |
|      | habl |
|      | e    |
|      | unde |
|      | r    |
|      | (i.e |
|      | .    |
|      | when |
|      | runn |
|      | ing  |
|      | behi |
|      | nd   |
|      | a    |
|      | L2/L |
|      | 3    |
|      | forw |
|      | ardi |
|      | ng   |
|      | devi |
|      | ce)  |
|      | (def |
|      | ault |
|      | :    |
|      | **nu |
|      | ll** |
|      | )    |
+------+------+
| **`` | Enab |
| enab | le   |
| le_h | Hybi |
| ybi1 | -10  |
| 0``* | vers |
| *    | ion  |
|      | of   |
|      | WebS |
|      | ocke |
|      | t    |
|      | (an  |
|      | inte |
|      | rmed |
|      | iary |
|      | spec |
|      | ).   |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Enab |
| enab | le   |
| le_r | RFC6 |
| fc64 | 455  |
| 55`` | vers |
| **   | ion  |
|      | of   |
|      | WebS |
|      | ocke |
|      | t    |
|      | (the |
|      | fina |
|      | l    |
|      | spec |
|      | ).   |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Enab |
| enab | le   |
| le_w | the  |
| ebst | WebS |
| atus | ocke |
| ``** | t    |
|      | serv |
|      | er's |
|      | stat |
|      | us   |
|      | rend |
|      | erin |
|      | g    |
|      | page |
|      | .    |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Vali |
| vali | date |
| date | inco |
| _utf | ming |
| 8``* | WebS |
| *    | ocke |
|      | t    |
|      | text |
|      | mess |
|      | ages |
|      | for  |
|      | UTF8 |
|      | conf |
|      | orma |
|      | nce. |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Mask |
| mask | serv |
| _ser | er-s |
| ver_ | ent  |
| fram | WebS |
| es`` | ocke |
| **   | t    |
|      | fram |
|      | es.  |
|      | WARN |
|      | ING: |
|      | Enab |
|      | ling |
|      | this |
|      | will |
|      | brea |
|      | k    |
|      | prot |
|      | ocol |
|      | comp |
|      | lian |
|      | ce!  |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | Requ |
| requ | ire  |
| ire_ | all  |
| mask | WebS |
| ed_c | ocke |
| lien | t    |
| t_fr | fram |
| ames | es   |
| ``** | rece |
|      | ived |
|      | to   |
|      | be   |
|      | mask |
|      | ed.  |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Actu |
| appl | ally |
| y_ma | appl |
| sk`` | y    |
| **   | WebS |
|      | ocke |
|      | t    |
|      | mask |
|      | ing  |
|      | (bot |
|      | h    |
|      | in-  |
|      | and  |
|      | outg |
|      | oing |
|      | ).   |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Maxi |
| max_ | mum  |
| fram | size |
| e_si | in   |
| ze`` | byte |
| **   | s    |
|      | of   |
|      | inco |
|      | ming |
|      | WebS |
|      | ocke |
|      | t    |
|      | fram |
|      | es   |
|      | acce |
|      | pted |
|      | or 0 |
|      | to   |
|      | allo |
|      | w    |
|      | any  |
|      | size |
|      | .    |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | Maxi |
| max_ | mum  |
| mess | size |
| age_ | in   |
| size | byte |
| ``** | s    |
|      | of   |
|      | inco |
|      | ming |
|      | WebS |
|      | ocke |
|      | t    |
|      | mess |
|      | ages |
|      | acce |
|      | pted |
|      | or 0 |
|      | to   |
|      | allo |
|      | w    |
|      | any  |
|      | size |
|      | .    |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | Auto |
| auto | mati |
| _fra | call |
| gmen | y    |
| t_si | frag |
| ze`` | ment |
| **   | outg |
|      | oing |
|      | WebS |
|      | ocke |
|      | t    |
|      | mess |
|      | ages |
|      | into |
|      | WebS |
|      | ocke |
|      | t    |
|      | fram |
|      | es   |
|      | of   |
|      | payl |
|      | oad  |
|      | maxi |
|      | mum  |
|      | spec |
|      | ifie |
|      | d    |
|      | size |
|      | in   |
|      | byte |
|      | s    |
|      | or 0 |
|      | to   |
|      | disa |
|      | ble. |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | On   |
| fail | seve |
| _by_ | re   |
| drop | erro |
| ``** | rs   |
|      | (lik |
|      | e    |
|      | WebS |
|      | ocke |
|      | t    |
|      | prot |
|      | ocol |
|      | viol |
|      | atio |
|      | ns), |
|      | brut |
|      | ally |
|      | drop |
|      | the  |
|      | TCP  |
|      | conn |
|      | ecti |
|      | on   |
|      | inst |
|      | ead  |
|      | of   |
|      | perf |
|      | ormi |
|      | ng   |
|      | a    |
|      | full |
|      | WebS |
|      | ocke |
|      | t    |
|      | clos |
|      | ing  |
|      | hand |
|      | shak |
|      | e.   |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | Duri |
| echo | ng   |
| _clo | a    |
| se_c | WebS |
| oder | ocke |
| easo | t    |
| n``* | clos |
| *    | ing  |
|      | hand |
|      | shak |
|      | e    |
|      | init |
|      | iate |
|      | d    |
|      | by a |
|      | peer |
|      | ,    |
|      | echo |
|      | the  |
|      | peer |
|      | 's   |
|      | clos |
|      | e    |
|      | code |
|      | and  |
|      | reas |
|      | on.  |
|      | Othe |
|      | rwis |
|      | e    |
|      | repl |
|      | y    |
|      | with |
|      | code |
|      | 1000 |
|      | and  |
|      | no   |
|      | reas |
|      | on.  |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *)   |
+------+------+
| **`` | WebS |
| open | ocke |
| _han | t    |
| dsha | open |
| ke_t | ing  |
| imeo | hand |
| ut`` | shak |
| **   | e    |
|      | time |
|      | out  |
|      | in   |
|      | ms   |
|      | or 0 |
|      | to   |
|      | disa |
|      | ble. |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | WebS |
| clos | ocke |
| e_ha | t    |
| ndsh | clos |
| ake_ | ing  |
| time | hand |
| out` | shak |
| `**  | e    |
|      | time |
|      | out  |
|      | in   |
|      | ms   |
|      | or 0 |
|      | to   |
|      | disa |
|      | ble. |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | Set  |
| tcp_ | the  |
| node | TCP  |
| lay` | No-D |
| `**  | elay |
|      | ("Na |
|      | gle" |
|      | )    |
|      | sock |
|      | et   |
|      | opti |
|      | on   |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+
| **`` | Send |
| auto | a    |
| _pin | WebS |
| g_in | ocke |
| terv | t    |
| al`` | ping |
| **   | ever |
|      | y    |
|      | this |
|      | many |
|      | ms   |
|      | or 0 |
|      | to   |
|      | disa |
|      | ble. |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | Drop |
| auto | the  |
| _pin | conn |
| g_ti | ecti |
| meou | on   |
| t``* | if   |
| *    | the  |
|      | peer |
|      | did  |
|      | not  |
|      | resp |
|      | ond  |
|      | to a |
|      | prev |
|      | ious |
|      | ly   |
|      | sent |
|      | ping |
|      | in   |
|      | this |
|      | many |
|      | ms   |
|      | or 0 |
|      | to   |
|      | disa |
|      | ble. |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | Payl |
| auto | oad  |
| _pin | size |
| g_si | for  |
| ze`` | ping |
| **   | s    |
|      | sent |
|      | ,    |
|      | must |
|      | be   |
|      | betw |
|      | een  |
|      | **4* |
|      | *    |
|      | and  |
|      | **12 |
|      | 5**  |
|      | (def |
|      | ault |
|      | :    |
|      | **4* |
|      | *)   |
+------+------+
| **`` | enab |
| comp | le   |
| ress | WebS |
| ion` | ocke |
| `**  | t    |
|      | comp |
|      | ress |
|      | ion  |
|      | -    |
|      | see  |
|      | `Web |
|      | Sock |
|      | et   |
|      | Comp |
|      | ress |
|      | ion  |
|      | <Web |
|      | Sock |
|      | et-C |
|      | ompr |
|      | essi |
|      | on>` |
|      | __   |
+------+------+
| **`` | Requ |
| requ | ire  |
| ire_ | WebS |
| webs | ocke |
| ocke | t    |
| t_su | clie |
| bpro | nts  |
| toco | to   |
| l``* | prop |
| *    | erly |
|      | anno |
|      | unce |
|      | the  |
|      | WAMP |
|      | -Web |
|      | Sock |
|      | et   |
|      | subp |
|      | roto |
|      | cols |
|      | it   |
|      | is   |
|      | able |
|      | to   |
|      | spea |
|      | k.   |
|      | This |
|      | can  |
|      | be   |
|      | one  |
|      | or   |
|      | more |
|      | from |
|      | ``wa |
|      | mp.2 |
|      | .jso |
|      | n``, |
|      | ``wa |
|      | mp.2 |
|      | .msg |
|      | pack |
|      | ``,  |
|      | ``wa |
|      | mp.2 |
|      | .jso |
|      | n.ba |
|      | tche |
|      | d``  |
|      | and  |
|      | ``wa |
|      | mp.2 |
|      | .jso |
|      | n.ba |
|      | tche |
|      | d``. |
|      | Cros |
|      | sbar |
|      | .io  |
|      | will |
|      | by   |
|      | defa |
|      | ult  |
|      | **re |
|      | quir |
|      | e**  |
|      | the  |
|      | clie |
|      | nt   |
|      | to   |
|      | anno |
|      | unce |
|      | the  |
|      | subp |
|      | roto |
|      | cols |
|      | it   |
|      | supp |
|      | orts |
|      | and  |
|      | sele |
|      | ct   |
|      | **on |
|      | e**  |
|      | of   |
|      | the  |
|      | anno |
|      | unce |
|      | d    |
|      | subp |
|      | roto |
|      | cols |
|      | .    |
|      | If   |
|      | this |
|      | opti |
|      | on   |
|      | is   |
|      | set  |
|      | to   |
|      | ``fa |
|      | lse` |
|      | `,   |
|      | Cros |
|      | sbar |
|      | .io  |
|      | will |
|      | no   |
|      | long |
|      | er   |
|      | requ |
|      | ire  |
|      | the  |
|      | clie |
|      | nt   |
|      | to   |
|      | anno |
|      | unce |
|      | subp |
|      | roto |
|      | cols |
|      | and  |
|      | assu |
|      | me   |
|      | ``wa |
|      | mp.2 |
|      | .jso |
|      | n``  |
|      | when |
|      | no   |
|      | WebS |
|      | ocke |
|      | t    |
|      | subp |
|      | roto |
|      | col  |
|      | is   |
|      | anno |
|      | unce |
|      | d.   |
|      | (def |
|      | ault |
|      | :    |
|      | **tr |
|      | ue** |
|      | )    |
+------+------+

Production Settings
-------------------

For example, here is a configuration for a production WebSocket service
with conservative settings:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "url": "ws://myserver.com:8080",
       "options": {
          "enable_webstatus": false,
          "max_frame_size": 1048576,
          "max_message_size": 1048576,
          "auto_fragment_size": 65536,
          "fail_by_drop": true,
          "open_handshake_timeout": 2500,
          "close_handshake_timeout": 1000,
          "auto_ping_interval": 10000,
          "auto_ping_timeout": 5000,
          "auto_ping_size": 4
       }
    }
