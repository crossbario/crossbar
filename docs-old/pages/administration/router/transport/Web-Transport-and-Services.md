title: Web Transport and Services
toc: [Documentation, Administration, Router Transports, Web Transport and Services]

# Web Transport and Services

Quick Links: **[Web Services](Web Services)** - **[HTTP Bridge](HTTP Bridge)** - **[Transport Endpoints](Transport Endpoints)**

Crossbar.io includes a full-featured WAMP router to wire up your application components. But if you serve HTML5 Web clients from Crossbar.io, the **static Web assets** for your frontends like HTML, JavaScript and image files need to be hosted somewhere as well.

You can host static content on your existing Web server or a static hosting service like Amazon S3. It does not matter if your Crossbar.io nodes reside on different domain names from the static content. However, you can  let Crossbar.io also host the static assets. This is possible by using a **Web Transport** with your router.

Besides hosting static content, the **Web Transport** also adds a whole number of other features like serving WSGI, redirection, file upload or CGI.

## Configuration

A Web transport is configured as a dictionary element in the list of `transports` of a router (see: [Router Configuration](Router-Configuration)). The Web transport dictionary has the following configuration parameters:

attribute | description
---|---
**`id`** | The (optional) transport ID - this must be unique within the router this transport runs in (default: **"transportN"** - where N is numbered starting with 1)
**`type`**  | Must be `"web"` (*required*)
**`endpoint`** | The endpoint to listen on (*required*). See [Transport Endpoints](Transport Endpoints)
**`paths`** | A dictionary for configuring services on subpaths (*required* - see below and [Web Services](Web Services) or [HTTP Bridge](HTTP Bridge)).
**`options`** | Is an optional dictionary for additional transport wide configuration (see below).

For Web transport `paths` the following two requirements must be fullfilled:

* a `path` must match the regular expression `^([a-z0-9A-Z_\-]+|/)$`
* there must be a root path `/` set

The value mapped to in the `paths` dictionary is a Web Service. The complete list of available Web services can be found here:

* [Web Services](Web Services)
* [HTTP Bridge](HTTP Bridge)

The Web transport `options` can have the following attributes:

attribute | description
---|---
**`access_log`** | set to `true` to enable Web access logging (default: **false**)
**`display_tracebacks`** | set to `true` to enable rendering of Python tracebacks (default: **false**)
**`hsts`** | set to `true` to enable [HTTP Strict Transport Security (HSTS)](http://en.wikipedia.org/wiki/HTTP_Strict_Transport_Security) (only applicable when using a TLS endpoint) (default: **false**)
**`hsts_max_age`** | for HSTS, use this maximum age (only applicable when using a TLS endpoint). (default: **31536000**)

---

## Example

Here is the basic outline of a Web Transport configuration

```javascript
{
   "controller": {
   },
   "workers": [
      {
         "type": "router",
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  "/": {
                     "type": "static",
                     "directory": ".."
                  },
                  "ws": {
                     "type": "websocket"
                  }
               }
            }
         ]
      }
   ]
}
```

Here is an example that combines three services:

```javascript
"paths": {
   "/": {
      "type": "static",
      "directory": ".."
   },
   "ws": {
      "type": "websocket",
   },
   "downloads": {
      "type": "static",
      "directory": "/home/someone/downloads"
   },
   "config": {
      "type": "json",
      "value": {
         "param1": "foobar",
         "param2": [1, 2, 3]
      }
   }
}
```

---
