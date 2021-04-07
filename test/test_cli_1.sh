#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbarfx/* if it doesn't yet exist
crossbarfx shell init --yes
crossbarfx master version

# start with scratched master database
mkdir -p ./test/cfc/.crossbar
mkdir -p ./test/cf1/.crossbar
mkdir -p ./test/cf2/.crossbar
mkdir -p ./test/cf3/.crossbar
crossbarfx edge stop --cbdir ./test/cf1/.crossbar
crossbarfx edge stop --cbdir ./test/cf2/.crossbar
crossbarfx edge stop --cbdir ./test/cf3/.crossbar
crossbarfx master stop --cbdir ./test/cfc/.crossbar
rm -rf ./test/cfc/.crossbar/.db-*

# start CFC node
crossbarfx master start --cbdir ./test/cfc/.crossbar &
sleep 5

# authenticate, create new management realm and pair the 3 CF nodes
crossbarfx shell init --yes
crossbarfx shell show status
crossbarfx shell show version
crossbarfx shell show license

crossbarfx shell create mrealm mrealm1
crossbarfx shell list mrealms
crossbarfx shell --realm mrealm1 list nodes
crossbarfx shell --realm mrealm1 show status

crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
crossbarfx shell --realm mrealm1 list nodes
crossbarfx shell --realm mrealm1 show node node1
crossbarfx shell --realm mrealm1 show node node2
crossbarfx shell --realm mrealm1 show node node3

# start the 3 CF nodes
crossbarfx edge start --cbdir ./test/cf1/.crossbar &
crossbarfx edge start --cbdir ./test/cf2/.crossbar &
crossbarfx edge start --cbdir ./test/cf3/.crossbar &
sleep 2
crossbarfx shell --realm mrealm1 list nodes
crossbarfx shell --realm mrealm1 list nodes --online
crossbarfx shell --realm mrealm1 list nodes --offline
crossbarfx shell --realm mrealm1 show node node1
crossbarfx shell --realm mrealm1 show node node2
crossbarfx shell --realm mrealm1 show node node3

# start a webcluster with webservices
crossbarfx shell --realm mrealm1 create webcluster cluster1 \
    --config '{"tcp_port": 8080, "tcp_shared": true, "tcp_backlog": 512}'

crossbarfx shell --realm mrealm1 show webcluster cluster1

crossbarfx shell --realm mrealm1 list webcluster-nodes cluster1
crossbarfx shell --realm mrealm1 list webcluster-services cluster1

# add nodes to the webcluster
crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node1 \
    --config '{"parallel": 3}'

crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node2 \
    --config '{"parallel": 3}'

crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node3 \
    --config '{"parallel": 2}'

crossbarfx shell --realm mrealm1 list webcluster-nodes cluster1

# add service to the webcluster
crossbarfx shell --realm mrealm1 add webcluster-service cluster1 '/' \
    --config '{"type": "static", "directory": "/tmp", "options": {"enable_directory_listing": true}}'

crossbarfx shell --realm mrealm1 add webcluster-service cluster1 'hello' \
    --config '{"type": "json", "value": "0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789"}'

crossbarfx shell --realm mrealm1 add webcluster-service cluster1 'info' \
    --config '{"type": "nodeinfo"}'

crossbarfx shell --realm mrealm1 list webcluster-services cluster1
crossbarfx shell --realm mrealm1 show webcluster-service cluster1 "/"
crossbarfx shell --realm mrealm1 show webcluster-service cluster1 "hello"
crossbarfx shell --realm mrealm1 show webcluster-service cluster1 "info"

# start the webcluster
crossbarfx shell --realm mrealm1 start webcluster cluster1
crossbarfx shell --realm mrealm1 show webcluster cluster1
for i in `seq 1 100`;
do
    sh -c 'curl -s http://localhost:8080/info | grep "with PID"'
done
sleep 1

# stop the webcluster
#crossbarfx shell --realm mrealm1 stop webcluster cluster1
#crossbarfx shell --realm mrealm1 show webcluster cluster1
#sleep 1

# remove all webcluster resources
#crossbarfx shell --realm mrealm1 remove webcluster-service cluster1 '/'
#crossbarfx shell --realm mrealm1 remove webcluster-service cluster1 'hello'
#crossbarfx shell --realm mrealm1 remove webcluster-service cluster1 'info'
#crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node1
#crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node2
#crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node3
#crossbarfx shell --realm mrealm1 delete webcluster cluster1
#sleep 2

# stop all nodes
crossbarfx shell --realm mrealm1 list nodes --online
crossbarfx shell --realm mrealm1 list nodes --offline

crossbarfx edge stop --cbdir ./test/cf1/.crossbar
crossbarfx edge stop --cbdir ./test/cf2/.crossbar
crossbarfx edge stop --cbdir ./test/cf3/.crossbar

crossbarfx shell --realm mrealm1 list nodes --online
crossbarfx shell --realm mrealm1 list nodes --offline

crossbarfx master stop --cbdir ./test/cfc/.crossbar
