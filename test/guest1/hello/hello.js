var autobahn = require('autobahn');

var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1'}
);

connection.onopen = function (session) {

   function hello() {
      return "Hello from NodeJS!";
   }

   session.register('com.hello.hello', hello).then(
      function (registration) {
         console.log("Ok, procedure registered with ID", registration.id);
      },
      function (error) {
         console.log("Error: could not register procedure - ", error);
      }
   );
};

connection.open();
