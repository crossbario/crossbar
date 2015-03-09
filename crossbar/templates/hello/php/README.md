# Hello WAMP with PHP/Thruway

A [PHP](http://www.php.net/)/[Thruway](https://github.com/voryx/Thruway)-based "Hello world!" example WAMP application.

**See: [Getting started with PHP](https://github.com/crossbario/crossbar/wiki/Getting-started-with-PHP)**

## How to run

Install dependencies (once):

```shell
make install
```

Start Crossbar by doing:

```shell
crossbar start
```

Open [`http://localhost:8080/`](http://localhost:8080/) (or wherever Crossbar runs) in your browser.

## How to hack

All PHP backend code is in `client.php`. All JavaScript frontend code is in `./web/index.html`.
