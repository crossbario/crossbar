# Master automation testing

## Automated CI test using Docker Crossbar.io

To test:

```console
./test_automated.sh
```

.. wait .. see [here](https://asciinema.org/a/351460) for a recording ..

Then open:

* [http://localhost:8080/info](http://localhost:8080/info): client endpoint (HAProxy)
* [http://localhost:8081/info](http://localhost:8081/info): node 1 (directly)
* [http://localhost:8082/info](http://localhost:8082/info): node 2 (directly)
* [http://localhost:8083/info](http://localhost:8083/info): node 3 (directly)
* [http://localhost:9000/info](http://localhost:9000/info): master node
* [http://localhost:1936/](http://localhost:1936/): HAProxy statistics


Add the following to `/etc/hosts`:

```console
127.0.0.1	localhost master node1 node2 node3 node4
```


## Manual test using host Crossbar.io

In a first terminal, run:

```console
rm -rf ./.test
make init_nodes
make run_master
```

In another terminal, run:

```console
make run_node1
```

Repeat for `node2` and `node3`.

Now in another terminal, run:

```console
./test_setup1.sh
```

Finally, start one or more test clients:

```console
python client.py --realm myrealm1
```

There are four realm running (`myrealm1`, `myrealm2`, `myrealm3`, `myrealm4`).
