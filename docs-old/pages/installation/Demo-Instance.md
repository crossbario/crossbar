title: Demo Instance
toc: [Documentation, Installation, Demo Instance]

# Demo Instance

We run a demo instance which serves the [Crossbar.io demos](https://demo.crossbar.io/) and can be used for light development work and testing.

## Using the Demo Instance

The demo instance runs a WAMP-over-WebSocket listening transport at

```
wss://demo.crossbar.io/ws
```

This offers a single realm:

```
realm1
```

and accepts authentication as anonymous with permissions for all four WAMP roles set (for any URI).

There is no possibility to configure anything from your side.

This means that

* You have to carefully namespace your topics & call names to avoid conflicts with those of other users (e.g. have some part in the path unique to your project).
* You cannot try out any of the more advanced features such as authorization or component hosting.

The instance is solely intended for ephemeral use during initial testing and development. It's supposed to make your life easier when you start out with WAMP/Crossbar.io, but not to become a permanent fixture in your workflow.

> Note: Other realms may exist on the demo server, but these are not intended for public use, and we may make breaking changes there at any time without announcement.

## Rules of Use

The demo instance is a small virtual machine. This means that you shouldn't expect wonders regarding performance when you really hammer it (think thousands of connections *and* messages per second). For normal development and testing workloads, performance should be fine.

We don't want to give any specific usage rules. Just bear in mind that this is a free service for you, but that we have to pay for the traffic. So use common sense regarding the amount of usage. A rule of thumb: When you start thinking about whether this is still sensible usage it probably isn't! By this time you're obviously past initial exploration, and it's not hard to set up your own instance [locally or in the cloud](Installation).
