<?php

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