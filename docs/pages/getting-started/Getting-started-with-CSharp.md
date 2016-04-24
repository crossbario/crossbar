[Documentation](.) > [Choose your Weapon](Choose your Weapon) > Getting started with C Sharp

# Getting started with C Sharp

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application written in C# using [WampSharp](https://github.com/Code-Sharp/WampSharp), an open-source WAMP implementation. The generated application includes a JavaScript frontend to run in a browser.

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server and WampSharp application component host.


## Prerequisites

To build the generated C# WAMP application component, you will need a .NET toolchain. I am using **Microsoft Visual Studio Express 2012 for Windows Desktop**.

> This version of Visual Studio also already includes [NuGet](https://www.nuget.org/) which we will use to automatically get project dependencies (including WampSharp).


## Running the demo app

### Initialize the application template

To instantiate the demo application template, run the following from an arbitrary directory (like `$HOME/mynode1`):

    crossbar init --template hello:csharp

You should see log output like the following:

```console
$ crossbar init --template hello:csharp
Initializing application template 'hello:csharp' in directory 'c:\Temp'
Using templates from 'c:/Python27/lib/site-packages/crossbar-0.9.8_5-py2.7.egg/crossbar/templates/hello/csharp'
Creating directory c:\Temp\.crossbar
Creating directory c:\Temp\src
Creating directory c:\Temp\web
Creating file      c:\Temp\.gitignore
Creating file      c:\Temp\.crossbar\config.json
Creating directory c:\Temp\src\Hello
Creating file      c:\Temp\src\Hello.sln
Creating directory c:\Temp\src\Hello\Properties
Creating file      c:\Temp\src\Hello\App.config
Creating file      c:\Temp\src\Hello\Hello.csproj
Creating file      c:\Temp\src\Hello\packages.config
Creating file      c:\Temp\src\Hello\Program.cs
Creating file      c:\Temp\src\Hello\Properties\AssemblyInfo.cs
Creating file      c:\Temp\web\autobahn.min.js
Creating file      c:\Temp\web\index.html
Application template initialized

Now build by opening 'src/Hello/Hello.sln' in Visual Studio, start Crossbar using 'crossbar start' and open http://local
host:8080 in your browser.
```

### Building the application component

Now open `src/Hello/Hello.sln` in Visual Studio by double clicking the file. Go to the menu entry `TOOLS -> Library Package Manager -> Package Manager Console` in Visual Studio and enter:

    Install-Package WampSharp.Default -Pre

Then press F7 to build the solution.


### Start the Crossbar.io node

Now start the Crossbar.io node:

    crossbar start

You should see the node and the C# WAMP application component starting:

```console
$ crossbar start
2014-10-18 15:27:42+0200 [Controller   5660] Log opened.
2014-10-18 15:27:42+0200 [Controller   5660] ============================== Crossbar.io ==============================

2014-10-18 15:27:42+0200 [Controller   5660] Crossbar.io 0.9.8-5 starting
2014-10-18 15:27:42+0200 [Controller   5660] Running on CPython using IOCPReactor reactor
2014-10-18 15:27:42+0200 [Controller   5660] Starting from node directory c:\Temp\node1\.crossbar
2014-10-18 15:27:42+0200 [Controller   5660] Starting from local configuration 'c:\Temp\node1\.crossbar\config.json'
2014-10-18 15:27:42+0200 [Controller   5660] Warning, could not set process title (setproctitle not installed)
2014-10-18 15:27:43+0200 [Controller   5660] Detected 2 WAMPlets in environment:
2014-10-18 15:27:43+0200 [Controller   5660] WAMPlet clandeck.irc
2014-10-18 15:27:43+0200 [Controller   5660] WAMPlet clandeck.twitter
2014-10-18 15:27:43+0200 [Controller   5660] Starting Router with ID 'worker1' ..
2014-10-18 15:27:43+0200 [Router       5256] Log opened.
2014-10-18 15:27:43+0200 [Router       5256] Warning: could not set worker process title (setproctitle not installed)
2014-10-18 15:27:43+0200 [Router       5256] Running under CPython using IOCPReactor reactor
2014-10-18 15:27:44+0200 [Router       5256] Entering event loop ..
2014-10-18 15:27:44+0200 [Controller   5660] Router with ID 'worker1' and PID 5256 started
2014-10-18 15:27:44+0200 [Controller   5660] Router 'worker1': PYTHONPATH extended
2014-10-18 15:27:44+0200 [Controller   5660] Router 'worker1': realm 'realm1' started
2014-10-18 15:27:44+0200 [Controller   5660] Router 'worker1': role 'role1' started on realm 'realm1'
2014-10-18 15:27:44+0200 [Controller   5660] Router 'worker1': transport 'transport1' started
2014-10-18 15:27:44+0200 [Controller   5660] Starting Guest with ID 'worker2' ..
2014-10-18 15:27:44+0200 [Controller   5660] GuestWorkerClientProtocol.connectionMade
2014-10-18 15:27:44+0200 [Controller   5660] Guest with ID 'worker2' and PID 6028 started
2014-10-18 15:27:44+0200 [Controller   5660] Guest 'worker2': started
2014-10-18 15:27:44+0200 [Router       5256] Site starting on 8080
2014-10-18 15:27:44+0200 [Guest        6028] WampSharp Hello demo starting ...
2014-10-18 15:27:44+0200 [Guest        6028] Connecting to ws://127.0.0.1:8080/ws, realm realm1
2014-10-18 15:27:45+0200 [Guest        6028] subscribed to topic 'onhello'
2014-10-18 15:27:45+0200 [Guest        6028] procedure add2() registered
2014-10-18 15:27:45+0200 [Guest        6028] published to 'oncounter' with counter 0
2014-10-18 15:27:46+0200 [Guest        6028] published to 'oncounter' with counter 1
...
```

Now open your browser at [http://127.0.0.1:8080](http://127.0.0.1:8080) and watch the JavaScript console output.

## The code

The generated C# code looks like this:

```csharp
using System;
using System.Reactive.Subjects;
using System.Threading.Tasks;
using WampSharp.Core.Listener;
using WampSharp.V2;
using WampSharp.V2.Client;
using WampSharp.V2.Core.Contracts;
using WampSharp.V2.Realm;
using WampSharp.V2.Rpc;

namespace Hello
{
    public class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("WampSharp Hello demo starting ...");

            string wsuri = "ws://127.0.0.1:8080/ws";
            string realm = "realm1";
            if (args.Length > 0) {
               wsuri = args[0];
               if (args.Length > 1) {
                  realm = args[1];
               }
            }

            Task runTask = Run(wsuri, realm);

            Console.ReadLine();
        }

        private async static Task Run(string wsuri, string realm)
        {
            Console.WriteLine("Connecting to {0}, realm {1}", wsuri, realm);

            DefaultWampChannelFactory factory = new DefaultWampChannelFactory();

            IWampChannel channel =
                factory.CreateJsonChannel(wsuri, realm);

            IWampClientConnectionMonitor monitor = channel.RealmProxy.Monitor;

            monitor.ConnectionBroken += OnClose;
            monitor.ConnectionError += OnError;

            await channel.Open().ConfigureAwait(false);

            IWampRealmServiceProvider services = channel.RealmProxy.Services;

            // SUBSCRIBE to a topic and receive events
            ISubject<string> helloSubject =
                services.GetSubject<string>("com.example.onhello");

            IDisposable subscription =
                helloSubject.Subscribe
                    (x => Console.WriteLine("event for 'onhello' received: {0}", x));

            Console.WriteLine("subscribed to topic 'onhello'");


            // REGISTER a procedure for remote calling
            Add2Service callee = new Add2Service();

            await services.RegisterCallee(callee)
                .ConfigureAwait(false);

            Console.WriteLine("procedure add2() registered");


            // PUBLISH and CALL every second... forever
            ISubject<int> onCounterSubject =
                services.GetSubject<int>("com.example.oncounter");

            IMul2Service proxy =
                services.GetCalleeProxy<IMul2Service>();

            int counter = 0;

            while (true)
            {
                // PUBLISH an event
                onCounterSubject.OnNext(counter);
                Console.WriteLine("published to 'oncounter' with counter {0}", counter);
                counter++;


                // CALL a remote procedure
                try
                {
                    int result = await proxy.Multiply(counter, 3)
                        .ConfigureAwait(false);

                    Console.WriteLine("mul2() called with result: {0}", result);
                }
                catch (WampException ex)
                {
                    if (ex.ErrorUri != "wamp.error.no_such_procedure")
                    {
                        Console.WriteLine("call of mul2() failed: " + ex);
                    }
                }


                await Task.Delay(TimeSpan.FromSeconds(1))
                    .ConfigureAwait(false);
            }
        }

        #region Callee

        public interface IAdd2Service
        {
            [WampProcedure("com.example.add2")]
            int Add(int x, int y);
        }

        public class Add2Service : IAdd2Service
        {
            public int Add(int x, int y)
            {
                Console.WriteLine("add2() called with {0} and {1}", x, y);
                return x + y;
            }
        }

        #endregion

        #region Caller

        public interface IMul2Service
        {
            [WampProcedure("com.example.mul2")]
            Task<int> Multiply(int x, int y);
        }

        #endregion

        private static void OnClose(object sender, WampSessionCloseEventArgs e)
        {
            Console.WriteLine("connection closed. reason: " + e.Reason);
        }

        private static void OnError(object sender, WampConnectionErrorEventArgs e)
        {
            Console.WriteLine("connection error. error: " + e.Exception);
        }
    }
}
```
