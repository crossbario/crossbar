# Router Cluster Placement Fix (Rlink Connections)

## Problem Overview

### Issue
When router placements were created in a router cluster with multiple worker groups, each router worker was only attempting to establish rlink (router-to-router link) connections to routers in **other worker groups**, but not to other routers **within the same worker group**. This caused incomplete mesh connectivity in the router cluster.

**Symptom:**
- Router A (workergroup_userapps) connects to Router B (workergroup_realm1) ✓
- Router B connects to Router A ✓
- But if Router C joins workergroup_userapps, Router A and Router C don't connect to each other ✗

### Root Cause

The rlink connection logic was filtering placements to only include routers from **different** worker groups:

```python
# OLD CODE (BUGGY)
for placement in workergroup_placements:
    # Only process placements in OTHER worker groups
    if placement.worker_group_oid == this_placement.worker_group_oid:
        continue  # Skip same worker group!
```

This was based on incorrect assumptions:
1. ❌ Workers in the same worker group are on the same node (not always true)
2. ❌ Workers on the same node can use local IPC (they still need TCP/WAMP connections)
3. ❌ Only cross-worker-group connections need to be established

**Reality:**
- Multiple worker groups can be placed on the **same node** (different workers)
- Multiple placements of the same worker group can be on **different nodes**
- **ALL** routers in a cluster need to be interconnected, regardless of worker group membership

## Solution

### Remove Worker Group Filtering

Changed the logic to establish rlink connections to **all other routers** in the cluster, regardless of worker group:

```python
# NEW CODE (FIXED)
for placement in workergroup_placements:
    # Connect to all other routers in the cluster
    # (but skip connecting to yourself)
    if (placement.node_oid == this_placement.node_oid and 
        placement.worker_name == this_placement.worker_name):
        continue  # Only skip self
    
    # Establish rlink connection to this router
    yield self._establish_rlink_connection(...)
```

### Key Changes

**Before:**
- Filter: Skip if `placement.worker_group_oid == this_worker_group_oid`
- Result: Only cross-worker-group connections

**After:**  
- Filter: Skip if `(placement.node_oid == this_node_oid AND placement.worker_name == this_worker_name)`
- Result: Connect to all routers except yourself

## Files Modified

### `/Users/marko/git/crossbar/crossbar/master/arealm/arealm.py`

**Lines 963-1200**: Modified `_apply_routercluster_placements()` method

**Before (lines ~975-980)**:
```python
for placement in workergroup_placements:
    # only process other router workers (in other worker groups than the one
    # we are currently processing, but same router cluster and application realm)
    if placement.worker_group_oid == this_placement.worker_group_oid:
        continue
```

**After**:
```python
for placement in workergroup_placements:
    # Connect to ALL other routers in the cluster, regardless of worker group
    # Only skip connecting to yourself (same node + same worker)
    if (placement.node_oid == this_placement.node_oid and 
        placement.worker_name == this_placement.worker_name):
        continue
```

## Detailed Changes

### The Fix in Context

```python
@inlineCallbacks
def _apply_routercluster_placements(self, arealm, session, placement_nodes, workergroup_placements):
    """Apply router cluster placements and establish rlink connections."""
    
    for this_placement in workergroup_placements:
        this_node_oid = this_placement.node_oid
        this_worker_name = this_placement.worker_name
        
        # For each router, establish connections to ALL OTHER routers
        for placement in workergroup_placements:
            # NEW: Only skip if it's literally the same worker on the same node
            if (placement.node_oid == this_node_oid and 
                placement.worker_name == this_worker_name):
                continue  # Don't connect to yourself
            
            # OLD: Skipped all routers in the same worker group
            # if placement.worker_group_oid == this_placement.worker_group_oid:
            #     continue
            
            # Establish rlink connection
            other_node_oid = placement.node_oid
            other_worker_name = placement.worker_name
            other_cluster_ip = placement_nodes[other_node_oid].cluster_ip
            
            self.log.info('Rlink other node worker is on node {node}, worker {worker}, '
                         'cluster_ip {ip}:',
                         node=other_node_oid,
                         worker=other_worker_name, 
                         ip=other_cluster_ip)
            
            # Create realm rlink connection
            rlink = yield self._create_realm_rlink(
                session, 
                this_node_oid, this_worker_name,
                arealm, realm_config,
                other_node_oid, other_worker_name, other_cluster_ip)
```

