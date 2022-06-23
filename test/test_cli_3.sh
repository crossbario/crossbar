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

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes with mrealm: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell pair node ${SCRIPT_DIR}/cf1/.crossbar/key.pub mrealm1 node1
crossbar edge start --cbdir ${SCRIPT_DIR}/cf1/.crossbar &
sleep 2
crossbar shell --realm mrealm1 show node node1

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> List Docker images on edge node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list docker-images node1
echo "\n>>>>>>> List Docker containers on edge node: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar shell --realm mrealm1 list docker-containers node1
sleep 2

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop the edge and master nodes: >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbar edge stop --cbdir ${SCRIPT_DIR}/cf1/.crossbar
crossbar master stop --cbdir ${SCRIPT_DIR}/cfc/.crossbar

echo "\n################################################################################################################################################################"
