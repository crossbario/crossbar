title: Getting started with Erlang
toc: [Documentation, Getting Started, Getting started with Erlang]

# Getting started with Erlang

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application written in Erlang using [Erwa](https://github.com/bwegh/erwa), an open-source Erlang WAMP implementation (both client and router). The generated application includes a JavaScript frontend to run in a browser.

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server and Erlang/Erwa application component host.

## Prerequisites

Install [Erlang](http://www.erlang.org/):

    sudo apt-get install erlang

## Create an example application

To create a new Crossbar.io node and generate a [Erlang](http://www.erlang.org/) / [Erwa](https://github.com/bwegh/erwa) based "Hello world!" example application:

    crossbar init --template hello:erlang --appdir $HOME/hello

This will initialize a new node and application under `$HOME/hello` using the application template `hello:erlang`.

> To get a list of available templates, use `crossbar templates`.

You should see the application template being initialized:

```console
oberstet@vbox-ubuntu1310:~$ crossbar init --template hello:erlang --appdir $HOME/hello
Crossbar.io application directory '/home/oberstet/hello' created
Initializing application template 'hello:erlang' in directory '/home/oberstet/hello'
Creating directory /home/oberstet/hello/web
Creating directory /home/oberstet/hello/.crossbar
Creating directory /home/oberstet/hello/src
Creating directory /home/oberstet/hello/rel
Creating file      /home/oberstet/hello/erlang.mk
Creating file      /home/oberstet/hello/.gitignore
Creating file      /home/oberstet/hello/README.md
Creating file      /home/oberstet/hello/relx.config
Creating file      /home/oberstet/hello/Makefile
Creating file      /home/oberstet/hello/web/autobahn.min.js
Creating file      /home/oberstet/hello/web/index.html
Creating file      /home/oberstet/hello/.crossbar/config.json
Creating file      /home/oberstet/hello/src/crossbar_client.erl
Creating file      /home/oberstet/hello/src/crossbar_client_sup.erl
Creating file      /home/oberstet/hello/src/crossbar_client_app.erl
Creating file      /home/oberstet/hello/src/crossbar_client.app.src
Creating file      /home/oberstet/hello/rel/sys.config
Application template initialized

Now build the Erlang/Erwa client by entering 'make', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.
```

## Build the example

To build the example:

    cd $HOME/hello
    make

## Start the node

Start your new Crossbar.io node using:

    cd $HOME/hello
    crossbar start

You should see the node starting:

```console
oberstet@vbox-ubuntu1310:~/hello$ crossbar start
2014-06-25 23:32:54+0200 [Controller   7097] Log opened.
2014-06-25 23:32:54+0200 [Controller   7097] ============================== Crossbar.io ==============================

2014-06-25 23:32:54+0200 [Controller   7097] Crossbar.io 0.9.6 starting
2014-06-25 23:32:55+0200 [Controller   7097] Running on CPython using EPollReactor reactor
2014-06-25 23:32:55+0200 [Controller   7097] Starting from node directory /home/oberstet/hello/.crossbar
2014-06-25 23:32:56+0200 [Controller   7097] Starting from local configuration '/home/oberstet/hello/.crossbar/config.json'
2014-06-25 23:32:56+0200 [Controller   7097] No WAMPlets detected in enviroment.
2014-06-25 23:32:56+0200 [Controller   7097] Starting Router with ID 'worker1' ..
2014-06-25 23:32:56+0200 [Router       7106] Log opened.
2014-06-25 23:32:57+0200 [Router       7106] Running under CPython using EPollReactor reactor
2014-06-25 23:32:57+0200 [Router       7106] Entering event loop ..
2014-06-25 23:32:57+0200 [Controller   7097] Router with ID 'worker1' and PID 7106 started
2014-06-25 23:32:57+0200 [Router       7106] CrossbarWampRawSocketServerFactory starting on 5555
2014-06-25 23:32:57+0200 [Controller   7097] Router 'worker1': transport 'transport1' started
2014-06-25 23:32:57+0200 [Router       7106] Monkey-patched MIME table (0 of 551 entries)
2014-06-25 23:32:57+0200 [Router       7106] Site starting on 8080
2014-06-25 23:32:57+0200 [Controller   7097] Router 'worker1': transport 'transport2' started
2014-06-25 23:32:57+0200 [Controller   7097] Starting Guest with ID 'worker2' ..
2014-06-25 23:32:57+0200 [Controller   7097] GuestWorkerClientProtocol.connectionMade
2014-06-25 23:32:57+0200 [Controller   7097] Guest with ID 'worker2' and PID 7110 started
2014-06-25 23:32:57+0200 [Controller   7097] Guest 'worker2': started
2014-06-25 23:32:57+0200 [Guest        7110] Exec: /home/oberstet/hello/_rel/crossbar_client/erts-5.10.2/bin/erlexec -noshell -noinput +Bd -boot /home/oberstet/hello/_rel/crossbar_client/releases/1/crossbar_client -mode embedded -config /home/oberstet/hello/_rel/crossbar_client/releases/1/sys.config -args_file /home/oberstet/hello/_rel/crossbar_client/releases/1/vm.args -- foreground
2014-06-25 23:32:57+0200 [Guest        7110] Root: /home/oberstet/hello/_rel/crossbar_client
2014-06-25 23:32:58+0200 [Guest        7110] starting client ... done.
2014-06-25 23:32:58+0200 [Guest        7110] connecting to realm <<"realm1">> at "localhost":5555 ...
2014-06-25 23:32:58+0200 [Guest        7110] done (1309258613243581).
2014-06-25 23:32:58+0200 [Guest        7110] subscribe to <<"com.example.onhello">> ...
2014-06-25 23:32:58+0200 [Guest        7110] subscribed (3068871086277393).
2014-06-25 23:32:58+0200 [Guest        7110] register <<"com.example.add2">> ...
2014-06-25 23:32:58+0200 [Guest        7110] registered (8274624887582561).
2014-06-25 23:32:58+0200 [Guest        7110] starting the timer ...
2014-06-25 23:32:58+0200 [Guest        7110] done
2014-06-25 23:32:58+0200 [Guest        7110] client sucessfully initialized.
2014-06-25 23:32:59+0200 [Guest        7110] tick
2014-06-25 23:32:59+0200 [Guest        7110] mul2() error no_such_procedure
2014-06-25 23:33:00+0200 [Guest        7110] tick
...
```

The Crossbar example configuration has started a WAMP router and a guest worker running the Erlang/Erwa based application component. It also runs a Web server for serving static Web content.


## Open the frontend

Open [`http://localhost:8080/`](http://localhost:8080/) (or wherever Crossbar runs) in your browser. When you watch the browser's JavaScript console.

You have just watched the Erlang backend component talking to the JavaScript frontend component and vice-versa. The calls and events were exchanged over [WAMP](http://wamp.ws/) and routed by Crossbar.io between the application components.

## Hacking the code

All the Erlang backend code is in `src/crossbar_client.erl` while all the JavaScript frontend code is in `web/index.html`.

The code in both the backend and the frontend each performs all four main interactions:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

Here is the Erlang backend component:

```erlang
-module(crossbar_client).
-behaviour(gen_server).

-define(RPC_MUL2_URL,<<"com.example.mul2">>).
-define(RPC_ADD2_URL,<<"com.example.add2">>).
-define(EVENT_ONHELLO_URL,<<"com.example.onhello">>).
-define(EVENT_ONCOUNTER_URL,<<"com.example.oncounter">>).
-define(REALM,<<"realm1">>).
-define(HOST,"localhost"). % has to be a string
-define(PORT,5555).
-define(ENCODING,msgpack). %% msgpack or json

-export([start_link/0]).

%% gen_server
-export([init/1]).
-export([handle_call/3]).
-export([handle_cast/2]).
-export([handle_info/2]).
-export([terminate/2]).
-export([code_change/3]).

-export([add2/4]).
-export([on_hello/4]).

-record(state,{
  con = undefined,
  session = undefined,
  counter = 0 }).


start_link() ->
  gen_server:start_link(?MODULE, [], []).

init(_) ->
  io:format("starting client ... "),
  {ok,Con} = erwa:start_client(),
  io:format("done.~nconnecting to realm ~p at ~p:~p ... ",[?REALM,?HOST,?PORT]),
  {ok,SessionId,_RouterDetails} = erwa:connect(Con,?HOST,?PORT,?REALM,?ENCODING),
  io:format("done (~p).~nsubscribe to ~p ... ",[SessionId,?EVENT_ONHELLO_URL]),
  {ok,SubId} = erwa:subscribe(Con,[{}],?EVENT_ONHELLO_URL,{crossbar_client,on_hello,[]}),
  io:format("subscribed (~p).~nregister ~p ... ",[SubId,?RPC_ADD2_URL]),
  {ok,RegId} = erwa:register(Con,[{}],?RPC_ADD2_URL,{crossbar_client,add2,[]}),
  io:format("registered (~p).~nstarting the timer ...",[RegId]),
  ok = timer:start(),
  {ok,_TRef} = timer:send_after(1000,on_timer),
  io:format("done~n"),
  io:format("client sucessfully initialized.~n"),
  {ok,#state{con=Con,session=SessionId}}.

on_hello(_Details,Arguments,ArgumentsKw,_) ->
  io:format("onhello(): ~p ~p~n",[Arguments,ArgumentsKw]),
  ok.

add2(_Details,[A,B],_ArgumentsKw,_) ->
  io:format("add2() called with ~p and ~p",[A,B]),
  {ok,[{}],[A+B],undefined}.


handle_call(_,_From,State) ->
  {noreply,State}.

handle_cast(_Msg,State) ->
  {noreply,State}.

handle_info(on_timer,#state{con=Con, counter=Counter}=State) ->
  io:format("tick~n"),
  ok = erwa:publish(Con,[{}],?EVENT_ONCOUNTER_URL,[Counter]),
  case erwa:call(Con,[{}],?RPC_MUL2_URL,[Counter,3]) of
    {ok,_Details,ResA,_ResAkw} ->
      io:format("mul2() result: ~p~n",ResA);
    {error,_Details,Error,_Arguments,_ArgumentsKw} ->
      io:format("mul2() error ~p~n",[Error])
    end,
  {ok,_TRef} = timer:send_after(1000,on_timer),
  {noreply,State#state{counter=Counter+1}};

handle_info(Msg,State) ->
  io:format("~nreceived unknown message: ~p~n",[Msg]),
  {noreply,State}.

terminate(_Reason,_State) ->
  ok.

code_change(_OldVsn,State,_Extra) ->
  {ok,State}.
```

And here the JavaScript frontend component:

```javascript
// the URL of the WAMP Router (Crossbar.io)
//
var wsuri = "ws://localhost:8080/ws";


// the WAMP connection to the Router
//
var connection = new autobahn.Connection({
   url: wsuri,
   realm: "realm1"
});


// timers
//
var t1, t2;


// fired when connection is established and session attached
//
connection.onopen = function (session, details) {

   console.log("Connected");

   // SUBSCRIBE to a topic and receive events
   //
   function on_counter (args) {
      var counter = args[0];
      console.log("on_counter() event received with counter " + counter);
   }
   session.subscribe('com.example.oncounter', on_counter).then(
      function (sub) {
         console.log('subscribed to topic');
      },
      function (err) {
         console.log('failed to subscribe to topic', err);
      }
   );


   // PUBLISH an event every second
   //
   t1 = setInterval(function () {

      session.publish('com.example.onhello', ['Hello from JavaScript (browser)']);
      console.log("published to topic 'com.example.onhello'");
   }, 1000);


   // REGISTER a procedure for remote calling
   //
   function mul2 (args) {
      var x = args[0];
      var y = args[1];
      console.log("mul2() called with " + x + " and " + y);
      return x * y;
   }
   session.register('com.example.mul2', mul2).then(
      function (reg) {
         console.log('procedure registered');
      },
      function (err) {
         console.log('failed to register procedure', err);
      }
   );


   // CALL a remote procedure every second
   //
   var x = 0;

   t2 = setInterval(function () {

      session.call('com.example.add2', [x, 18]).then(
         function (res) {
            console.log("add2() result:", res);
         },
         function (err) {
            console.log("add2() error:", err);
         }
      );

      x += 3;
   }, 1000);
};


// fired when connection was lost (or could not be established)
//
connection.onclose = function (reason, details) {
   console.log("Connection lost: " + reason);
   if (t1) {
      clearInterval(t1);
      t1 = null;
   }
   if (t2) {
      clearInterval(t2);
      t2 = null;
   }
}


// now actually open the connection
//
connection.open();
```
