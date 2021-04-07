# Node logs

The master node receives node logs events from the management uplinks
coming from (edge) nodes connected to the master.

The master node persists received events in zLMDB databases using a
database schema with tables

* log -> node -> mrealm -> user

Analyzing the node log maintained by the master node allow to compute
aggregated usage data. Here is how to read tables from the master node:


```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx/test/test_nodelog$ python test_nodelog.py 

52 node log records so far
owner, mrealm, node, time, #routers, #containers, #guests, #marketmakers
superuser mrealm1 node1 2019-05-14T17:39:09.490890178 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:39:50.812433517 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:00.792169602 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:10.786195293 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:20.790742620 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:30.792636706 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:40.790232465 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:40:50.791513545 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:41:00.787395861 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:41:10.810902090 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:41:20.792408553 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:41:30.791614933 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:44:26.121980884 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:44:36.159296751 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:44:46.159587518 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:44:56.163120027 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:45:06.212297534 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:45:16.160142791 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:45:26.162360382 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:45:36.160919571 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:45:50.967920972 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:00.961435248 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:10.965793588 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:20.950098628 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:30.935027196 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:40.934658188 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:46:50.936909645 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:00.940719932 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:10.965127053 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:20.962240447 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:30.937644329 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:40.935115553 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:47:50.936809708 2 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:00.934715540 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:03.704631338 0 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:10.964888597 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:13.731553286 0 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:20.971234903 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:23.697337670 0 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:30.981604636 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:33.699652739 0 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:40.940593587 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:48.787305369 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:48:50.931857035 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:48:58.759720472 1 0 0 0
superuser mrealm1 node1 2019-05-14T17:49:00.941503429 2 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:08.793794088 1 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:18.758409459 1 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:28.758079915 1 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:38.757069890 1 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:48.758263647 1 0 0 0
superuser mrealm1 node2 2019-05-14T17:49:58.757891938 1 0 0 0
```
