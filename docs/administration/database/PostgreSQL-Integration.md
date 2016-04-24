[Documentation](.) > [Administration](Administration) > [Database Integration](Database Integration) > PostgreSQL Integration

# PostgreSQL Integration

## Introduction

The PostgreSQL integration provided by Crossbar.io extends WAMP directly into the database. Using the integration services, you can

* **[publish](PostgreSQL-Integration-Publisher)** WAMP events directly from within the database (e.g. a database trigger or stored procedure)
* **[subcribe](PostgreSQL-Integration-Subscriber)** database stored procedures to receive WAMP events on a topic
* **[register](PostgreSQL-Integration-Callee)** database stored procedures to be called transparently like any other WAMP procedure
* **[call](PostgreSQL-Integration-Caller)** any WAMP procedure from within the database (e.g. a database trigger or stored procedure)

You can find complete, working examples in the [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples/):

* [PostgreSQL Publisher Example](https://github.com/crossbario/crossbarexamples/tree/master/database/postgresql/publisher)
* [PostgreSQL Subscriber Example](https://github.com/crossbario/crossbarexamples/tree/master/database/postgresql/subscriber)
* [PostgreSQL Caller Example](https://github.com/crossbario/crossbarexamples/tree/master/database/postgresql/caller)
* [PostgreSQL Callee Example](https://github.com/crossbario/crossbarexamples/tree/master/database/postgresql/callee)

**Why?**

This is an incredibly powerful feature, as it allows you to (selectively) move business logic into the database, close to your data, greatly reducing latencies, round-trips and increasing security, as you have full and application-independent control and a clean API to your database, that encaspulates and abstracts away SQL, shielding you from schema changes.

And the best: doing so is fully transparent to all consumers. A WAMP caller that calls into the database is completely *unaware* that the callee actually is a stored procedure running inside a database.


## Installation

### Prerequisites

You will need to have Crossbar.io installed with PostgreSQL support:

```console
pip install crossbar[postgres]
```

or

```console
pip install crossbar[all]
```

> Note: On Debian/Ubuntu, you might need the PostgreSQL client library with development headers: `sudo apt-get install -y libpq-dev`


### Database Setup

To use the PostgreSQL integration services of Crossbar.io, the following needs to be run **once** as a database superuser (e.g. `postgres`) connected to the database where you want to have the intgration:

```sql
CREATE ROLE crossbar LOGIN INHERIT;

ALTER ROLE crossbar ENCRYPTED PASSWORD 'crossbar';

CREATE SCHEMA crossbar AUTHORIZATION crossbar;

GRANT USAGE ON SCHEMA crossbar TO public;
```

**For production, you will want to change the password 'crossbar' above to something safe!** The examples assume the password 'crossbar' though.

> Above commands will setup a database schema `crossbar` where Crossbar.io will create database objects (tables, stored procedures, ..) needed for the integration, and it will create a database user `crossbar` under which Crossbar.io will connect to your PostgreSQL database.

To remove everything again:

```sql
DROP OWNED BY crossbar CASCADE;

DROP SCHEMA IF EXISTS crossbar CASCADE;

DROP ROLE IF EXISTS crossbar;
```

## Notes on PostgreSQL

For convenience, here are some notes regarding PostgreSQL on Debian/Ubuntu.

Further information can be found in the [Ubuntu/PostgreSQL documentation](https://help.ubuntu.com/community/PostgreSQL) and the [Linux/PostgreSQL documentation](http://www.postgresql.org/download/linux/ubuntu/).

### Installation

To install PostgreSQL on Debian/Ubuntu

```console
sudo apt-get install -y postgresql-9.4
```

If your Debian/Ubuntu is too old and lacks PostgreSQL 9.4, here is how you can add the PostgreSQL project's binary package repository which always contains the latest version.

Add the PostgreSQL package repository

```console
sudo vi /etc/apt/sources.list.d/pgdg.list
```

and add the following line in this file

```
deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main
```

Then, add the PostgreSQL package repository key

```console
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
```

update the package list

```console
sudo apt-get update
```

and finally install PostgreSQL

```console
sudo apt-get install -y postgresql-9.4
```

This will create a new PostgreSQL database cluster with these directories

* `/etc/postgresql/9.4/main` for configuration
* `/var/lib/postgresql/9.4/main` for data

For example, the configuration file for authorization is here `/etc/postgresql/9.4/main/pg_hba.conf`.

### Administration

**Connect**

This will connect as PostgreSQL superuser (`postgres` by default) to the service database `postgres`

```console
sudo -u postgres psql postgres
```

**Control**

Control the PostgreSQL server by doing

```console
sudo -u postgres pg_ctlcluster 9.4 main <action>
```

where `<action>` is one of `start`, `stop`, `restart`, `reload`, `status` or `promote`.

**Change Password**

To change (or set) the password of the PostgreSQL default superuser (`postgres`)

```console
sudo -u postgres psql postgres
```

and run

```sql
ALTER ROLE postgres ENCRYPTED PASSWORD '123456';
```
