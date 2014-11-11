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


// This challenge callback will authenticate our backend component
//
function onchallenge (session, method, extra) {

   console.log("onchallenge", method, extra);

   if (method === "wampcra") {

      console.log("authenticating via '" + method + "' and challenge '" + extra.challenge + "'");

      return autobahn.auth_cra.sign(process.argv[5], extra.challenge);

   } else {
      throw "don't know how to authenticate using '" + method + "'";
   }
}


var connection = new autobahn.Connection({
   url: process.argv[2],
   realm: process.argv[3],

   // The following authentication information is for authenticating
   // our backend component
   //
   authid: process.argv[4],
   authmethods: ["wampcra"],
   onchallenge: onchallenge
});


connection.onopen = function (session) {

   console.log("backend connected");

   var topics = [
      'com.example.topic1',
      'com.example.topic2',
      'com.foobar.topic1',
      'com.foobar.topic2'   
   ];

   topics.forEach(function (topic) {
      function onhello (args) {
         var msg = args[0];
         console.log("event received on topic " + topic + ": " + msg);
      }
      session.subscribe(topic, onhello).then(
         function () {
            console.log("ok, subscribed to topic " + topic);
         },
         function (e) {
            console.log("could not subscribe to topic " + topic + ": " + e.error);
         }
      );
   });

   function add2 (args) {
      var x = args[0];
      var y = args[1];
      console.log("add2() called with " + x + " and " + y);
      return x + y;
   }

   session.register('com.example.add2', add2).then(
      function () {
         console.log("procedure add2() registered");
      },
      function (err) {
         console.log("could not register procedure", err);
      }
   );
};


connection.onclose = function (reason, details) {
   console.log("Connection lost:", reason, details);
}


connection.open();
