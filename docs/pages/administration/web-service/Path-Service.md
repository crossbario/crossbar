title: Path Service
toc: [Documentation, Administration, Web Services, Path Service]

# Path Service

Provides nesting of Web path services.

## Configuration

To configure a Path Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

attribute | description
---|---
**`type`** | must be `"path"`
**`paths`** | A dictionary for configuring services on subpaths with keys matching the regular expression `^([a-z0-9A-Z_\-]+|/)$`, and with `/` in the set of keys.

## Example

Here is an example where two subpaths are collected on a Path Service which serves as a kind of folder:

```javascript
{
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
                     "directory": "../web"
                  },
                  "myfolder": {
                     "type": "path"
                     "paths": {
                        "download1": {
                            "type": "static",
                            "directory": "/tmp"
                         },
                         "download2": {
                            "type": "static",
                            "directory": "/data/tmp"
                         }
                     }
                  }
               }
            }
         ]
      }
   ]
}
```

---
