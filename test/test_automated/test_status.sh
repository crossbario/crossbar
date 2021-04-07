#!/bin/sh

#
# Global
#
crossbarfx shell show status

#
# Management Realms
#
crossbarfx shell list mrealms
crossbarfx shell list mrealms --names
crossbarfx shell show mrealm default

#
# Managed Nodes
#
crossbarfx shell --realm default list nodes
crossbarfx shell --realm default list nodes --names

crossbarfx shell --realm default show node
crossbarfx shell --realm default show node node1,node2,node3,node4

#
# Web Clusters
#
crossbarfx shell --realm default list webclusters
crossbarfx shell --realm default list webclusters --names

crossbarfx shell --realm default show webcluster
crossbarfx shell --realm default show webcluster cluster1

crossbarfx shell --realm default list webcluster-nodes cluster1
crossbarfx shell --realm default list webcluster-nodes cluster1 --names
crossbarfx shell --realm default list webcluster-nodes cluster1 --filter-status online
crossbarfx shell --realm default list webcluster-nodes cluster1 --names --filter-status online

crossbarfx shell --realm default show webcluster-node cluster1 node1
crossbarfx shell --realm default show webcluster-node cluster1
crossbarfx shell --realm default show webcluster-node cluster1 node1,node2,node3,node4

# crossbarfx shell --realm default list webcluster-workers cluster1 node1
# crossbarfx shell --realm default list webcluster-workers cluster1 node1 --names
# crossbarfx shell --realm default list webcluster-workers cluster1 node1 --filter-status online
# crossbarfx shell --realm default list webcluster-workers cluster1 node1 --names --filter-status online

# crossbarfx shell --realm default show webcluster-worker cluster1 node1 worker1
# crossbarfx shell --realm default show webcluster-worker cluster1 node1
# crossbarfx shell --realm default show webcluster-worker cluster1
# crossbarfx shell --realm default show webcluster-worker cluster1 node1 worker1,worker2,worker3

crossbarfx shell --realm default list webcluster-services cluster1

# crossbarfx shell --realm default show webcluster-service cluster1
crossbarfx shell --realm default show webcluster-service cluster1 "settings"

#
# Router Clusters
#
crossbarfx shell --realm default list routerclusters
crossbarfx shell --realm default list routerclusters --names

crossbarfx shell --realm default show routercluster
crossbarfx shell --realm default show routercluster cluster2

crossbarfx shell --realm default list routercluster-nodes cluster2
crossbarfx shell --realm default list routercluster-nodes cluster2 --names
crossbarfx shell --realm default list routercluster-nodes cluster2 --filter-status online
crossbarfx shell --realm default list routercluster-nodes cluster2 --names --filter-status online

crossbarfx shell --realm default show routercluster-node cluster2
crossbarfx shell --realm default show routercluster-node cluster2 node1
crossbarfx shell --realm default show routercluster-node cluster2 node1,node2,node3,node4

# crossbarfx shell --realm default list routercluster-workergroups cluster2
# crossbarfx shell --realm default list routercluster-workergroups cluster2 --names

# crossbarfx shell --realm default show routercluster-workergroup cluster2
crossbarfx shell --realm default show routercluster-workergroup cluster2 mygroup1
crossbarfx shell --realm default show routercluster-workergroup cluster2 mygroup2
crossbarfx shell --realm default show routercluster-workergroup cluster2 mygroup3

# crossbarfx shell --realm default list routercluster-workers cluster2 mygroup1
# crossbarfx shell --realm default list routercluster-workers cluster2 mygroup1 --names
# crossbarfx shell --realm default list routercluster-workers cluster2 mygroup2
# crossbarfx shell --realm default list routercluster-workers cluster2 mygroup3

# crossbarfx shell --realm default show routercluster-worker cluster2 mygroup1 mygroup1_1
# crossbarfx shell --realm default show routercluster-worker cluster2 mygroup1
# crossbarfx shell --realm default show routercluster-worker cluster2
# crossbarfx shell --realm default show routercluster-worker cluster2 mygroup1 mygroup1_1,mygroup1_2,mygroup3_1

#
# Application Realms
#
crossbarfx shell --realm default show role myrole1

crossbarfx shell --realm default show arealm myrealm1
crossbarfx shell --realm default show arealm myrealm2
crossbarfx shell --realm default show arealm myrealm3
crossbarfx shell --realm default show arealm myrealm4
