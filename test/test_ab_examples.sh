#!/bin/sh

cd /tmp
rm -f master.zip
curl -o master.zip https://codeload.github.com/crossbario/autobahn-python/zip/master
rm -rf autobahn-python-master
unzip -q master.zip
cd autobahn-python-master/examples

# run RawSocket tests using Twisted and asyncio Autobahn client
AUTOBAHN_DEMO_ROUTER=rs://127.0.0.1:8080 python run-all-examples.py

# run WebSocket tests using Twisted and asyncio Autobahn client
AUTOBAHN_DEMO_ROUTER=ws://127.0.0.1:8080/ws python run-all-examples.py
