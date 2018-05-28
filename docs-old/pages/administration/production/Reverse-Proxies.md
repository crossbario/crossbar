title: Reverse Proxies
toc: [Documentation, Administration, Going to Production, Reverse Proxies]

# Reverse Proxies

Running Crossbar.io behind [reverse proxies](http://en.wikipedia.org/wiki/Reverse_proxy).

## HAProxy

Write me.

## Nginx

Write me. You can find some Nginx examples and hints [here](https://github.com/nicokaiser/nginx-websocket-proxy).

Note also that nginx's default timeout is 60 seconds; use `proxy_read_timeout` option to increase this.

## Apache

Apache supports proxying WebSocket connections using [mod_proxy_wstunnel](http://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html).
