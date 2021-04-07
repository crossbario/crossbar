#!/bin/sh

CROSSBAR=crossbarfx
CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub
CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
CROSSBARFX_WATCH_TO_PAIR=../nodes

pkill python

${CROSSBAR} edge stop --cbdir=./.test/nodes/node4
${CROSSBAR} edge stop --cbdir=./.test/nodes/node3
${CROSSBAR} edge stop --cbdir=./.test/nodes/node2
${CROSSBAR} edge stop --cbdir=./.test/nodes/node1
${CROSSBAR} master stop --cbdir=./.test/master

rm -rf ./.test
