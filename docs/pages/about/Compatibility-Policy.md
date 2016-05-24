title: Compatibility Policy
toc: [Documentation, Compatibility Policy]

# Compatibility Policy

This document describes our compatibility policies for Crossbar.io:

1. [Backward Compatibility of Releases](#backward-compatibility-of-releases)
2. [Compatibility with WAMP Client Libraries](#compatibility-with-wamp-client-libraries)


## Backward Compatibility of Releases

It is important to first define the scope of "backward compatibility". Crossbar.io has a backward compatibility policy defined with respect to the following aspects and areas:

1. WAMP protocol (the wire level)
2. WAMP meta API
3. Crossbar.io specific WAMP meta API
4. Crossbar.io node configuration file format
5. Crossbar.io command line

Crossbar.io (after the first official, stable release 2016.3) follows a strict backwards compatibility policy. **We promise to do our best to not break any of above.**

We consider the above list to be an exhaustive description of the **public API** of Crossbar.io. Anything else isn't public, and you should avoid relying on private things.

> **IMPORTANT**: Everything not listed in above is subject to change at any time. In particular, functions and classes from the Crossbar.io code base. You absolutely MUST NOT import any of these directly in code and applications of yours. The Crossbar.io code base itself should be considered fully internal, private and an implementation artifact. Of course, since Crossbar.io is fully open-source, we cannot technically stop you from not following this advice. However, you should note that due to the AGPL license of Crossbar.io, you would need to follow the requirements of the AGPL if you were to import and use the Crossbar.io source code directly. Also not covered by our compatibility policy is the *internal management API* of Crossbar.io. This API isn't for public consumption, but for management via the upcoming Crossbar.io DevOps Center. The management API is also covered by an API license that comes with some strings attached that effectively disallows any third-party use. Please see the `LICENSE-FOR-API` document in the Crossbar.io repository for complete details.

**Details**

If you have a WAMP client component that is connecting to Crossbar.io via the WAMP protocol, we ensure that this component will continue to work as new Crossbar.io releases are published.

We think this is an extremely important aspect. Consider an embedded device with a WAMP component burned into the firmware. Even if you have a way of updating and upgrading the device firmware in the field (which you totally should have!), we believe doing is often complex and requires coordination specific to the device and the application or solution it is part of. That needs to be under your control, and Crossbar.io should not impose additional requirements and restrictions.

What if new features are introduced in the WAMP protocol? Firstly, the WAMP protocol now (2016) has been stable for quite some time. Secondly, if there are new developments at the WAMP protocol level, we ensure that these changes to the WAMP protocol are made in an backwards compatible way (that is, Crossbar.io will be able to talk to "old" and "new" clients at the same time).

We make the same promises for the WAMP meta API as implemented in Crossbar.io, and the Crossbar.io specific WAMP meta API.

**In other words, our policy is: existing WAMP clients MUST NOT break.**

> IMPORTANT: We do make these promises only for WAMP clients talking over the WAMP protocol, and connecting via an actual WAMP transport (like TCP). Whether the client is started externally or started by Crossbar.io as **guest workers** doesn't matter. We do NOT make these promises for WAMP Python based components running side-by-side in **router workers**, or started in separate **container workers**. In fact, the possibility to start Python components in such a way (in router/container workers, rather than in guest workers) might be deprecated or made private in the future.

Regarding the Crossbar.io node configuration file format, our backwards compatibility policy works slightly differently. An "old" node configuration file can be upgraded to a "new" format from the Crossbar.io command line (`crossbar upgrade`). The node configuration file has an embedded version number, and Crossbar.io uses this to ugprade the configuration file stepwise (one version increment at a time) until the final, current format has been reached.

Regarding the Crossbar.io command line arguments and parameters. These are simply "extend only". That is, a command line option available today will continue to be supported "as is". New commands, arguments or parameter values might be added from time to time (though we don't expect much here), but nothing will be removed.


## Compatibility with WAMP Client Libraries

WAMP is an open standard, and a major focus is on interoperability between implementations from different parties. We also believe that we have a track record of being open and supportive towards third parties. We deeply believe in open standards, open source and not discriminating between implementations. We don't like vendor lock-in.

On the other hand, as there are now literally dozens of WAMP client library implementations out there, most not under our control, we cannot guarantee interoperability or long-term support of these particular clients.

**We are committed to maintaining and supporting the Autobahn family of WAMP client libraries,** and we work on a best-effort basis to work nice with other WAMP client library implementors.
