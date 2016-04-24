[Documentation](.) > [Administration](Administration) > [Web Services](Web Services) > Web Redirection Service

# Web Redirection Service

## Configuration

To configure a Web Redirection Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

option | description
---|---
**`type`** | must be `"redirect"`
**`url`** | the HTTP(S) URL where to redirect to, e.g. `"http://somehost:8080/something"`.

## Example

Here is how you define a **Web Transport** that redirects HTTP (and WebSocket) on port 80 to secure HTTPS (and secure WebSocket) on port 443:

```javascript
{
   "type": "web",
   "endpoint": {
      "type": "tcp",
      "port": 80
   },
   "paths": {
      "/": {
         "type": "redirect",
         "url": "https://example.com"
      }
   }
}
```
> The former example assumes the host's name is **example.com**


The single parameter to the *Redirection* service is `url`, which can take different forms:

 * `../foobar` (relative)
 * `/download` (absolute)
 * `https://example.com` (fully qualified)

You can also redirect *subpaths* on a **Web Transport**:

```javascript
{
   "type": "web",
   "endpoint": {
      "type": "tcp",
      "port": 80
   },
   "paths": {
      "/": {
         "type": "static",
         "directory": ".."
      },
      "ws": {
         "type": "websocket",
         "url": "ws://localhost:8080/ws"
      },
      "tavendo": {
         "type": "redirect",
         "url": "http://somewhere.com/to/something"
      }
   }
}
```

---
