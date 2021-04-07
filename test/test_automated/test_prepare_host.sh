#!/bin/sh

CROSSBAR=crossbar
CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub
CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
CROSSBAR_WATCH_TO_PAIR=../nodes

if [ ! -f ${CROSSBAR_FABRIC_SUPERUSER} ]; then
  CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} ${CROSSBAR} shell init --yes
fi

if [ -d ./.test ]; then
  ${CROSSBAR} master stop --cbdir=./.test/master
  ${CROSSBAR} edge stop --cbdir=./.test/nodes/node1
  ${CROSSBAR} edge stop --cbdir=./.test/nodes/node2
  ${CROSSBAR} edge stop --cbdir=./.test/nodes/node3
  ${CROSSBAR} edge stop --cbdir=./.test/nodes/node4
  rm -rf ./.test
fi

mkdir -p ./.test/nodes
mkdir -p ./.test/master
CROSSBAR_NODE_ID=node1 `which crossbar` edge keys --cbdir=./.test/nodes/node1
CROSSBAR_NODE_ID=node2 `which crossbar` edge keys --cbdir=./.test/nodes/node2
CROSSBAR_NODE_ID=node3 `which crossbar` edge keys --cbdir=./.test/nodes/node3
CROSSBAR_NODE_ID=node4 `which crossbar` edge keys --cbdir=./.test/nodes/node4

CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER} CROSSBAR_WATCH_TO_PAIR=${CROSSBAR_WATCH_TO_PAIR} \
  ${CROSSBAR} master start --cbdir=./.test/master &

while ! curl -s http://localhost:9000/info > /dev/null
do
  echo "$(date) - master: still trying"
  sleep 1
done
echo "$(date) - master: connected successfully"

echo "sleep 20s .."
sleep 20

CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
  ${CROSSBAR} edge start --cbdir=./.test/nodes/node1 &

CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
  ${CROSSBAR} edge start --cbdir=./.test/nodes/node2 &

CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
  ${CROSSBAR} edge start --cbdir=./.test/nodes/node3 &

CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
  ${CROSSBAR} edge start --cbdir=./.test/nodes/node4 &

echo "done! sleep 30s .."
sleep 30
