[Documentation](.) > [Administration](Administration) > [Database Integration](Database Integration) > Oracle Integration

# Oracle Integration

## Quick Setup

From a terminal, run the following to setup the Crossbar.io Oracle database integration:

```
cd database
sqlplus sys/oracle@localhost:1521/orcl as sysdba @create_users.sql
sqlplus cbdb/crossbar@localhost:1521/orcl @install.sql
```

> Note: Above assumes Oracle database is listening on `localhost` port `1521` using the service name `ORCL`, and that `SYS` still has the default password `oracle`.

Then start Crossbar.io

```
crossbar start
```

## Installation

By default, the installation scripts generated will create two database users:

* `CBADAPTER`
* `CBDB`

The `CBADAPTER` user is used by Crossbar.io to connect to Oracle. Other than `CREATE SESSION`, this user only has `EXECUTE` permission on the public API (the stored procedures) exposed by the Crossbar.io database integration.

The `CBDB` user is the owning schema of the database objects making up the Crossbar.io database integration.

To create those user, you must be connected as `SYS` and run the following script (from within the `database` directory generated):

```console
$ sqlplus sys/oracle@localhost:1521/orcl as sysdba @create_users.sql

SQL*Plus: Release 12.1.0.2.0 Production on Mon Oct 27 12:49:40 2014

Copyright (c) 1982, 2014, Oracle.  All rights reserved.


Connected to:
Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, OLAP, Advanced Analytics and Real Application Testing options

...

No errors.
Disconnected from Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, OLAP, Advanced Analytics and Real Application Testing options
```

The next step creates all the database objects that together make up the Crossbar.io database integration.

To create those objects, you must be connected as `CBDB` and run the following script (from within the `database` directory generated):

```console
$ sqlplus cbdb/crossbar@localhost:1521/orcl @install.sql

SQL*Plus: Release 12.1.0.2.0 Production on Mon Oct 27 12:50:22 2014

Copyright (c) 1982, 2014, Oracle.  All rights reserved.


Connected to:
Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, OLAP, Advanced Analytics and Real Application Testing options

****** Installing Crossbar.io Oracle Integration  *******

...

****** Installation complete  *******
No errors.
Disconnected from Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, OLAP, Advanced Analytics and Real Application Testing options
```




