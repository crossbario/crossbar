CROSSBAR=crossbarfx
CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub
CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
CROSSBAR_WATCH_TO_PAIR=../nodes

init_shell:
	CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
	${CROSSBAR} shell init --yes

clean:
	rm -rf ./.test

init_nodes:
	mkdir -p ./.test/nodes
	mkdir -p ./.test/master
	CROSSBAR_NODE_ID=node1 ${CROSSBAR} edge keys --cbdir=./.test/nodes/node1
	CROSSBAR_NODE_ID=node2 ${CROSSBAR} edge keys --cbdir=./.test/nodes/node2
	CROSSBAR_NODE_ID=node3 ${CROSSBAR} edge keys --cbdir=./.test/nodes/node3
	CROSSBAR_NODE_ID=node4 ${CROSSBAR} edge keys --cbdir=./.test/nodes/node4
	find ./.test/nodes

run_master:
	mkdir -p ./.test/master
	mkdir -p ./.test/nodes
	CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER} \
	CROSSBAR_WATCH_TO_PAIR=${CROSSBAR_WATCH_TO_PAIR} \
	${CROSSBAR} master start --cbdir=./.test/master

run_node1:
	CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
	${CROSSBAR} edge start --cbdir=./.test/nodes/node1

run_node2:
	CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
	${CROSSBAR} edge start --cbdir=./.test/nodes/node2

run_node3:
	CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
	${CROSSBAR} edge start --cbdir=./.test/nodes/node3

run_node4:
	CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL} \
	${CROSSBAR} edge start --cbdir=./.test/nodes/node4

setup1:
	./test_setup1.sh

setup2:
	./test_setup2.sh

setup3:
	./test_setup3.sh





test1:
	curl -s http://localhost:8080/info | grep PID

test2:
	python client.py --realm myrealm1 &
	python client.py --realm myrealm1 &
	python client.py --realm myrealm1 &
	python client.py --realm myrealm2 &
	python client.py --realm myrealm2 &
	python client.py --realm myrealm3 &
	python client.py --realm myrealm4 &
