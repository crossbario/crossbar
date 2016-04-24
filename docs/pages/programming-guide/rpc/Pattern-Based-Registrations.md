[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > RPC > Patter-Based Registrations

# Pattern-Based Registrations

As a default, URIs in registration requests and calls are processed with exact matching, i.e. an call will be accepted and a procedure invoked on a callee if the  URI of the call exactly matches the URI for which the callee registered the procedure.

## Use cases for Pattern-Based Registrations

There are use cases where more flexibility is required. As an example, in a warehouse management system, you may have calls such as "com.myapp.manage.move.473883sjs", where the final URI part is an ID for an individual item in the warehouse. Alterantively, it may be convenient to include the ID for goods as an earlier URI part, e.g. "com.myapp.manage.34dhfh56.move" and "com.myapp.manage.dj4783839.retrieve". In both cases, a component which offers handling of "move" would want to register for all "move" calls irrespective of the particular goods ID.

WAMP offers two matching mechanisms to cover use cases such as these:

* prefix matching
* wildcard matching

## Prefix Matching

With prefix matching, a callee can register to be invoked for calls to URIs which contain the registration URI as a prefix.

For example, the registration URI

`com.myapp.manage`

in a registration with prefix matching would all the callee to be called for calls to URIs

`com.myapp.manage.add`
`com.myapp.manage.store`
`com.myapp.manage.retrieve`
`com.myapp.manage.ship`

but not

`com.myapp2.manage.create`

Using this, in the warehouse management application mentioned initially, with the goods ID as the final URI part, a component would register for "com.myapp.manage.move" and set prefix matching for this.

To set prefix matching, the matching policy "prefix" needs to be set within the registation options.

As an example, in an application written in JavaScript and using Autobahn|JS as the WAMP client library, the registration would be

```javascript
session.register("com.myapp.manage.move", move, { match: "prefix" });
```

## Wildcard Matching

With wildcard matching, a callee can register to be invoked for calls to URIs where all given URI components match the registration URI.

For example, the registration URI

`com.myapp.manage..create`

contains four defined URI components ("com", "myapp", "manage", "create") and one wildcard. The wildcard is defined by the double dots betwen "manage" and "create". 

This would be matched by

`com.myapp.manage.47837483.create`
`com.myapp.manage.an_item.create`
`com.myapp.manage.test.create`

but not by

`com.myapp.manage.test.3728378.create`
`com.myapp.manage.37283.create.new`

Using this, in the warehouse management application mentioned initially, with the goods ID used as a component within the URI, a component would register for "com.myapp.manage..move" and set wildcard matching for this.

To set wildcard matching, the matching policy "wildcard" needs to be set within the registation options.

As an example, in an application written in JavaScript and using Autobahn|JS as the WAMP client library, the registration would be

```javascript
session.register("com.myapp.manage..move", move, { match: "wildcard" });
```

> Using wildcard matching, only entire component parts of URIs can be set as wildcards. There is no mechanism to match partially identical components, e.g. "com.myapp.user3278378" and "com.myapp.user7727278".

## Exact matching

It is possibly to explicitly set the matching policy for exact matching, e.g.

```javascript
session.register("com.myapp.manage.move", move, { match: "exact" });
```

Since this is the default, it is unnecessary though, unless there is a need to make the matching policy explicit as a marker in the code.


> Note: the above examples are for Autobahn|JS since we also maintain and use this WAMP client library, and JavaScript is the closest there is to a lingua franca in programming. Users of other WAMP client libraries should feel free to add code examples for these!

## No Set-Based Registration Logic

Registrations are entities which are based on a combination of registration URI and matching policy. It is thus not possible to perform any set-based logic with registrations.

As an example: 

There is an existing registration for the URI `com.myapp` using prefix matching. It is then not possible to send an 'unregister' for the URI `com.myapp.procedure2` in order to prevent the callee being invoked for calls to this URI.


## Conflict resolution

With pattern-based subscriptions comes the possibility of having multiple registrations match the URI of a call. For example, given the registrations

1. `com.myapp.manage.47837483.create` - match: "exact"
2. `com.myapp` - match: "prefix"
3. `com.myapp.manage` - match: "prefix"
4. `com.myapp.manage...` - match: "wildcard"
5. `com.myapp...create` - match: "wildcard"

a call to 

`com.myapp.manage.47837483.create` 

would in principle match all five registrations. 

Since we want only a single callee to be invoked, there is a need to determine which registration takes precedence.

This is determined by first a hierarchy of matching policies, and then a determination within the prefix or wildcard matches.

## Hierarchy of Matching Policies

The hierarchy is simply:

- Exact match
- Prefix match
- Wildcard match

This means that a registration using prefix matching can only apply when there is no registration with an exact match for the call URI, and that a registration using wildcard matching can only apply when there is neither an exact match nor a prefix match for the call URI. 

In the initial example, registration 1. would apply.
Registrations 2. and 3. could only apply absent registration 1..
Registrations 3. and 4. could only apply abesent registrations 1. - 3..

Crossbar.io internally checks following this hierarchy. The rules below for prefix matching respectively wildcard matching are only checked if no match is found at the higher level(s) of the hierarchy.

## Longest Prefix Match Wins

If there are multiple registrations using prefix matchin which would in principle match (but no exact matching registration), then the longest of these prefixes wins. 

In the initial example, among registrations 2. and 3., registration 3. would apply since it is longer.

## Wildcard Matches

A conflict resolution for wildcard matches has yet to be specified and implemented.




> Note: the above examples are for Autobahn|JS since we also maintain and use this WAMP client library, and JavaScript is the closest there is to a lingua franca in programming. Users of other WAMP client libraries should feel free to add code examples for these!


## Working Example

For a full working example in JavaScript, see [Crossbar Examples](https://github.com/crossbario/crossbarexamples/tree/master/patternregs).