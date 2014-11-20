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

$user     = $argv[3];
$password = $argv[4];

$onChallenge = function (ClientSession $session, $method, ChallengeMessage $msg) use ($user, $password) {

    if ("wampcra" !== $method) {
        return false;
    }

    $cra = new ClientWampCraAuthenticator($user, $password);
    return $cra->getAuthenticateFromChallenge($msg)->getSignature();
};

$connection = new Connection(
    [
        "realm"       => $argv[2],
        "url"         => $argv[1],
        "authmethods" => ["wampcra"],
        "onChallenge" => $onChallenge,
        "authid"      => $user
    ]
);

$connection->on('open', function (ClientSession $session) use ($connection) {

    echo "backend connected session with ID {$session->getSessionId()}\n";

    // Subscribe to topics
    //
    $topics = [
        'com.example.topic1',
        'com.example.topic2',
        'com.foobar.topic1',
        'com.foobar.topic2'
    ];

    foreach ($topics as $topic) {

        $onHello = function ($args) use ($topic) {
            $msg = array_shift($args);
            echo "event received on topic  {$topic}: {$msg}\n";
        };

        $session->subscribe($topic, $onHello)->then(
            function ($pub) use ($topic) {
                echo "ok, subscribed to topic {$topic}\n";
            },
            function ($error) use ($topic) {
                echo "could not subscribe to topic {$topic} failed: {$error}\n";
            }
        );
    }

    $add2 = function ($args) {
        $x = array_shift($args);
        $y = array_shift($args);
        echo "add2() called with  {$x} and {$y}\n";
        return $x + $y;
    };

    $session->register('com.example.add2', $add2)->then(
        function () {
            echo "procedure add2() registered\n";
        },
        function ($error) {
            echo "could not register procedure {$error}";
        });

});

$connection->on('close', function ($reason) {
    echo "The backend client connection has closed with reason: {$reason}\n";
});

$connection->on('error', function ($reason) {
    echo "The backend client connection has closed with error: {$reason}\n";
});

$connection->open();
