title: Subscriber Black and Whitelisting
toc: [Documentation, Programming Guide, Subscriber Black and Whitelisting]

# Subscriber Black- and Whitelisting

> **Subscriber Black-/Whitelisting** is a feature from the WAMP Advanced Profile. The specification can be found [here](https://github.com/tavendo/WAMP/blob/master/spec/advanced/subscriber-blackwhite-listing.md).

There is a [complete white- and black- listing example](https://github.com/crossbario/crossbar-examples/tree/master/exclude_subscribers) with Python and JavaScript clients available.

As per default, whenever there is a publication to a topic, a PubSub event is dispatched to all (authorized) subscribers to that topic other than the publisher itself. **Subscriber Black- and White- listing** restricts the set of subscribers who receive events for a particular publication.

There are three ways to do blacklisting: `exclude` (using a list of session IDs to exclude), `exclude_authid` (using a list of authentication IDs to exclude) and `exclude_authrole` (using a list of authentication roles to exclude); and three corresponding ways to do whitelisting: `eligible`, `eligible_authid`, and `eligible_authrole`.

## Use Cases

For a frontend with state synchronized across devices, a device on which an update is made may communicate this via an RPC to the backend. The local change may be effected as soon as the user input is made, with a possible rollback should the RPC fail. The other devices receive the update based on a successfully processed user input from the backend. In this case the backend will want to exclude the source device for the user input from the update.

## Subscriber Blacklisting

If you have a list of sessions to exclude from a publication, you should pass a list of session-id's to `exclude`; if any of those sessions are subscribers, they will not receive this publish.

You can also exclude sessions with `exclude_authid` or `exclude_authrole`. These options take a string or list of strings representing sessions to remove from the receivers. Thus any subscribers with the corresponding `authid` (or `authrole`) will not receive this publish.

---

## Subscriber Whitelisting

Whitelisting is the inverse of blacklisting: you specify the set of subscribers who may receive the publish instead of saying who may not.

If you have a list of sessions who could receive a publication, you should pass a list of session-id's to the `eligible` option; only these sessions will possibly be able to receive the publish. This is a *filtering* operation, so they won't all **necessarily** receive the publish -- they still need to subscribe, for example.

You can also filter by `eligible_authid` or `eligible_authrole`. These options both take either a single string or a list of strings representing an assigned `authid` or `authrole` and work similarly. Of all the subscribers, only those without the correct `authid` (or `authrole`) will get the publish.


---

## Getting Session IDs

Subscriber Session IDs, which are used in **Subscriber Black- and Whitelisting**, can be communicated to application components via application-level messages. Components should be able to retrieve their WAMP Session ID - e.g. in Autobahn|JS, it's stored in `session.id`.

Additionally, Crossbar.io has [Subscription Meta-Events and Procedures](Subscription Meta Events and Procedures) which allow the retrieval of this information from the router.

Further, Crossbar.io has [Publisher Identification](Publisher Identification) and [Caller Identification](Caller Identification).

---
