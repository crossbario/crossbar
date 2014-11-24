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

var tessel = require('tessel');
var autobahn = require('wamp-tessel');

var leds = [tessel.led[0], tessel.led[1]];

// replace IP below with IP of computer running Crossbar.io
var connection = new autobahn.Connection({
   url: "ws://192.168.1.134:8080/ws", 
   realm: "realm1"
});

connection.onopen = function (session) {

   console.log("connected");

   // SUBSCRIBE to a topic and receive events
   //
   function onhello (args) {
      var msg = args[0];
      console.log("event for 'onhello' received: " + msg);
      leds[0].toggle();
   }
   session.subscribe('com.example.onhello', onhello).then(
      function (sub) {
         console.log("subscribed to topic 'onhello'");
      },
      function (err) {
         console.log("failed to subscribed: " + err);
      }
   );


   // REGISTER a procedure for remote calling
   //
   function add2 (args) {
      var x = args[0];
      var y = args[1];
      console.log("add2() called with " + x + " and " + y);
      return x + y;
   }
   session.register('com.example.add2', add2).then(
      function (reg) {
         console.log("procedure add2() registered");
      },
      function (err) {
         console.log("failed to register procedure: " + err);
      }
   );


   // PUBLISH and CALL every second .. forever
   //
   var counter = 0;
   setInterval(function () {

      // PUBLISH an event
      //
      session.publish('com.example.oncounter', [counter]);
      console.log("published to 'oncounter' with counter " + counter);

      // CALL a remote procedure
      //
      session.call('com.example.mul2', [counter, 3]).then(
         function (res) {
            console.log("mul2() called with result: " + res);
            leds[1].toggle();
         },
         function (err) {
            if (err.error !== 'wamp.error.no_such_procedure') {
               console.log('call of mul2() failed: ' + err);
            }
         }
      );

      counter += 1;
   }, 1000);
};

connection.open();
