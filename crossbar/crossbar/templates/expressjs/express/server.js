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

var express = require('express');
var nunjucks = require('nunjucks');
var autobahn = require('autobahn');

// this is our Express application
var app = express();

// serve static content from /static directory
app.use('/static', express.static(__dirname + '/static'));

// configure Nunjucks templating engine for Express
nunjucks.configure('views', {
   autoescape: true,
   express: app
});

// this will hold a WAMP client session when connected
// to WAMP router (Crossbar.io)
app.session = null;

// here we count the number of visits to the root HTML page
app.visits = 0;

// setup a route for rendering the root HTML page
app.get('/', function (req, res) {
   app.visits += 1;

   // when the WAMP session is ready ..
   if (app.session) {

      // .. PUBLISH an event to the topic "com.example.on_visit"
      // with the total number of visits as payload
      app.session.publish('com.example.on_visit', [app.visits]);
   }

   // render the root HTML page, providing the visit count
   // as a variable for use within the page template
   res.render('index.html', {visitors: app.visits});
});

// setup a route for rendering the live monitor HTML page
app.get('/monitor', function (req, res) {
   res.render('monitor.html');
});

// start Express and listen on this port
app.listen(8080);


// create a connection to WAMP router (Crossbar.io)
//
var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:9000',
   realm: 'realm1'}
);

connection.onopen = function (session) {
   console.log("connected to WAMP router");
   app.session = session;

   // REGISTER a procedure for remote calling
   //
   function get_visits () {
      return app.visits;
   }
   session.register('com.example.get_visits', get_visits).then(
      function (reg) {
         console.log("procedure get_visits() registered");
      },
      function (err) {
         console.log("failed to register procedure: " + err);
      }
   );
};

connection.onclose = function (reason, details) {
   console.log("WAMP connection closed", reason, details);
   app.session = null;
}

connection.open();
