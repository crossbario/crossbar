try {
   var autobahn = require('autobahn');
} catch (e) {
   // when running in browser, AutobahnJS will
   // be included without a module system
}

var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1'}
);

connection.onopen = function (session) {

   function onevent1(args) {
      console.log("Got event:", args[0]);
      document.getElementById('WAMPEvent').innerHTML = "Events:"+ args[0];
   }

   session.subscribe('com.myapp.hello', onevent1);
};

connection.open();
