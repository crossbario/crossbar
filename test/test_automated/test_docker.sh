#!/bin/sh

# log example: https://gist.github.com/oberstet/b0698b8ca2a3da28a68b13afaee69607

# https://serverfault.com/a/941314/117074
docker-compose rm --stop
docker-compose down
docker-compose rm -f

sudo rm -rf ./.test
sudo mkdir -p ./.test/nodes
sudo CROSSBAR_NODE_ID=node1 `which crossbar` edge keys --cbdir=./.test/nodes/node1
sudo CROSSBAR_NODE_ID=node2 `which crossbar` edge keys --cbdir=./.test/nodes/node2
sudo CROSSBAR_NODE_ID=node3 `which crossbar` edge keys --cbdir=./.test/nodes/node3
sudo CROSSBAR_NODE_ID=node4 `which crossbar` edge keys --cbdir=./.test/nodes/node4

docker-compose up -d

# now wait until "docker-compose logs --tail=100" returns:
# master     | 2020-08-02T20:08:34+0000 [Container      25] Success: managed node "node1" is now online [oid=79f35fb9-5626-4449-8091-ffb651576f23, session=1047345041252532, status=online] <crossbar.master.mrealm.controller.MrealmController._on_node_heartbeat>
# master     | 2020-08-02T20:08:35+0000 [Container      25] Success: managed node "node3" is now online [oid=301f5c26-ed16-4ee8-8705-12830472e267, session=7723427004653304, status=online] <crossbar.master.mrealm.controller.MrealmController._on_node_heartbeat>
# master     | 2020-08-02T20:08:36+0000 [Container      25] Success: managed node "node2" is now online [oid=19a89cc7-4383-41ad-86b5-f360cf

while ! curl -s http://localhost:1936/ > /dev/null
do
  echo "$(date) - haproxy: still trying"
  sleep 1
done
echo "$(date) - haproxy: connected successfully"

while ! curl -s http://localhost:9000/info > /dev/null
do
  echo "$(date) - master: still trying"
  sleep 1
done
echo "$(date) - master: connected successfully"

echo "sleep .."
sleep 10

./test_setup1.sh

echo "done! sleep .."
sleep 30

while ! curl -s http://localhost:8080/info > /dev/null
do
  echo "$(date) - public endpoint: still trying"
  sleep 1
done
echo "$(date) - public endpoint: connected successfully"

while ! curl -s http://localhost:8081/info > /dev/null
do
  echo "$(date) - node1 endpoint: still trying"
  sleep 1
done
echo "$(date) - node1 endpoint: connected successfully"

while ! curl -s http://localhost:8082/info > /dev/null
do
  echo "$(date) - node2 endpoint: still trying"
  sleep 1
done
echo "$(date) - node2 endpoint: connected successfully"

while ! curl -s http://localhost:8083/info > /dev/null
do
  echo "$(date) - node3 endpoint: still trying"
  sleep 1
done
echo "$(date) - node3 endpoint: connected successfully"

while ! curl -s http://localhost:8084/info > /dev/null
do
  echo "$(date) - node4 endpoint: still trying"
  sleep 1
done
echo "$(date) - node4 endpoint: connected successfully"

echo "completed!"

python client.py --realm myrealm1 &
python client.py --realm myrealm1 &
python client.py --realm myrealm1 &
python client.py --realm myrealm2 &
python client.py --realm myrealm2 &
python client.py --realm myrealm3 &
python client.py --realm myrealm4 &

sleep 30

docker-compose stop
docker-compose rm -f

pkill python
