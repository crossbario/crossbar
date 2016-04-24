[Documentation](.) > [Administration](Administration) > [Going to Production](Going to Production) > SSL-TLS Interception Proxies

# SSL-TLS Interception Proxies

SSL-TLS Interception Proxies sit between browsers and Web/WebSocket servers, unwrapping a secure TLS connection to look inside the payload of the traffic. Here is an [introduction](http://www.secureworks.com/cyber-threat-intelligence/threats/transitive-trust/).

Interception proxies are usually operating transparently to the user, impersonating target sites and servers to do their content inspection thing. They are one class of devices that in the context of WebSocket are called *intermedaries*.

## Products

### Barracuda Web Filter

According to a Barracuda sales engineer (2014/07/08), the [Barracuda Web Filter](https://www.barracuda.com/products/webfilter) does **NOT** support WebSocket. Hence, WAMP-over-WebSocket will not work.

It is unclear whether the appliance allows to exclude (via configuration) certain target URLs from interception, and if doing so would make WebSocket work on such configured target addresses.

It is unclear whether WAMP-over-HTTP/longpoll would work for that appliance (precisely, whether the appliance would allow long standing HTTP/POST requests to persist and immediately forward data sent downstream).
