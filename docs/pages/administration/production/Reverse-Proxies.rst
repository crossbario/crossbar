:orphan:


Reverse Proxies
===============

Running Crossbar.io behind `reverse
proxies <https://en.wikipedia.org/wiki/Reverse_proxy>`__.

HAProxy
-------

Write me.

Nginx
-----

Write me. You can find some Nginx examples and hints
`here <https://github.com/nicokaiser/nginx-websocket-proxy>`__.

Note also that nginx's default timeout is 60 seconds; use
``proxy_read_timeout`` option to increase this.

Apache
------

Apache supports proxying WebSocket connections using
`mod\_proxy\_wstunnel <http://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html>`__.
