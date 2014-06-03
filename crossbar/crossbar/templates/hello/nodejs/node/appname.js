var autobahn = require('autobahn');

var connection = new autobahn.Connection({
   url: '{{ url }}',
   realm: '{{ realm }}'}
);

connection.onopen = function (session) {

   function hello() {
      return "Hello from NodeJS!";
   }

   session.register('com.{{ appname }}.hello', hello).then(
      function (registration) {
         console.log("Ok, procedure registered with ID", registration.id);
      },
      function (error) {
         console.log("Error: could not register procedure - ", error);
      }
   );
};

connection.open();
