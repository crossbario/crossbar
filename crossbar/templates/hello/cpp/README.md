# Hello WAMP in C++11

A [C++11](http://en.wikipedia.org/wiki/C%2B%2B11) / [AutobahnCpp](https://github.com/tavendo/AutobahnCpp) based "Hello world!" example WAMP application.

**See: [Getting started with C++](http://crossbar.io/docs/Getting-started-with-Cplusplus/)**

## How to run

Build the app using [SCons](http://scons.org/):

```shell
scons
```

Start Crossbar by doing:

```shell
crossbar start
```

Open [`http://localhost:8080/`](http://localhost:8080/) (or wherever Crossbar runs) in your browser.

## How to hack

All C++ backend code is in `hello.cpp`. All JavaScript frontend code is in `./web/index.html`.
