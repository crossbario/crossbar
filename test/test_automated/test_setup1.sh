#!/bin/sh

crossbar shell show status
crossbar shell list mrealms
crossbar shell show mrealm default
crossbar shell --realm default list nodes
crossbar shell --realm default show node all

echo "creating webcluster .."

crossbar shell --realm default create webcluster cluster1 \
    --config='{"tcp_port": 8080, "tcp_shared": true}'

crossbar shell --realm default add webcluster-node cluster1 all \
    --config '{"parallel": 2}'

crossbar shell --realm default add webcluster-service cluster1 "/" \
    --config '{"type": "static", "directory": "..", "options": {"enable_directory_listing": true}}'
crossbar shell --realm default add webcluster-service cluster1 "info" \
    --config '{"type": "nodeinfo"}'
crossbar shell --realm default add webcluster-service cluster1 "settings" \
    --config '{"type": "json", "value": [1, 2, 3]}'
crossbar shell --realm default add webcluster-service cluster1 "ws" \
    --config '{"type": "websocket"}'

crossbar shell --realm default show webcluster cluster1
crossbar shell --realm default list webclusters
crossbar shell --realm default start webcluster cluster1
crossbar shell --realm default list webcluster-services cluster1
crossbar shell --realm default show webcluster-service cluster1 "settings"

echo "creating router cluster .."

crossbar shell --realm default create routercluster cluster2
crossbar shell --realm default add routercluster-node cluster2 all --config '{}'
crossbar shell --realm default add routercluster-workergroup cluster2 mygroup1 --config '{}'
crossbar shell --realm default add routercluster-workergroup cluster2 mygroup2 --config '{}'
crossbar shell --realm default add routercluster-workergroup cluster2 mygroup3 --config '{}'
crossbar shell --realm default start routercluster cluster2

echo "creating application realm .."

crossbar shell --realm default create arealm myrealm1 --config='{"enable_meta_api": true, "bridge_meta_api": true}'

crossbar shell --realm default create role myrole1 --config='{}'
crossbar shell --realm default add role-permission myrole1 "" \
    --config='{"match": "prefix", "allow_call": true, "allow_register": true, "allow_publish": true, "allow_subscribe": true, "disclose_caller": true, "disclose_publisher": true, "cache": true}'

crossbar shell --realm default create role myrole2 --config='{}'
crossbar shell --realm default add role-permission myrole2 "" \
    --config='{"match": "prefix", "allow_call": true, "allow_register": true, "allow_publish": true, "allow_subscribe": true, "disclose_caller": true, "disclose_publisher": true, "cache": true}'

crossbar shell --realm default add arealm-role myrealm1 myrole1 --config='{"authmethod": "anonymous"}'

crossbar shell --realm default start arealm myrealm1 cluster2 mygroup1 cluster1

crossbar shell --realm default create arealm myrealm2 --config='{"enable_meta_api": true, "bridge_meta_api": true}'
crossbar shell --realm default add arealm-role myrealm2 myrole2 --config='{"authmethod": "anonymous"}'
crossbar shell --realm default start arealm myrealm2 cluster2 mygroup2 cluster1

crossbar shell --realm default create arealm myrealm3 --config='{"enable_meta_api": true, "bridge_meta_api": true}'
crossbar shell --realm default add arealm-role myrealm3 myrole1 --config='{"authmethod": "anonymous"}'
crossbar shell --realm default start arealm myrealm3 cluster2 mygroup3 cluster1

crossbar shell --realm default create arealm myrealm4 --config='{"enable_meta_api": true, "bridge_meta_api": true}'
crossbar shell --realm default add arealm-role myrealm4 myrole1 --config='{"authmethod": "anonymous"}'
crossbar shell --realm default start arealm myrealm4 cluster2 mygroup3 cluster1

# FIXME
crossbar shell --realm default add principal myrealm4 user1 --config='{"authrole": "myrole2"}'
crossbar shell --realm default add principal-credential myrealm4 user1 --config='{"authmethod": "ticket", "secret": "secret123"}'

crossbar shell --realm default list principals myrealm4
crossbar shell --realm default list principals myrealm4 --names
crossbar shell --realm default show principal myrealm4 user1

crossbar shell --realm default list principal-credentials myrealm4 user1

crossbar shell --realm default show routercluster cluster2
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup1
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup2
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup3
crossbar shell --realm default show role myrole1
crossbar shell --realm default show arealm myrealm1
crossbar shell --realm default show arealm myrealm2
crossbar shell --realm default show arealm myrealm3
crossbar shell --realm default show arealm myrealm4

echo "done! sleep 90s .."
sleep 90

while ! curl -s http://localhost:8080/info > /dev/null
do
  echo "$(date) - public endpoint: still trying"
  sleep 1
done
echo "$(date) - public endpoint: connected successfully"

echo "completed!"
