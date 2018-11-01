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

   var received = 0;
   var textmessage =  "Closed after recieving 5 events, Hit F5 to refresh";

   function onevent1(args) {
      console.log("Got event:", args[0]);
      document.getElementById('WAMPEvent').innerHTML = "Events:"+ args[0];
      received += 1;
      if (received > 5) {
         console.log("Closing ..");
         document.getElementById('WAMPEvent').textContent= textmessage;
         connection.close();
      }
   }

   session.subscribe('com.myapp.hello', onevent1);
};

connection.open();
