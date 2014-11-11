///////////////////////////////////////////////////////////////////////////////
//
//  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
//
//  Redistribution and use in source and binary forms, with or without
//  modification, are permitted provided that the following conditions are met:
//
//  1. Redistributions of source code must retain the above copyright notice,
//     this list of conditions and the following disclaimer.
//
//  2. Redistributions in binary form must reproduce the above copyright notice,
//     this list of conditions and the following disclaimer in the documentation
//     and/or other materials provided with the distribution.
//
//  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
//  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
//  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
//  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
//  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
//  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
//  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
//  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
//  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
//  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
//  POSSIBILITY OF SUCH DAMAGE.
//
///////////////////////////////////////////////////////////////////////////////

var autobahn = require('autobahn');


if (true) {
   // authenticate using authid "joe"
   var user = "joe";
   var key = "secret2";
} else {
   // authenticate using authid "peter", and using a salted password
   var user = "peter";
   var key = autobahn.auth_cra.derive_key("secret1", "salt123", 100, 16);
}


// This challenge callback will authenticate our frontend component
//
function onchallenge (session, method, extra) {

   console.log("onchallenge", method, extra);

   if (method === "wampcra") {

      console.log("authenticating via '" + method + "' and challenge '" + extra.challenge + "'");

      return autobahn.auth_cra.sign(key, extra.challenge);

   } else {
      throw "don't know how to authenticate using '" + method + "'";
   }
}


var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1',

   // The following authentication information is for authenticating
   // our frontend component
   //
   authid: user,
   authmethods: ["wampcra"],
   onchallenge: onchallenge
});


connection.onopen = function (session) {

   console.log("frontend connected");

   var done = [];

   // call a procedure we are allowed to call (so this should succeed)
   //
   done.push(session.call('com.example.add2', [2, 3]).then(
      function (res) {
         console.log("call result: " + res);
      },
      function (e) {
         console.log("call error: " + e.error);
      }
   ));

   // (try to) register a procedure where we are not allowed to (so this should fail)
   //
   done.push(session.register('com.example.mul2', function (args) { return args[0] * args[1]; }).then(
      function () {
         console.log("Uups, procedure registered .. but that should have failed!");
      },
      function (e) {
         console.log("registration failed - this is expected: " + e.error);
      }
   ));

   // (try to) publish to some topics
   //
   var topics = [
      'com.example.topic1',
      'com.example.topic2',
      'com.foobar.topic1',
      'com.foobar.topic2'   
   ];

   topics.forEach(function (topic) {
      done.push(session.publish(topic, null, null, {acknowledge: true}).then(
         function () {
            console.log("ok, published to topic " + topic);
         },
         function (e) {
            console.log("could not publish to topic " + topic + ": " + e.error);
         }
      ));
   });

   // close the session when everything is done. we have to
   // use this construct, since all ops run asynch and might
   // not yet be completed when we reach this line ..
   //
   autobahn.when.all(done).then(
      function () {
         session.leave();
      }
   );
};


connection.onclose = function (reason, details) {
   console.log("Connection lost:", reason, details);
}


connection.open();
