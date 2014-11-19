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

use Psr\Log\NullLogger;
use Thruway\ClientSession;
use Thruway\ClientWampCraAuthenticator;
use Thruway\Connection;
use Thruway\Logging\Logger;
use Thruway\Message\ChallengeMessage;

require __DIR__ . '/vendor/autoload.php';

Logger::set(new NullLogger());

$user     = "joe";
$password = "secret2";

$onChallenge = function (ClientSession $session, $method, ChallengeMessage $msg) use ($user, $password) {

    if ("wampcra" !== $method) {
        return false;
    }

    $cra = new ClientWampCraAuthenticator($user, $password);
    return $cra->getAuthenticateFromChallenge($msg)->getSignature();
};

$connection = new Connection(
    [
        "realm"       => 'realm1',
        "url"         => 'ws://127.0.0.1:8080/ws',
        "authmethods" => ["wampcra"],
        "onChallenge" => $onChallenge,
        "authid"      => $user
    ]
);

$connection->on('open', function (ClientSession $session) use ($connection) {

    echo "connected session with ID {$session->getSessionId()}";

    // call a procedure we are allowed to call (so this should succeed)
    //
    $session->call('com.example.add2', [2, 3])->then(
        function ($res) {
            echo "call result: {$res}\n";
        },
        function ($error) {
            if ($error !== 'wamp.error.no_such_procedure') {
                echo "call error: {$error}\n";
            }
        }
    );

    // (try to) register a procedure where we are not allowed to (so this should fail)
    //
    $session->register('com.example.mul2', function ($args) {
        return $args[0] * $args[1];
    })->then(
        function () {
            echo "Uups, procedure registered .. but that should have failed!\n";
        },
        function ($error) {
            echo "registration failed - this is expected: {$error}\n";
        }
    );

    // (try to) publish to some topics
    //
    $topics = [
        'com.example.topic1',
        'com.example.topic2',
        'com.foobar.topic1',
        'com.foobar.topic2'
    ];

    foreach ($topics as $topic) {

        $session->publish($topic, ["hi"], null, ["acknowledge" => true])->then(
            function ($pub) use ($topic) {
                echo "ok, published to topic: {$topic}\n";
            },
            function (\Thruway\Message\ErrorMessage $error) use ($topic) {
                echo "could not publish to topic {$topic}: {$error}\n";
            }
        );
    }
});

$connection->on('close', function ($reason) {
    echo "The client connection has closed with reason: {$reason}\n";
});

$connection->on('error', function ($reason) {
    echo "The client connection has closed with error: {$reason}\n";
});

$connection->open();
