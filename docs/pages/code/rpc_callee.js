// Example WAMP client for AutobahnJS connecting to a Crossbar.io WAMP router.
// AutobahnJS, the WAMP client library to connect and talk to Crossbar.io:
var isBrowser = false;
try {
    var autobahn = require('autobahn');
} catch (e) {
    // when running in browser, AutobahnJS will
    // be included without a module system
    isBrowser = true;
}
console.log("Running AutobahnJS " + autobahn.version);

if (isBrowser) {
    url = 'ws://127.0.0.1:8080/ws';
    realm = 'realm1';
}
else {
    url = process.env.CBURL;
    realm = process.env.CBREALM;
}
var connection = new autobahn.Connection({ url: url, realm: realm });
console.log("Running AutobahnJS " + url+ "  "+realm);

// .. and fire this code when we got a session
connection.onopen = function (session, details) {
    console.log("session open!", details);
    // Your code goes here: use WAMP via the session you got to
    // call, register, subscribe and publish ..
    function utcnow() {
        console.log("Someone is calling com.myapp.date");
        now = new Date();
        return now.toISOString();
    }
    session.register('com.myapp.date', utcnow).then(
        function (registration) {
            console.log("Procedure registered:", registration.id);
        },
        function (error) {
            console.log("Registration failed:", error);
        }
    );
};

// .. and fire this code when our session has gone
connection.onclose = function (reason, details) {
    console.log("session closed: " + reason, details);
}

// Don't forget to actually trigger the opening of the connection!
connection.open();
