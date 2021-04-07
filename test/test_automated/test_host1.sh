#!/bin/bash

# we want individual failed test not stop the whole script
# set -e

CROSSBAR=crossbar
CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub
CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
CROSSBAR_WATCH_TO_PAIR=../nodes

while ! curl -s http://localhost:8080/info > /dev/null
do
  echo "$(date) - public endpoint: still trying (sleeping for 1s)"
  sleep 1
done
echo "$(date) - public endpoint: connected successfully"

echo ""
echo "**************************************************************************************"
echo "******************************** START TEST ******************************************"
echo "**************************************************************************************"
echo ""

errored=0

echo ""
echo "******************************** TEST-1 **********************************************"
echo ""
python test_ci.py --realms 4 --repeat 1 --count 1
if [ $? -ne 0 ]
then
  ((errored++))
fi

echo ""
echo "******************************** TEST-2 **********************************************"
echo ""
python test_ci.py --realms 1 --repeat 7 --count 200
if [ $? -ne 0 ]
then
  ((errored++))
fi
# {'node3': {'mygroup1_1': 200}}

echo ""
echo "******************************** TEST-3 **********************************************"
echo ""
python test_ci.py --realms 2 --repeat 5 --count 100
if [ $? -ne 0 ]
then
  ((errored++))
fi
# {'node1': {'mygroup2_1': 100}, 'node3': {'mygroup1_1': 100}}

echo ""
echo "******************************** TEST-4 **********************************************"
echo ""
python test_ci.py --realms 4 --repeat 9 --count 50
if [ $? -ne 0 ]
then
  ((errored++))
fi
# {'node1': {'mygroup2_1': 50}, 'node3': {'mygroup1_1': 50}, 'node4': {'mygroup3_1': 100}}

echo ""
echo "**************************************************************************************"
echo "******************************** END TEST ********************************************"
echo "**************************************************************************************"
echo ""

if [ -z "$1" ]
then
    echo "skipping stop/remove test cluster"
else
    echo "stopping/removing test cluster .."
    ./test_stop_host.sh
fi

if [ $errored -ne 0 ]
then
  echo "FAILED: $errored tests errored"
  exit 1
else
  echo "OK: all tests succeeded!"
  exit 0
fi
