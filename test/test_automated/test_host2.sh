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

python test_ci.py --realms 1 --repeat 10 --count 200
if [ $? -ne 0 ]
then
  ((errored++))
fi
# {'node3': {'mygroup1_4': 200}}
# FIXME: => proxy workers should distribute incoming connections to any (of multiple) route defined
# to an available backend!

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
