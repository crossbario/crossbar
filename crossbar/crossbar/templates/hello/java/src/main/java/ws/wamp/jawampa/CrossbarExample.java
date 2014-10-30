/*
 * Copyright 2014 Matthias Einwag
 *
 * The jawampa authors license this file to you under the Apache License,
 * version 2.0 (the "License"); you may not use this file except in compliance
 * with the License. You may obtain a copy of the License at:
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */

package ws.wamp.jawampa;

import java.io.IOException;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import rx.Scheduler;
import rx.Subscription;
import rx.functions.Action0;
import rx.functions.Action1;
import rx.schedulers.Schedulers;
import ws.wamp.jawampa.ApplicationError;
import ws.wamp.jawampa.Request;
import ws.wamp.jawampa.WampError;
import ws.wamp.jawampa.WampClient;
import ws.wamp.jawampa.WampClientBuilder;

/**
 * A demo application that demonstrates all features of WAMP
 * and equals the demo applications of crossbar.io
 */
public class CrossbarExample {
    
    String url;
    String realm;
    
    WampClient client;
    
    Subscription addProcSubscription;
    Subscription counterPublication;
    Subscription onHelloSubscription;
    
    // Scheduler for this example
    ExecutorService executor = Executors.newSingleThreadExecutor();
    Scheduler rxScheduler = Schedulers.from(executor);
    
    static final int TIMER_INTERVAL = 1000; // 1s
    int counter = 0;
    
    CrossbarExample(String url, String realm) throws Exception {
        this.url = url;
        this.realm = realm;
    }
    
    /**
     * Main entry point of the example
     * @param args Expected are 2 arguments: The url of the router and the name of the realm
     * @throws Exception
     */
    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.out.println("Need 2 commandline arguments: Router URL and ream name");
            return;
        }
        
        new CrossbarExample(args[0], args[1]).run();
    }
    
    void run() {
        
        WampClientBuilder builder = new WampClientBuilder();
        try {
            builder.witUri(url)
                   .withRealm(realm)
                   .withInfiniteReconnects()
                   .withCloseOnErrors(true)
                   .withReconnectInterval(5, TimeUnit.SECONDS);
            client = builder.build();
        } catch (WampError e) {
            e.printStackTrace();
            return;
        }

        // Subscribe on the clients status updates
        client.statusChanged()
              .observeOn(rxScheduler)
              .subscribe(new Action1<WampClient.Status>() {
            @Override
            public void call(WampClient.Status t1) {
                System.out.println("Session status changed to " + t1);

                if (t1 == WampClient.Status.Connected) {
                    
                    // SUBSCRIBE to a topic and receive events
                    onHelloSubscription = client.makeSubscription("com.example.onhello", String.class)
                                                .observeOn(rxScheduler)
                                                .subscribe(new Action1<String>() {
                         @Override
                         public void call(String msg) {
                             System.out.println("event for 'onhello' received: " + msg);
                         }
                     }, new Action1<Throwable>() {
                         @Override
                         public void call(Throwable e) {
                             System.out.println("failed to subscribe 'onhello': " + e);
                         }
                     }, new Action0() {
                         @Override
                         public void call() {
                             System.out.println("'onhello' subscription ended");
                         }
                     });
                    
                    // REGISTER a procedure for remote calling
                    addProcSubscription = client.registerProcedure("com.example.add2")
                                                .observeOn(rxScheduler)
                                                .subscribe(new Action1<Request>() {
                        @Override
                        public void call(Request request) {
                            if (request.arguments() == null || request.arguments().size() != 2
                             || !request.arguments().get(0).canConvertToLong()
                             || !request.arguments().get(1).canConvertToLong())
                            {
                                try {
                                    request.replyError(new ApplicationError(ApplicationError.INVALID_PARAMETER));
                                } catch (ApplicationError e) { }
                            }
                            else {
                                long a = request.arguments().get(0).asLong();
                                long b = request.arguments().get(1).asLong();
                                request.reply(a + b);
                            }
                        }
                    }, new Action1<Throwable>() {
                        @Override
                        public void call(Throwable e) {
                            System.out.println("failed to register procedure: " + e);
                        }
                    }, new Action0() {
                        @Override
                        public void call() {
                            System.out.println("procedure subscription ended");
                        }
                    });
                    
                    // PUBLISH and CALL every second .. forever
                    counter = 0;
                    counterPublication = rxScheduler.createWorker().schedulePeriodically(new Action0() {
                        @Override
                        public void call() {
                            // PUBLISH an event
                            final int published = counter;
                            client.publish("com.example.oncounter", published)
                                  .observeOn(rxScheduler)
                                  .subscribe(new Action1<Long>() {
                                    @Override
                                    public void call(Long t1) {
                                        System.out.println("published to 'oncounter' with counter " + published);
                                    }
                                }, new Action1<Throwable>() {
                                    @Override
                                    public void call(Throwable e) {
                                        System.out.println("Error during publishing to 'oncounter': " + e);
                                    }
                                });
                            
                            // CALL a remote procedure
                            client.call("com.example.mul2", Long.class, counter, 3)
                                  .observeOn(rxScheduler)
                                  .subscribe(new Action1<Long>() {
                                    @Override
                                    public void call(Long result) {
                                        System.out.println("mul2() called with result: " + result);
                                    }
                                }, new Action1<Throwable>() {
                                    @Override
                                    public void call(Throwable e) {
                                        boolean isProcMissingError = false;
                                        if (e instanceof ApplicationError) {
                                            if (((ApplicationError) e).uri().equals("wamp.error.no_such_procedure"))
                                                isProcMissingError = true;
                                        }
                                        if (!isProcMissingError) {
                                            System.out.println("call of mul2() failed: " + e);
                                        }
                                    }
                                });
                            
                            counter++;
                        }
                    }, TIMER_INTERVAL, TIMER_INTERVAL, TimeUnit.MILLISECONDS);
                }
                else if (t1 == WampClient.Status.Disconnected) {
                    closeSubscriptions();
                }
            }
        }, new Action1<Throwable>() {
            @Override
            public void call(Throwable t) {
                System.out.println("Session ended with error " + t);
            }
        }, new Action0() {
            @Override
            public void call() {
                System.out.println("Session ended normally");
            }
        });

        client.open();
        
        waitUntilKeypressed();
        System.out.println("Shutting down");
        closeSubscriptions();
        client.close();
        try {
            client.getTerminationFuture().get();
        } catch (Exception e) {}
        
        executor.shutdown();
    }
    
    /**
     * Close all subscriptions (registered events + procedures)
     * and shut down all timers (doing event publication and calls)
     */
    void closeSubscriptions() {
        if (onHelloSubscription != null)
            onHelloSubscription.unsubscribe();
        onHelloSubscription = null;
        if (counterPublication != null)
            counterPublication.unsubscribe();
        counterPublication = null;
        if (addProcSubscription != null)
            addProcSubscription.unsubscribe();
        addProcSubscription = null;
    }
    
    private void waitUntilKeypressed() {
        try {
            System.in.read();
            while (System.in.available() > 0) {
                System.in.read();
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

}
