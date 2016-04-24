[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > Session > Sample Authentication Flow

# A Sample Authentication Flow

## Introduction

Authentication is one of the topics which come up again and again in questions. There are many ways to implement a login workflow. This article describes one flow for both login and registration which uses WAMP exclusively and which we are using ourselves for Web apps.

Everything that follows uses a browser environment, but the flows can be used for other applications as well.

We will first take a look at the login and logout, and then how to add a registration step to these.

## Login

For the login we use WAMP-CRA and cookie authentication. 

WAMP-CRA is an implementation of a challenge-response authentication (see the docs for more information). The flow here is very simple: The user provides a username and a password, which will usually get from a login form. (Since we're using WAMP you don't submit the form, but we still use a form with the usual login markup to enable password managers to store and enter the credentials.) The username is sent over the wire, Crossbar.io sends a challenge, our local code derives the correct response using the password, this travels back to Crossbar.io - and we have an authenticated connection.

To enable this you need to configure WAMP-CRA in the Crossbar.io config. A simple version, using static authentication (i.e. the user credentials stored in the config file) would look like this:

```json
"transports": [
   {
      "type": "web",
      "endpoint": {
         "type": "tcp",
         "port": 8030
      },
      "paths": {
         ...
         "static": {
            "type": "websocket",
            "auth": {
               "wampcra": {
                  "type": "static",
                  "users": {
                     "user_a": {
                        "secret": "kdg89sdf89h3hjksdag7",
                        "role": "user"
                     }
                  }
               }                     
            }
         }
      }
   }
]
```

This works fine for applications where you have a limited and persistent number of users. For more complex deployments, dynamic authentication enables you to use a WAMP component to provide Crossbar.io with the secret, making it possible to use any external store for credentials that you want. For dynamic authentication, you'd change the above configuration to something like

```json
"transports": [
   {
      "type": "web",
      "endpoint": {
         "type": "tcp",
         "port": 8030
      },
      "paths": {
         ...
         "dynamic": {
            "type": "websocket",
            "auth": {
               "wampcra": {
                  "type": "dynamic",
                  "authenticator": "io.crossbar.examples.authenticate"
               }                        
            }
         }
      }
   }
]
```

You then also need the dynamic authentication component. This can be something as simple as:

```javascript
var authenticate = function (args) {

   var realm = args[0];
   var authId = args[1];
   var details = args[2];
   
   if (users[authId]) {
      return {"secret": users[authId].secret, "role": users[authId].role};   
   } else {
      throw "user unknown";
   }
  
};

session.register("io.crossbar.advanced.backend.authenticate", authenticate)
```

In the above example, user credentials are stored in a `users` object, but for real-life use you would have a database request here.

The login code in the client looks like this

```javascript
var onChallenge = function (session, method, extra) {
   if (method === "wampcra") {
      return autobahn.auth_cra.sign(password, extra.challenge);
   }
} 

connectionAuth = new autobahn.Connection({   
   realm: "crossbario_advanced",
   authmethods: ["wampcra"],
   authid: username,
   onchallenge: onChallenge
});

...

connectionAuth.open();
```

Since nobody loves logins, you can make life easier for your users by adding cookie authentication. For each WAMP connection, you can define a list of authentication methods to try. Since we want cookies to be used instead of WAMP-CRA when possible, we add cookie authentication before WAMP-CRA.

```javascript
connectionAuth = new autobahn.Connection({   
   realm: "crossbario_advanced",
   authmethods: ["cookie", "wampcra"],
   authid: username,
   onchallenge: onChallenge
});
```

In Crossbar.io, we need to cofigure two things: the setting of the cookie in principle (this can be used for purposes other than authentication), and the cookie authentication itself for the transport.

An example for setting up cookie tracking on our above dynamic authentication path would be 

```json
"dynamic": {
   "type": "websocket",
   "cookie": {
      "name": "cba_user",
      "length": 24,
      "max_age": 300,
      "store": {
         "type": "memory"
      }
   },
   "auth": {
      "wampcra": {
         "type": "dynamic",
         "authenticator": "io.crossbar.advanced.backend.authenticate"
      }                       
   }
}
```

and enabling cookie authentication for our transport from before just requires extending the authentication methods dictionary:

```json
"auth": {
   "wampcra": {
      "type": "dynamic",
      "authenticator": "io.crossbar.advanced.backend.authenticate"
   },
   "cookie": {
   }                          
}
```

The flow then is that the initial attempt at authenticating is using cookies. If no cookie is present, or if the cookie is older than the age limit, then we can do one of:

- nothing, e.g. if this is on a Web page and this is usable without any WAMP connection
- authenticate anonymously, if the Web page or app can be used with an anonymous WAMP connection
- show a login/registration prompt if the Web page or app requires an authenticated connection

## Logout

Logout first of all means that we close the current authenticated connection. We also need to do something to either delete or invalidate the cookie. Otherwise the user is automatically logged in again on the next page load (provided the cookie has not expired in the meantime). Crossbar.io invalidates the cookie if you give "wamp.close.logout" as the reason when closing the connection:

```javascript
connectionAuth.close("wamp.close.logout");
```

(You could of course also delete the cookie from your client-side JavaScript, but why do so when there's a dedicated method.)


## Registration

For registration, we require at a minimum two items of information: the username and the password. These are sent to the backend using an anonymous WAMP connection. Since this means that the shared secret between the client and the router (the password) travels over the wire, this connection should be encrypted. 

The registration is handled by a registration component which registers a procedure to call. This does not need to do any more than create the user in the user object (used above for login) or, more realistically, in the user database. Additionally you will most likely validate the registration data regarding your requirements for username and password.

If the data sent passes these checks, then a new user is created, and the registration procedure returns a success.

We then use the user data we still hold locally in the browser to establish a new, authenticated connection using WAMP-CRA. We also close the anonymous WAMP connection. 

If there is a problem with the registration data, we display this to the user.
