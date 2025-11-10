# Bug Fix: Stale Worker Placements Prevent Realm Distribution

## Issue

When a Crossbar.io Fabric Center edge node is removed from a router cluster (via `remove_routercluster_node()`), the worker group placements referencing that node were **NOT automatically deleted** from the database. This caused critical issues when nodes were unpaired and re-paired:

1. Old node unpaired → old `node_oid` removed from database
2. Node restarts and re-pairs → gets new `node_oid`
3. Node removed from clusters → membership deleted, **but placements remain**
4. Node added back to clusters → creates new placements with new `node_oid`
5. **Database now has both old (stale) and new placements**
6. ApplicationRealmMonitor tries to process ALL placements
7. Stale placements reference non-existent nodes → monitor fails
8. Realm status stuck in `STATUS_STARTING` → clients never authenticate

## Root Cause

The `remove_routercluster_node()` method in `crossbar/master/cluster/routercluster.py` only deleted the `routercluster_node_memberships` entry but did not cascade the deletion to associated `router_workergroup_placements` entries.

Similarly, `remove_routercluster_workergroup()` did not delete associated placements when removing a workergroup (there was even a FIXME comment acknowledging this).

## Fix Applied

Modified two methods in `/Users/marko/git/crossbar/crossbar/master/cluster/routercluster.py`:

### 1. `remove_routercluster_node()` (Line ~938-989)

**Added code to delete all placements for the node being removed:**

```python
# CRITICAL FIX: Delete all worker placements for this node in all workergroups of this cluster
# This fixes the bug where stale placements prevent realms from redistributing when nodes rejoin
deleted_placements = 0

# Get all workergroups in this router cluster
for workergroup_oid in self.schema.idx_router_workergroups_by_cluster.select(
        txn, 
        from_key=(routercluster_oid_, ),
        return_values=False):
    
    # Find all placements for this workergroup on the node being removed
    # idx_clusterplacement_by_workername: (workergroup_oid, cluster_oid, node_oid, worker_name) -> placement_oid
    placement_oids_to_delete = []
    for placement_oid in self.schema.idx_clusterplacement_by_workername.select(
            txn,
            from_key=(workergroup_oid, routercluster_oid_, node_oid_, ''),
            to_key=(workergroup_oid, routercluster_oid_, uuid.UUID(int=(int(node_oid_) + 1)), ''),
            return_keys=False):
        placement_oids_to_delete.append(placement_oid)
    
    # Delete each placement
    for placement_oid in placement_oids_to_delete:
        del self.schema.router_workergroup_placements[txn, placement_oid]
        deleted_placements += 1
        self.log.debug(
            'Deleted stale worker placement {placement_oid} for node {node_oid} in workergroup {workergroup_oid}',
            placement_oid=hlid(placement_oid),
            node_oid=hlid(node_oid_),
            workergroup_oid=hlid(workergroup_oid))

if deleted_placements > 0:
    self.log.info(
        'Cleaned up {count} stale worker placement(s) for node {node_oid} being removed from router cluster {cluster_oid}',
        count=hlval(deleted_placements),
        node_oid=hlid(node_oid_),
        cluster_oid=hlid(routercluster_oid_))
```

### 2. `remove_routercluster_workergroup()` (Line ~1318-1347)

**Added code to delete all placements for the workergroup being removed:**

```python
# CRITICAL FIX: Delete all worker placements for this workergroup
# This fixes the bug where stale placements remain when workergroups are deleted
deleted_placements = 0

# Find all placements for this workergroup
# idx_clusterplacement_by_workername: (workergroup_oid, cluster_oid, node_oid, worker_name) -> placement_oid
placement_oids_to_delete = []
for placement_oid in self.schema.idx_clusterplacement_by_workername.select(
        txn,
        from_key=(workergroup_oid_, uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
        to_key=(uuid.UUID(int=(int(workergroup_oid_) + 1)), uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
        return_keys=False):
    placement_oids_to_delete.append(placement_oid)

# Delete each placement
for placement_oid in placement_oids_to_delete:
    del self.schema.router_workergroup_placements[txn, placement_oid]
    deleted_placements += 1
    self.log.debug(
        'Deleted worker placement {placement_oid} for workergroup {workergroup_oid}',
        placement_oid=hlid(placement_oid),
        workergroup_oid=hlid(workergroup_oid_))

if deleted_placements > 0:
    self.log.info(
        'Cleaned up {count} worker placement(s) for workergroup {workergroup_oid} being removed',
        count=hlval(deleted_placements),
        workergroup_oid=hlid(workergroup_oid_))
```

## Impact

This fix ensures proper cascading deletion of database records, preventing orphaned placements from blocking realm distribution.

**Before the fix:**
- Nodes could never be successfully re-added to clusters after restart
- Application realms stuck in `STATUS_STARTING` indefinitely
- Client authentication failures persisted forever
- Required manual database cleanup or arealm restart workarounds

**After the fix:**
- Node removal cleanly deletes all associated placements
- Nodes can be re-added to clusters without stale data interference
- Application realms properly distribute to all active nodes
- Client authentication works immediately upon node rejoin

## Testing

To verify the fix works:

1. Start with a node in a router cluster with active realms
2. Unpair and remove the node from clusters
3. Check logs - should see: `"Cleaned up N stale worker placement(s) for node {node_oid}"`
4. Re-pair the node with a new UUID
5. Add node back to clusters
6. Monitor ApplicationRealmMonitor logs - should NOT see: `"Router cluster node {node_oid} from placement not found!"`
7. Check arealm status - should transition from `STARTING` to `RUNNING` within 10-20 seconds
8. Verify clients can authenticate successfully on the rejoined node

## Related Files

- `/Users/marko/git/crossbar/crossbar/master/cluster/routercluster.py` - Fixed file
- `/Users/marko/git/crossbar/crossbar/master/arealm/arealm.py` - ApplicationRealmMonitor (consumer of placements)
- `/Users/marko/git/crossbar/NODE-REJOIN-REALM-ISSUE.md` - Detailed analysis of the bug

## Version

- **Crossbar.io Version**: 23.1.2 (and likely earlier versions)
- **Fix Date**: 2025-10-18
- **Severity**: Critical - prevents production operations
