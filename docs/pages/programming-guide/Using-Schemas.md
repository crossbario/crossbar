[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > Session > Using Schemas

# Using Schemas

## Programmatic Use

The reflection services of Crossbar.io are exposed via two procedures

 * `wamp.reflect.describe`
 * `wamp.reflect.define`

and two topics

 * `wamp.reflect.on_define`
 * `wamp.reflect.on_undefine`

For example, here is how you would call `describe` to retrieve all schema information available in the realm connected to:

```javascript
var connection = new autobahn.Connection({
   url: "ws://127.0.0.1:8080/ws",
   realm: "realm1"
});

connection.onopen = function (session, details) {
   console.log("connected");
   session.call('wamp.reflect.describe').then(
      function (schemas) {
         console.log("schemas in realm:", schemas);
      },
      function (err) {
         console.log("failed to retrieve schemas", err);
      }
   );
};

connection.onclose = function (reason, details) {
   console.log("Connection lost: " + reason);
}

connection.open();
```

You can run above in an enclosing HTML like this:

```html
<!DOCTYPE html>
<html>
   <body>
      <h1>WAMP reflection and metadata with Crossbar.io</h1>
      <script src="autobahn.min.js"></script>
      <script>
      ... JavaScript code from above ...
      </script>
   </body>
</html>
```



### wamp.reflect.describe

```javascript
{
   "$schema": "http://wamp.ws/schema#",
   "uri": "wamp.reflect.describe",
   "type": "procedure",
   "title": "Describe URI",
   "description": "Describe WAMP procedures, topics and errors. \
      The procedure takes an optional URI argument to only query \
      a single URIs declaration."
   "args": {
      "type": "array",
      "items": [
         {
            "type": "string",
            "title": "uri",
            "description": "When provided, restrict query to this URI, \
               otherwise return schema information for all URIs."
         }
      ]
   }
}
```