## Understanding Rlink Connections

### What is an Rlink?

An **rlink** (router link) is a WAMP connection between two router workers that allows them to:
- Share subscriptions (distributed PubSub)
- Share registrations (distributed RPC)
- Route calls/events across the cluster
- Create a transparent routing mesh

### Rlink Connection Structure

Each rlink connection involves:

1. **Backend Transport** on target router:
   - TCP rawsocket listener (port auto-assigned 10000-10100)
   - Authenticates connecting routers via cryptosign-proxy
   - Shared by all rlinks to that router

2. **Rlink Configuration** on source router:
   - Connects to target's backend transport
   - Joins application realm with role 'rlink'
   - Bidirectional connection (A→B and B→A are separate)

### Connection Topology

**With the bug (3 routers, 2 worker groups):**
```
Router A (wg1)  ←→  Router B (wg2)
Router C (wg1)  ←→  Router B (wg2)
Router A (wg1)   ✗   Router C (wg1)  # Missing!
```

**After the fix:**
```
Router A (wg1)  ←→  Router B (wg2)
Router A (wg1)  ←→  Router C (wg1)
Router B (wg2)  ←→  Router C (wg1)
```
Complete mesh: Every router connected to every other router.

## Why Worker Group Filtering Was Wrong

### Original Assumption (Incorrect)
"Workers in the same worker group are co-located and can use efficient local communication"

### Reality
1. **Worker groups are logical, not physical**:
   - Multiple worker groups can run on the same physical node
   - Example: `workergroup_userapps` and `workergroup_realm1` both on `router_node_1`

2. **Same worker group can span multiple nodes**:
   - `workergroup_userapps` might have placements on `node1` and `node2`
   - They need TCP/WAMP connections like any other routers

3. **Worker groups are for organization, not optimization**:
   - Used to group workers by purpose (realm handling, app logic, etc.)
   - Don't dictate communication patterns

### Correct Approach
- **Physical**: Only skip if **same node AND same worker** (literally the same process)
- **Logical**: Connect to all other routers in the cluster
- **Complete mesh**: Every router knows about every other router

## Example Scenarios

### Scenario 1: Multi-Worker-Group Cluster

**Setup:**
- Node 1: workergroup_realm1 
- Node 2: workergroup_userapps

**Old behavior:**
- ✓ realm1 ↔ userapps connections established (different worker groups)

**No issue here** - this case worked even with the bug.

### Scenario 2: Same Worker Group, Different Nodes

**Setup:**
- Node 1: workergroup_userapps_1
- Node 2: workergroup_userapps_2  
- Both in same worker group: `workergroup_userapps`

**Old behavior:**
- ✗ No connection between userapps_1 and userapps_2 (same worker group)
- ✗ Incomplete cluster mesh

**New behavior:**
- ✓ userapps_1 ↔ userapps_2 connection established
- ✓ Complete mesh

### Scenario 3: Scale-Out Within Worker Group

**Setup:**
- Start: Node 1 has workergroup_userapps_1
- Add: Node 2 gets workergroup_userapps_2 (scale out)

**Old behavior:**
- ✗ New router userapps_2 not connected to existing userapps_1
- ✗ Split-brain: Two isolated routers in same logical group

**New behavior:**
- ✓ userapps_2 automatically connects to userapps_1
- ✓ Seamless cluster expansion

## Rlink Creation Process

### Step-by-Step

