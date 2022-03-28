#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub

SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbar/* if it doesn't yet exist
crossbar shell init --yes
crossbar master version

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
