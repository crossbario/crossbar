<?php

###############################################################################
##
##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
##
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################

use Thruway\ClientSession;
use Thruway\Connection;

require __DIR__ . '/vendor/autoload.php';

$onClose = function ($msg) {
    echo $msg;
};

$connection = new Connection(
    array(
        "realm" => 'realm1',
        "onClose" => $onClose,
        "url" => 'ws://127.0.0.1:8080/ws',
    )
);

$connection->on('open', function (ClientSession $session) use ($connection) {


        // SUBSCRIBE to a topic and receive events
        $onHello = function ($args) {
            echo "event for 'onhello' received: {$args[0]}\n";
        };
        $session->subscribe('com.example.onhello', $onHello);
        echo "subscribed to topic 'onhello'";


        // REGISTER a procedure for remote calling
        $add2 = function ($args) {
            echo "add2() called with {$args[0]} and {$args[1]}\n";
            return $args[0] + $args[1];
        };
        $session->register('com.example.add2', $add2);
        echo "procedure add2() registered\n";


        // PUBLISH and CALL every second .. forever
        $counter = 0;
        while (true) {

            // PUBLISH an event
            $session->publish('com.example.oncounter', array($counter));
            echo "published to 'oncounter' with counter {$counter}\n";
            $counter++;

            // CALL a remote procedure
            $session->call('com.example.mul2', array($counter, 3))->then(
                function ($res) {
                    echo "mul2() called with result: {$res}\n";
                },
                function ($error) {
                    if ($error !== 'wamp.error.no_such_procedure') {
                        echo "call of mul2() failed: {$error}\n";
                    }
                }
            );

            // Tell the connection to process the events every second
            $connection->doEvents(1);

        }
    }
);

$connection->open();