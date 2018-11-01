var isBrowser = false;

try {
    var autobahn = require('autobahn');
} catch (e) {
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

connection.onopen = function (session, details) {
    console.log("session open!", details);

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

connection.onclose = function (reason, details) {
    console.log("session closed: " + reason, details);
}

connection.open();
