[Documentation](.) > [Administration](Administration) > [Database Integration](Database Integration) > [PostgreSQL Integration](PostgreSQL Integration) > PostgreSQL Publisher

# PostgreSQL Publisher

### Node Configuration

#### Running inside a Container Worker

For running the **Publisher** integration, here is how you would configure your node (only relevant parts are shown - [here](https://github.com/crossbario/crossbarexamples/blob/master/database/postgresql/publisher/.crossbar/config_using_container.json) is complete config) to have the adapter run in a separate worker process:

```json
{
   "workers": [
      {
         "type": "router",
         ...
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  ...
                  "ws": {
                     "type": "websocket"
                  }
               }
            }
         ]
      },
      {
         "type": "container",
         "options": {
            "reactor": {
               "win32": "select"
            }
         },
         "components": [
            {
               "type": "class",
               "classname": "crossbar.adapter.postgres.PostgreSQLPublisher",
               "realm": "realm1",
               "transport": {
                  "type": "websocket",
                  "endpoint": {
                     "type": "tcp",
                     "host": "127.0.0.1",
                     "port": 8080
                  },
                  "url": "ws://127.0.0.1:8080/ws"
               },
               "extra": {
                  "database": {
                     "host": "127.0.0.1",
                     "port": 5432,
                     "database": "cdc",
                     "user": "crossbar",
                     "password": "crossbar"
                  }
               }
            }
         ]
      }
   ]
}
```

Essentially, the PostgreSQL integration for Publisher is provided as a WAMP component `crossbar.adapter.postgres.PostgreSQLPublisher` which can be run and connected to a router worker as any other WAMP component.

The integration component however requires an `extra` configuration with the following attributes:

option | description
---|---
**`database`** | A dictionary with database connection configuration (*required*)
**`database.host`** | The hostname or IP address of the target PostgreSQL database cluster to connect to (*required*).
**`database.port`** | The TCP listening port on the PostgreSQL database cluster to connect to (*required*).
**`database.database`** | The database on the PostgreSQL cluster to connect to (*required*).
**`database.user`** | The name of the user to connect to the PostgreSQL cluster (*required*).
**`database.password`** | The password of the user to connect to the PostgreSQL cluster (*required*).


#### Running inside a Router Worker

Since the PostgreSQL integration is provided as a regular WAMP component (`crossbar.adapter.postgres.PostgreSQLPublisher`), you can also run the integration within a *router worker* (side-by-side). Here are relevant parts of a config (complete config [here](https://github.com/crossbario/crossbarexamples/blob/master/database/postgresql/publisher/.crossbar/config.json)):

```json
{
   "workers": [
      {
         "type": "router",
         ...
         "components": [
            {
               "type": "class",
               "classname": "crossbar.adapter.postgres.PostgreSQLPublisher",
               "realm": "realm1",
               "role": "anonymous",
               "extra": {
                  "database": {
                     "host": "127.0.0.1",
                     "port": 5432,
                     "database": "cdc",
                     "user": "crossbar",
                     "password": "crossbar"
                  }
               }
            }
         ]
      }
   ]
}
```

#### Database Connection Parameters from Environment Variables

Instead of providing database connection configuration using literal values in the node configuration, you can also use **environment variables**:

```json
"extra": {
  "database": {
     "host": "127.0.0.1",
     "port": 5432,
     "database": "cdc",
     "user": "crossbar",
     "password": "$PGPASSWORD"
  }
}
```

Crossbar.io will now try to read the `extra.database.password` attribute from the environment variable `PGPASSWORD`:

```console
export PGPASSWORD="crossbar"
```

You can use any names for your environment variables, as long as the name match the regular expression `^\$([A-Z0-9_]+)$`.

However, PostgreSQL has a number of [standard environment variables](http://www.postgresql.org/docs/current/static/libpq-envars.html), and it might be wise to reuse those, as these are usually used by other tools as well (such as `psql`):

* `PGHOST`
* `PGPORT`
* `PGDATABASE`
* `PGUSER`
* `PGPASSWORD`


### Using the PostgreSQL Integration

Publishing events from within PostgreSQL is done by calling the stored procedure `crossbar.publish()` provided by the integration:

```sql
FUNCTION crossbar.publish (
    topic       TEXT,
    args        JSONB       DEFAULT NULL,
    kwargs      JSONB       DEFAULT NULL,
    options     JSONB       DEFAULT NULL,
    autonomous  BOOLEAN     DEFAULT FALSE
) RETURNS BIGINT
```

with these parameters

* `topic` The WAMP URI the event should be published to (*required*)
* `args` Any positional payload for the event.
* `kwargs` Any keyword-based payload for the event.
* `options` WAMP publish options (see below).
* `autonomous`: If `TRUE`, do the publish in an autonomous transaction, otherwise do the publish within the current transaction context (*[NOT YET IMPLEMENTED](https://github.com/crossbario/crossbar/issues/223)*)

Here are a couple of examples:

```sql
SELECT crossbar.publish('com.example.topic1');
```

This will publish an event to topic `com.example.topic1` with no payload.

Of course you can supply payload as well:

```sql
SELECT crossbar.publish('com.example.topic1', json_build_array('hello world!', 23)::jsonb);
```

Here, the event is published with (positional) payload consisting of two arguments `'hello world!'` and `23`.

You can supply both positional and keyword-based payload for events

```sql
SELECT crossbar.publish('com.example.topic1',
   json_build_array(23, 7, 'hello world!')::jsonb,
   json_build_object('foo', 'bar', 'baz', 42)::jsonb
);
```

#### Publish Options

The PostgreSQL Publisher integration supports WAMP options for publishing events:

```sql
SELECT crossbar.publish('com.example.topic1',
    options := json_build_object(
        'exclude', json_build_array(1968608799)::jsonb
    )::jsonb
);
```

The following options are supported:

* `exclude` - a list of WAMP session IDs (integers)
* `eligible` - a list of WAMP session IDs (integers)
* `acknowledge` - *[NOT YET IMPLEMENTED](https://github.com/crossbario/crossbar/issues/357)*
