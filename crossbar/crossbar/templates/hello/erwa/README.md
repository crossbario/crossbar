Erwa simple client example
==========================

To try this example, you need GNU `make` and `git` in your PATH.
And you need a running wamp v2 router, listening at port 5555 for
incomming TCP connections with msgpack format (e.g. simple_router).

The client will connect to the realm _ws.wamp.test_ and will subscribe
to _ws.wamp.test.info_ and register the procedure _ws.wamp.test.echo_.

After receiving one event it will unsubsribe.
After receiving one call it will unregister the procedure.

To build the example, run the following command:

``` bash
$ make
```

To start the release in the foreground:

``` bash
$ ./_rel/simple_client/bin/simple_client console
```


Also have a look at simple_client.erl to see the implementation and
play around with it.
