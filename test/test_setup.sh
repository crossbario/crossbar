#!/bin/sh

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

# this will create ~/.crossbarfx/* if it doesn't yet exist
crossbarfx shell init --yes
crossbarfx master version

# start CFC node
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Start the master node >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
CROSSBARFX_METERING_URL="" CROSSBARFX_DISABLE_CE=1 crossbarfx master start --cbdir ./test/cfc/.crossbar &
sleep 5
echo "\n>>>>>>> Master node started >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"

# authenticate, create new management realm and pair the 3 CF nodes
echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Creating mrealm >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell init --yes
crossbarfx shell create mrealm mrealm1
sleep 5

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Pairing nodes >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx shell list mrealms
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3

echo "\n################################################################################################################################################################"
echo "\n>>>>>>> Stop master node >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
crossbarfx master stop --cbdir ./test/cfc/.crossbar
