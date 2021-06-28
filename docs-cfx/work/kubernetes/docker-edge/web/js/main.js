var profiles = new Profiles();

var default_profile = profiles.get_default_profile();

if (!default_profile) {
   var email = "tobias.oberstein@gmail.com";
   default_profile = profiles.create_profile({email: email});
}



STM32L476xx









console.log('running autobahn-js ' + autobahn.version);

function get_user_email() {
   var d = autobahn.defer();
   d.callback("tobias.oberstein@gmail.com");
   return d;
}

var keystore = new KeyStore(localStorage, 'com.crossbario.fabric.keystore', get_user_email);

//keystore.erase();

// try to get key store data from local storage
if (!keystore.load()) {
   keystore.init();
   keystore.save();
}


var config = {
   // either null, to connect to the global user management realm or
   // a specific management realm to which the user must have
   // access permissions.
   realm: null,
   //realm: "oberstet1",

   // the user email (used as authid)
   authid: keystore.user_email(),

   // enforce re-sending of new activation code
   request_new_activation_code: false
}

// the WebSocket-WAMP URL of Crossbar.io
if (document.location.origin == "file://") {
   config.url = "ws://127.0.0.1:9000/ws";

} else {
   config.url = (document.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
                 document.location.host + "/ws";
}

// set WAMP serializer to use (we know Fabric supports MessagePack)
config.serializers = [new autobahn.serializer.MsgpackSerializer()];

// this will auto-generate a new key seed (a secret) and store that
// in browser local storage if there isn't a key already
//config.pkey = autobahn.auth_cryptosign.load_private_key(config.private_key);

config.pkey = keystore.user_key();

if (keystore.user_key_status() == 'unverified') {
   // the activation code must be set exactly once during exchange
   config.activation_code = 'VNXP-TUJH-PK4F';
} else {
   config.activation_code = null;
}

// this will create and configure a connection using WAMP-cryptosign authentication
// the parameters are used as follows:
//    - url: the ws(s) router URL (required)
//    - authid: the user email (required for registration and during key activation)
//    - pkey: the private key to be used (eg from load_private_key())
//    - activation_code: The activation code to be used (only once!).
//    - request_new_activation_code:
var connection = autobahn.auth_cryptosign.create_connection(config);

// main app entry point
connection.onopen = function (session, details) {
   console.log("Connected:", session.id, details);

   if (keystore.user_key_status() !== 'verified') {
      keystore.data.user_key_status = 'verified';
      keystore.save();
      console.log('user key status save: new status is verified');
   }

   //
   // HERE: place app code here, eg calls into Crossbar.io Fabric Service API:
   //   - com.crossbario.fabric.show_fabric
   //
   session.call('com.crossbario.fabric.show_fabric', null, {verbose: true}).then(
      function (fabric_info) {
         console.log("Fabric run-time information", fabric_info);

         //
         // if we are connected to the global users realm, we can list our management realms:
         //
         if (fabric_info.type == 'users') {
            console.log("Connected to global users realm!");

            // list management realms
            session.call('com.crossbario.fabric.list_management_realms', null, {verbose: true}).then(
               function (mrealms) {
                  //
                  // if we won't have a management realm already, we create one:
                  //
                  if (mrealms.length == 0) {
                     session.call('com.crossbario.fabric.create_management_realm', ["oberstet1"]).then(
                        function (created) {
                           console.log("Management realm created", created);
                        },
                        function (err) {
                           console.log(err);
                        }
                     );
                  } else {
                     console.log("Management realms:", mrealms);
                  }
               },
               function (err) {
                  console.log(err);
               }
            );

            if (true) {
               console.log('Pairing node ..');
               var node_mrealm = 'oberstet1';
               var node_pubkey = '7582a95a7aff6c8e7d4c6bd5e2a2308b5f637b65c1cc510056707adea678e9ea';
               var node_authid = 'node1';
               session.call('com.crossbario.fabric.pair_node', [node_mrealm, node_pubkey, node_authid]).then(
                  function (res) {
                     console.log('Node paired!', res);
                  },
                  function (err) {
                     console.log(err);
                  }
               );
            }

         } else {
            console.log("Connected to management realm ", fabric_info.name);

            // list nodes
            session.call('com.crossbario.fabric.list_nodes', null, {verbose: true}).then(
               function (nodes) {
                  console.log("Nodes:", nodes);
               },
               function (err) {
                  console.log(err);
               }
            );
         }
      },
      function (err) {
         console.log(err);
      }
   );
};

// TODO: handle different failing cases appropriately in the app
connection.onclose = function (reason, details) {

   // A WAMP-cryptosign authentication request can fail for various reasons:

   if (details.reason == 'fabric.auth-failed.pending-activation') {
      console.log("PENDING-ACTIVATION:", details.message);
      // there already was an activation request sent: hence, that is pending
      // and the client should authenticate but provide an activation token
      // in the authextra in addition to the regular WAMP-cryptosign challenge
      // signing thing. you can override this behavior when "request_new_activation_code"
      // is set to "true", which forces generating/sending a new activation token

   } else if (details.reason == 'fabric.auth-failed.new-user-auth-code-sent') {
      console.log("NEW-USER-AUTH-CODE-SENT:", details.message);
      // a new activation token has been sent to the user email

   } else if (details.reason == 'fabric.auth-failed.no-pending-activation') {
      console.log("NO-PENDING-ACTIVATION:", details.message);
      // an activation token was provided where none was expected

   } else {
      console.log("Connection lost: " + reason, details);
      // a different reason, unrelated to WAMP-cryptosign occurred
   }
}

// trigger actual opening of the connection
connection.open();
