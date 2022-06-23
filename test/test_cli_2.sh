#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub

# SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(pwd)/test

echo "Using SCRIPT_DIR=${SCRIPT_DIR}"
echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbar/* if it doesn't yet exist
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Authenticate the CLI client (shell) and print version info: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell init --yes
crossbar master version

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop all nodes (if any are running) and scratch all data: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
mkdir -p ${SCRIPT_DIR}/cfc/.crossbar
mkdir -p ${SCRIPT_DIR}/cf1/.crossbar
mkdir -p ${SCRIPT_DIR}/cf2/.crossbar
mkdir -p ${SCRIPT_DIR}/cf3/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf1/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf2/.crossbar
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf3/.crossbar
crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar
rm -rf ${SCRIPT_DIR}/cfc/.crossbar/.db-*

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Start the master node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar master start --cbdir ${SCRIPT_DIR}/cfc/.crossbar &
sleep 5

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Authenticate the CLI client (shell): >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell init --yes
echo "\n>>>>>>> Create a new mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell create mrealm mrealm1
echo "\n>>>>>>> List mrealms, this must have 1 mrealm entry: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell list mrealms
sleep 3

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 show node node1
crossbar shell --realm mrealm1 show node node2
crossbar shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Unpairing all nodes from mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell unpair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub
crossbar shell unpair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub
crossbar shell unpair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub
echo "\n>>>>>>> Nodes unpaired! The list of nodes in the mrealm must be empty: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list nodes
echo "\n>>>>>>> Deleting the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell delete mrealm mrealm1
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Re-create the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell create mrealm mrealm1
echo "\n>>>>>>> Re-Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes re-paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 show node node1
crossbar shell --realm mrealm1 show node node2
crossbar shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Deleting the mrealm (with CASCADE unpair of all nodes): >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell delete mrealm mrealm1 --cascade
echo "\n>>>>>>> Mrealm deleted! The list of mrealms must be empty: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell list mrealms
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Re-create the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell create mrealm mrealm1
echo "\n>>>>>>> Re-pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ${SCRIPT_DIR}/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ${SCRIPT_DIR}/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 show node node1
crossbar shell --realm mrealm1 show node node2
crossbar shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop the master node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar

echo "\n################################################################################################################################################################"