1. **Query all placements** for this application realm
2. **For each router** (this_placement):
   - For each **other router** (placement):
     - Skip if it's the same worker (same node + same worker name)
     - Get other router's cluster IP and backend transport port
     - Create rlink configuration:
       ```python
       {
           'id': 'rlink_{other_worker_name}',
           'realm': arealm.name,
           'transport': {
               'type': 'rawsocket',
               'endpoint': {
                   'type': 'tcp',
                   'host': other_cluster_ip,
                   'port': backend_transport_port
               },
               'serializer': 'cbor'
           },
           'auth': {
               'cryptosign-proxy': {'type': 'static'}
           }
       }
       ```
     - Call `start_router_realm_rlink()` on this router
     - Rlink connects to other router's backend transport
     - Authentication via cryptosign-proxy (pubkey authentication)
     - Join realm with role 'rlink'

3. **Result**: This router now has rlinks to all other routers

### Bidirectional Connections

If we have Router A and Router B:
- A creates rlink to B: `rlink_workergroup_realm1_1` on Router A
- B creates rlink to A: `rlink_workergroup_userapps_1` on Router B

Both connections are needed because:
- A can call procedures registered on B
- B can call procedures registered on A
- Subscriptions propagate in both directions

## Validation

### How to Verify the Fix

1. **Check rlink creation logs**:
```bash
docker logs crossbar_master | grep "Rlink other node worker"
```
Should see connections to **all** routers, not just other worker groups.

2. **Check rlink status on router**:
```bash
# Via WAMP management API
crossbarfx shell show rlinks --realm myappreaim
```

3. **Count rlinks per router**:
For N routers, each should have N-1 rlinks:
- 2 routers → 1 rlink each
- 3 routers → 2 rlinks each
- 4 routers → 3 rlinks each

### Testing Different Topologies

**Test 1: Single Worker Group, Multiple Nodes**
```yaml
router_cluster:
  worker_groups:
    - name: workergroup_userapps
      placements:
        - node: router_node_1
          worker: workergroup_userapps_1
        - node: router_node_2
          worker: workergroup_userapps_2
```
Expected: 1 bidirectional rlink (2 total rlink objects)

**Test 2: Multiple Worker Groups**
```yaml
router_cluster:
  worker_groups:
    - name: workergroup_userapps
      placements:
        - node: router_node_1
    - name: workergroup_realm1
      placements:
        - node: router_node_2
```
Expected: 1 bidirectional rlink (works even with old code)

**Test 3: Mixed Topology**
```yaml
router_cluster:
  worker_groups:
    - name: workergroup_userapps
      placements:
        - node: router_node_1
        - node: router_node_2
    - name: workergroup_realm1
      placements:
        - node: router_node_3
```
Expected: 3 routers → 6 total rlinks (each router has 2 rlinks)

## Performance & Scaling

### Connection Overhead

**N routers** in cluster:
- Total rlinks: N × (N-1) bidirectional connections
- Each rlink: 1 TCP connection + 1 WAMP session
- Overhead: O(N²) connections

**Example:**
- 3 routers: 6 rlinks total
- 5 routers: 20 rlinks total  
- 10 routers: 90 rlinks total

### Practical Limits

For most deployments:
- **Small** (2-5 routers): Negligible overhead
- **Medium** (5-10 routers): Acceptable overhead
- **Large** (10+ routers): Consider hierarchical routing or sharding

### Connection Reuse

- **Backend transports are shared**: One TCP listener per router accepts all incoming rlinks
- **CBOR serialization**: Efficient binary protocol
- **Persistent connections**: Rlinks stay connected (not per-message)

## Debugging Tips

### Check if rlink exists
```python
# Via WAMP
rlinks = yield session.call('crossbar.router.get_router_realm_rlinks', 
                            realm_name)
```

### Monitor rlink health
```bash
docker logs crossbar_router_userapps | grep rlink
```

### Verify mesh completeness
```python
# Each router should have (N-1) rlinks
num_routers = len(placements)
expected_rlinks_per_router = num_routers - 1

actual_rlinks = len(yield session.call('get_router_realm_rlinks', realm))
assert actual_rlinks == expected_rlinks_per_router
```

## Related Documentation

- See `fix-dynamic-principal-updates.md` for how principals are managed
- WAMP router clustering: https://crossbar.io/docs/Router-Clustering/
- Rlink configuration: `crossbar/router/rlink.py`
- Router realm management: `crossbar/worker/router.py`
