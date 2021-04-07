#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbarfx/* if it doesn't yet exist
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Authenticate the CLI client (shell) and print version info: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell init --yes
crossbarfx master version

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop all nodes (if any are running) and scratch all data: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
mkdir -p ./test/cfc/.crossbar
mkdir -p ./test/cf1/.crossbar
mkdir -p ./test/cf2/.crossbar
mkdir -p ./test/cf3/.crossbar
crossbarfx edge stop --cbdir ./test/cf1/.crossbar
crossbarfx edge stop --cbdir ./test/cf2/.crossbar
crossbarfx edge stop --cbdir ./test/cf3/.crossbar
crossbarfx master stop --cbdir ./test/cfc/.crossbar
rm -rf ./test/cfc/.crossbar/.db-*

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Start the master node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx master start --cbdir ./test/cfc/.crossbar &
sleep 5

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Authenticate the CLI client (shell): >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell init --yes
echo "\n>>>>>>> Create a new mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell create mrealm mrealm1
echo "\n>>>>>>> List mrealms, this must have 1 mrealm entry: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell list mrealms
sleep 3

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 show node node1
crossbarfx shell --realm mrealm1 show node node2
crossbarfx shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Unpairing all nodes from mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell unpair node ./test/cf1/.crossbar/key.pub
crossbarfx shell unpair node ./test/cf2/.crossbar/key.pub
crossbarfx shell unpair node ./test/cf3/.crossbar/key.pub
echo "\n>>>>>>> Nodes unpaired! The list of nodes in the mrealm must be empty: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list nodes
echo "\n>>>>>>> Deleting the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell delete mrealm mrealm1
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Re-create the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell create mrealm mrealm1
echo "\n>>>>>>> Re-Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes re-paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 show node node1
crossbarfx shell --realm mrealm1 show node node2
crossbarfx shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Deleting the mrealm (with CASCADE unpair of all nodes): >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell delete mrealm mrealm1 --cascade
echo "\n>>>>>>> Mrealm deleted! The list of mrealms must be empty: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell list mrealms
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Re-create the mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell create mrealm mrealm1
echo "\n>>>>>>> Re-pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
echo "\n>>>>>>> Nodes paired! The list of nodes in the mrealm must have all nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list nodes
echo "\n>>>>>>> Check each node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 show node node1
crossbarfx shell --realm mrealm1 show node node2
crossbarfx shell --realm mrealm1 show node node3
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop the master node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx master stop --cbdir ./test/cfc/.crossbar

echo "\n################################################################################################################################################################"
