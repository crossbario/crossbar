[Documentation](.) > [Administration](Administration) > [Database Integration](Database Integration) > Database Connection Pools

# Database Connection Pools

## Introduction

Crossbar.io is able to integrate with external databases to support different features:

* WAMP direct-to-database integration
* event persistence
* ...

For efficient resource use, Crossbar.io uses database connection pools.

## Configuration

Database connection pools can be configured on native workers (routers and containers) and controller processes.

```json
{
    "workers": {
        "type": "router",
        "connections": [
            ... connections go here ...
        ]
    }
}
```

Here is an example database connection pool configuration for a PostgreSQL pool:

```json
{
   "id": "pgpool1",
   "type": "postgresql.connection",
   "host": "localhost",
   "port": 5432,
   "database": "cdc",
   "user": "crossbar",
   "password": "crossbar",
   "options": {
      "min_connections": 5,
      "max_connections": 20
   }
}
```

* `id`: Optional configuration item ID. If not provided, items are named `connectionN`, where `N` is numbered starting with 1.
* `type`: Type of connection pool. For a PostgreSQL database connection pool, this must be `"postgresql.conncetion" (**required**).
* `host`: Hostname of PostgreSQL database server (**default: localhost**)
* `port`: TCP Port to connect to (**default: 5432**).
* `database`: Name of database to connect to (**required**)
* `user`: Database user name (**required**)
* `password`: Password for database user (**required**)
* `options`: A dictionary with addition configuration, see below.

The database connection pool can be tuned further using `options`:

* `options.min_connections`: Keep at least this many database connections in the connection pool.
* `options.max_connections`: Limit number of database connections in the pool (active or not) to this many connections.
