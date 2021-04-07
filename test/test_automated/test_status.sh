#!/bin/sh

#
# Global
#
crossbar shell show status

#
# Management Realms
#
crossbar shell list mrealms
crossbar shell list mrealms --names
crossbar shell show mrealm default

#
# Managed Nodes
#
crossbar shell --realm default list nodes
crossbar shell --realm default list nodes --names

crossbar shell --realm default show node
crossbar shell --realm default show node node1,node2,node3,node4

#
# Web Clusters
#
crossbar shell --realm default list webclusters
crossbar shell --realm default list webclusters --names

crossbar shell --realm default show webcluster
crossbar shell --realm default show webcluster cluster1

crossbar shell --realm default list webcluster-nodes cluster1
crossbar shell --realm default list webcluster-nodes cluster1 --names
crossbar shell --realm default list webcluster-nodes cluster1 --filter-status online
crossbar shell --realm default list webcluster-nodes cluster1 --names --filter-status online

crossbar shell --realm default show webcluster-node cluster1 node1
crossbar shell --realm default show webcluster-node cluster1
crossbar shell --realm default show webcluster-node cluster1 node1,node2,node3,node4

# crossbar shell --realm default list webcluster-workers cluster1 node1
# crossbar shell --realm default list webcluster-workers cluster1 node1 --names
# crossbar shell --realm default list webcluster-workers cluster1 node1 --filter-status online
# crossbar shell --realm default list webcluster-workers cluster1 node1 --names --filter-status online

# crossbar shell --realm default show webcluster-worker cluster1 node1 worker1
# crossbar shell --realm default show webcluster-worker cluster1 node1
# crossbar shell --realm default show webcluster-worker cluster1
# crossbar shell --realm default show webcluster-worker cluster1 node1 worker1,worker2,worker3

crossbar shell --realm default list webcluster-services cluster1

# crossbar shell --realm default show webcluster-service cluster1
crossbar shell --realm default show webcluster-service cluster1 "settings"

#
# Router Clusters
#
crossbar shell --realm default list routerclusters
crossbar shell --realm default list routerclusters --names

crossbar shell --realm default show routercluster
crossbar shell --realm default show routercluster cluster2

crossbar shell --realm default list routercluster-nodes cluster2
crossbar shell --realm default list routercluster-nodes cluster2 --names
crossbar shell --realm default list routercluster-nodes cluster2 --filter-status online
crossbar shell --realm default list routercluster-nodes cluster2 --names --filter-status online

crossbar shell --realm default show routercluster-node cluster2
crossbar shell --realm default show routercluster-node cluster2 node1
crossbar shell --realm default show routercluster-node cluster2 node1,node2,node3,node4

# crossbar shell --realm default list routercluster-workergroups cluster2
# crossbar shell --realm default list routercluster-workergroups cluster2 --names

# crossbar shell --realm default show routercluster-workergroup cluster2
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup1
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup2
crossbar shell --realm default show routercluster-workergroup cluster2 mygroup3

# crossbar shell --realm default list routercluster-workers cluster2 mygroup1
# crossbar shell --realm default list routercluster-workers cluster2 mygroup1 --names
# crossbar shell --realm default list routercluster-workers cluster2 mygroup2
# crossbar shell --realm default list routercluster-workers cluster2 mygroup3

# crossbar shell --realm default show routercluster-worker cluster2 mygroup1 mygroup1_1
# crossbar shell --realm default show routercluster-worker cluster2 mygroup1
# crossbar shell --realm default show routercluster-worker cluster2
# crossbar shell --realm default show routercluster-worker cluster2 mygroup1 mygroup1_1,mygroup1_2,mygroup3_1

#
# Application Realms
#
crossbar shell --realm default show role myrole1

crossbar shell --realm default show arealm myrealm1
crossbar shell --realm default show arealm myrealm2
crossbar shell --realm default show arealm myrealm3
crossbar shell --realm default show arealm myrealm4
