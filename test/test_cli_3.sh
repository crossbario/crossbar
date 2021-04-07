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

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx edge start --cbdir ./test/cf1/.crossbar &
sleep 2
crossbarfx shell --realm mrealm1 show node node1

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> List Docker images on edge node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list docker-images node1
echo "\n>>>>>>> List Docker containers on edge node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell --realm mrealm1 list docker-containers node1
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop the edge and master nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx edge stop --cbdir ./test/cf1/.crossbar
crossbarfx master stop --cbdir ./test/cfc/.crossbar

echo "\n################################################################################################################################################################"
