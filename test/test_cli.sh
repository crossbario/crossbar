#!/bin/sh

cwd=$(pwd)

# version
#
crossbar --personality=standalone version

# legal
#
#crossbar legal

# status
#
#crossbar status

# start (from empty node dir)
#
#rm -rf /tmp/testnode && mkdir /tmp/testnode
#cd /tmp/testnode && crossbar start &
#find /tmp/testnode
#sleep 5
#crossbar stop

# cd $(cwd)


# init and start
#
rm -rf /tmp/testnode
crossbar init --appdir=/tmp/testnode
find /tmp/testnode
(crossbar --personality=standalone start --cbdir=/tmp/testnode/.crossbar) &
sleep 5
crossbar stop --cbdir=/tmp/testnode/.crossbar
