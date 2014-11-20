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

$userDb = [
    // A user with an unsalted password
    'joe'   => [
        'secret' => 'secret2',
        'role'   => 'frontend'
    ],
    // A user with a salted password
    'peter' => [
        'secret'     => 'prq7+YkJ1/KlW1X0YczMHw==',
        'role'       => 'frontend',
        'salt'       => 'salt123',
        'iterations' => 100,
        'keylen'     => 16
    ]
];


$authenticate = function ($args) use ($userDb) {
    $realm  = array_shift($args);
    $authid = array_shift($args);

    echo "authenticate called: {$realm}, {$authid}\n";

    if (isset($userDb[$authid])) {
        return $userDb[$authid];
    }

    echo "no such user: {$realm}, {$authid}\n";
};

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

$connection->on('open', function (ClientSession $session) use ($connection, $authenticate) {

    echo "custom authenticator connected\n";

    $session->register('com.example.authenticate', $authenticate)->then(
        function () {
            echo "Ok, custom WAMP-CRA authenticator procedure registered\n";
        },
        function ($error) {
            echo "Uups, could not register custom WAMP-CRA authenticator {$error}\n";
        }
    );
});

$connection->on('close', function ($reason) {
    echo "The authenticator client connection has closed with reason: {$reason}\n";
});

$connection->on('error', function ($reason) {
    echo "The authenticator client connection has closed with error: {$reason}\n";
});

$connection->open();
