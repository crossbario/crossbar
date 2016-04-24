[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > URI Format

# URI Format

WAMP uses URIs (*Uniform Resource Identifiers*) to identify topics, registered procedures, and errors. All of these form a single, global, hierarchical namespace.

To avoid resource naming conflicts, WAMP follows the package naming convention from Java, where URIs should begin with (reversed) domain names owned by the organization defining the URI. 

So for a company using the domain "expressweasel.com" an URL for a login procedure could be

```
com.expressweasel.user.login
```

## URI format rules

Crossbar.io implements the strict URI conventions from the WAMP specification. This is in order to assure that URIs are valid identifiers across as many languages as possible.

This means:

* Allowed characters are **lower case** letters, numbers, '.' and '_'. (Lower case letters are used to ensure compatibility with languages which have case-insensitive identifiers.)
* There can be no non-empty parts between the separating full-stops, e.g. `com.expressweasel.user..start` is not a valid URI. (It could be used as part of patter-based subscriptions/registrations though.)
* `wamp` as an inital URI part is not allowed, since this is reserved for URIs predefined with the WAMP protocol itself.
* `crossbar` as an initial URI part is not allowed, since this is used by Crossbar.io itself for internal messaging.