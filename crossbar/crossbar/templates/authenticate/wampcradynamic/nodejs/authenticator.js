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

var USERDB = {
   'joe': {
      'secret': 'secret2',
      'role': 'frontend'
   },
   'peter': {
      // autobahn.auth_cra.derive_key("secret1", "salt123", 100, 16);
      'secret': 'prq7+YkJ1/KlW1X0YczMHw==',
      'role': 'frontend',
      'salt': 'salt123',
      'iterations': 100,
      'keylen': 16
   }
};

function authenticate (args) {
   var realm = args[0];
   var authid = args[1];

   console.log("authenticate called:", realm, authid);

   if (USERDB[authid] !== undefined) {
      return USERDB[authid];
   } else {
      throw "no such user";
   }
}

var connection = new autobahn.Connection({
   url: process.argv[2],
   realm: process.argv[3]
});

connection.onopen = function (session) {

   console.log("connected");
   session.register('com.example.authenticate', authenticate).then(
      function () {
         console.log("Ok, custom WAMP-CRA authenticator procedure registered");
      },
      function (err) {
         console.log("Uups, could not register custom WAMP-CRA authenticator", err);
      }
   );
};

connection.open();
