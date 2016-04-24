[Documentation](.) > [Administration](Administration) > Database Integration

# Database Integration

Crossbar.io includes direct database integration services for the following databases:

* [Database Connection Pools](Database Connection Pools)
* [PostgreSQL Integration](PostgreSQL-Integration)
* [Oracle Integration](Oracle Integration)

The database integration makes procedural code running inside a database (like PostgreSQL PL/pgSQL or Oracle PL/SQL database stored procedures and triggers) a **first class WAMP citizen**.

You can

* **publish** WAMP events directly from within the database (e.g. a database trigger or stored procedure)
* **subcribe** database stored procedures to receive WAMP events on a topic
* **register** database stored procedures to be called transparently like any other WAMP procedure
* **call** any WAMP procedure from within the database (e.g. a database trigger or stored procedure)

**Why?**

This is an incredibly powerful feature, as it allows you to (selectively) move business logic into the database, close to your data, greatly reducing latencies, round-trips and increasing security, as you have full and application-independent control and a clean API to your database, that encaspulates and abstracts away SQL, shielding you from schema changes.

And the best: doing so is fully transparent to all consumers. A WAMP caller that calls into the database is completely *unaware* that the callee actually is a stored procedure running inside a database.
