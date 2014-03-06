var autobahn = require('autobahn');
var when = require('when');

function read_config() {
   process.stdin.setEncoding('utf8');

   var buffer = '';
   var d = when.defer();

   process.stdin.on('readable', function (chunk) {
      var chunk = process.stdin.read();
      if (chunk !== null) {
         buffer += chunk;
      }
   });

   process.stdin.on('end', function () {
      try {
         var config = JSON.parse(buffer);
         d.resolve(config);
      }
      catch (e) {
         d.reject(e);
      }
   });

   return d.promise;
}

read_config().then(function (config) {

   var connection = new autobahn.Connection({
      url: config.url,
      realm: config.realm}
   );

   connection.onopen = function (session) {

      function utcnow() {
         console.log("Someone is calling me;)");
         now = new Date();
         return now.toISOString();
      }

      session.register('com.timeservice.now', utcnow).then(
         function (registration) {
            console.log("Procedure registered:", registration.id);
         },
         function (error) {
            console.log("Registration failed:", error);
         }
      );
   };

   connection.open();
});
