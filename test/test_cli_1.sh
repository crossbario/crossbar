#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub

# SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(pwd)/test

echo "Using SCRIPT_DIR=${SCRIPT_DIR}"
echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbar/* if it doesn't yet exist
crossbar shell init --yes
crossbar master version

# start with scratched master database
mkdir -p ${SCRIPT_DIR}/cfc/.crossbar
mkdir -p ${SCRIPT_DIR}/cf1/.crossbar
mkdir -p ${SCRIPT_DIR}/cf2/.crossbar
mkdir -p ${SCRIPT_DIR}/cf3/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf1/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf2/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf3/.crossbar
crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar
rm -rf ${SCRIPT_DIR}/cfc/.crossbar/.db-*

# start CFC node
crossbar master start --cbdir ${SCRIPT_DIR}/cfc/.crossbar &
sleep 5

# authenticate, create new management realm and pair the 3 CF nodes
crossbar shell init --yes
crossbar shell show status
crossbar shell show version
crossbar shell show license

crossbar shell create mrealm mrealm1
crossbar shell list mrealms
crossbar shell --realm mrealm1 list nodes
crossbar shell --realm mrealm1 show status

crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub mrealm1 node3
crossbar shell --realm mrealm1 list nodes
crossbar shell --realm mrealm1 show node node1
crossbar shell --realm mrealm1 show node node2
crossbar shell --realm mrealm1 show node node3

# start the 3 CF nodes
crossbar edge start --cbdir ${SCRIPT_DIR}/cf1/.crossbar &
crossbar edge start --cbdir ${SCRIPT_DIR}/cf2/.crossbar &
crossbar edge start --cbdir ${SCRIPT_DIR}/cf3/.crossbar &
sleep 2
crossbar shell --realm mrealm1 list nodes
crossbar shell --realm mrealm1 list nodes --online
crossbar shell --realm mrealm1 list nodes --offline
crossbar shell --realm mrealm1 show node node1
crossbar shell --realm mrealm1 show node node2
crossbar shell --realm mrealm1 show node node3

# start a webcluster with webservices
crossbar shell --realm mrealm1 create webcluster cluster1 \
    --config '{"tcp_port": 8080, "tcp_shared": true, "tcp_backlog": 512}'

crossbar shell --realm mrealm1 show webcluster cluster1

crossbar shell --realm mrealm1 list webcluster-nodes cluster1
crossbar shell --realm mrealm1 list webcluster-services cluster1

# add nodes to the webcluster
crossbar shell --realm mrealm1 add webcluster-node cluster1 node1 \
    --config '{"parallel": 3}'

crossbar shell --realm mrealm1 add webcluster-node cluster1 node2 \
    --config '{"parallel": 3}'

crossbar shell --realm mrealm1 add webcluster-node cluster1 node3 \
    --config '{"parallel": 2}'

crossbar shell --realm mrealm1 list webcluster-nodes cluster1

# add service to the webcluster
crossbar shell --realm mrealm1 add webcluster-service cluster1 '/' \
    --config '{"type": "static", "directory": "/tmp", "options": {"enable_directory_listing": true}}'

crossbar shell --realm mrealm1 add webcluster-service cluster1 'hello' \
    --config '{"type": "json", "value": "0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789"}'

crossbar shell --realm mrealm1 add webcluster-service cluster1 'info' \
    --config '{"type": "nodeinfo"}'

crossbar shell --realm mrealm1 list webcluster-services cluster1
crossbar shell --realm mrealm1 show webcluster-service cluster1 "/"
crossbar shell --realm mrealm1 show webcluster-service cluster1 "hello"
crossbar shell --realm mrealm1 show webcluster-service cluster1 "info"

# start the webcluster
crossbar shell --realm mrealm1 start webcluster cluster1
crossbar shell --realm mrealm1 show webcluster cluster1
for i in `seq 1 100`;
do
    sh -c 'curl -s http://localhost:8080/info | grep "with PID"'
done
sleep 1

# stop the webcluster
#crossbar shell --realm mrealm1 stop webcluster cluster1
#crossbar shell --realm mrealm1 show webcluster cluster1
#sleep 1

# remove all webcluster resources
#crossbar shell --realm mrealm1 remove webcluster-service cluster1 '/'
#crossbar shell --realm mrealm1 remove webcluster-service cluster1 'hello'
#crossbar shell --realm mrealm1 remove webcluster-service cluster1 'info'
#crossbar shell --realm mrealm1 remove webcluster-node cluster1 node1
#crossbar shell --realm mrealm1 remove webcluster-node cluster1 node2
#crossbar shell --realm mrealm1 remove webcluster-node cluster1 node3
#crossbar shell --realm mrealm1 delete webcluster cluster1
#sleep 2

# stop all nodes
crossbar shell --realm mrealm1 list nodes --online
crossbar shell --realm mrealm1 list nodes --offline

crossbar edge stop --cbdir ${SCRIPT_DIR}/cf1/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf2/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf3/.crossbar

crossbar shell --realm mrealm1 list nodes --online
crossbar shell --realm mrealm1 list nodes --offline

crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar
