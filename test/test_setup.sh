#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub

# SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(pwd)/test

echo "Using SCRIPT_DIR=${SCRIPT_DIR}"
echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# create superuser key
crossbar shell init --yes

# pre-create node keys
mkdir -p ${SCRIPT_DIR}/cf1/.crossbar
mkdir -p ${SCRIPT_DIR}/cf2/.crossbar
mkdir -p ${SCRIPT_DIR}/cf3/.crossbar
CROSSBAR_NODE_ID=core1 CROSSBAR_NODE_CLUSTER_IP=core1 crossbar edge keys --cbdir=${SCRIPT_DIR}/cf1/.crossbar
CROSSBAR_NODE_ID=core2 CROSSBAR_NODE_CLUSTER_IP=core2 crossbar edge keys --cbdir=${SCRIPT_DIR}/cf2/.crossbar
CROSSBAR_NODE_ID=core3 CROSSBAR_NODE_CLUSTER_IP=core3 crossbar edge keys --cbdir=${SCRIPT_DIR}/cf3/.crossbar

# start CFC node
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Start the master node >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar_METERING_URL="" CROSSBAR_DISABLE_CE=1 crossbar master start --cbdir ${SCRIPT_DIR}/cfc/.crossbar &
sleep 5
echo "\n>>>>>>> Master node started >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"

# authenticate, create new management realm and pair the 3 CF nodes
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Creating mrealm >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell init --yes
crossbar shell create mrealm mrealm1
sleep 5

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell list mrealms
crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub mrealm1 node3

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop master node >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar
