# Erlang/Erwa

An [Erlang](http://www.erlang.org/)/[Erwa](https://github.com/bwegh/erwa)-based "Hello world!" example WAMP application.

**See: [Getting started with Erlang](https://github.com/crossbario/crossbar/wiki/Getting-started-with-Erlang)**

## How to run

Build the app by doing:

```shell
make
```

Start Crossbar by doing:

```shell
crossbar start
```

Open [`http://localhost:8080/`](http://localhost:8080/) (or wherever Crossbar runs) in your browser.

## How to hack

All Erlang backend code is in `./src/*`. All JavaScript frontend code is in `./web/index.html`.
