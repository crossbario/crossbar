//###############################################################################
//##
//##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
//##
//##  Redistribution and use in source and binary forms, with or without
//##  modification, are permitted provided that the following conditions are met:
//##
//##  1. Redistributions of source code must retain the above copyright notice,
//##     this list of conditions and the following disclaimer.
//##
//##  2. Redistributions in binary form must reproduce the above copyright notice,
//##     this list of conditions and the following disclaimer in the documentation
//##     and/or other materials provided with the distribution.
//##
//##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
//##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
//##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
//##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
//##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
//##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
//##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
//##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
//##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
//##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
//##  POSSIBILITY OF SUCH DAMAGE.
//##
//###############################################################################

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
