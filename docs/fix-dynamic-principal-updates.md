# Dynamic Principal Updates Fix

## Problem Overview

### Issue
Router backend transports were configured with cryptosign-proxy authentication requiring principals (authorized nodes), but when new proxy or router nodes came online after initial deployment, they were not added to the transport's principal list. This caused authentication failures when these new nodes tried to connect.

**Error symptom:**
```
wamp.error.not_authorized: no principal with authid 'proxy2' exists
```

### Root Causes

1. **Static Principal Configuration**: Principals were only set when the transport was initially created during `_apply_routercluster_placements`. If new nodes came online later, they were never added.

2. **Transport Retrieval Bug**: When checking current principals, the code was looking at `transport.get('auth')` instead of `transport.get('config', {}).get('auth')`, causing it to always see empty principals and attempt restart every 10 seconds.

3. **No Update Mechanism**: The authentication system (`PendingAuthCryptosign`) loads and caches principals at initialization time with no API for runtime updates.

## Solution Architecture

### Dynamic Principal Updates

Added `_update_transport_principals()` method to `ApplicationRealmMonitor` that:

1. **Runs on every monitor iteration** (~10 seconds) after router placements are applied
2. **Queries all nodes** from the global database (both router and webcluster nodes)
3. **Builds desired principals list**:
   - Router nodes: All routers get mutual authentication (all router pubkeys in authorized_keys)
   - Webcluster/proxy nodes: Each gets individual authentication (own pubkey only)
4. **Compares with current principals** using normalized comparison (sorted authorized_keys)
5. **Restarts transport if changed** to apply updated principals

### Key Implementation Details

#### Principal Structure

For **router nodes** (rlink connections):
```python
{
    'authid': 'router_name',
    'realm': 'arealm.name',        # Realm-specific for rlinks
    'role': 'rlink',
    'authorized_keys': [pubkey1, pubkey2, pubkey3, ...]  # All router pubkeys
}
```

For **webcluster/proxy nodes** (service sessions):
```python
{
    'authid': 'proxy_name', 
    'realm': 'proxy',             # Transport-level placeholder, serves all realms
    'role': 'proxy',              # Ignored for cryptosign-proxy auth
    'authorized_keys': [pubkey]   # Only this node's pubkey
}
```

**IMPORTANT**: The backend transport is **shared across ALL realms** on a worker. Different types of
principals are used to distinguish connection purposes:
- Router rlinks use `realm=<arealm.name>` (realm-specific routing)
- Proxy service sessions use `realm='proxy'` (transport-level placeholder)

**Note**: For cryptosign-proxy authentication (used by proxy service sessions), the `realm` and `role` 
in the principal are completely ignored and replaced by the forwarded client credentials from 
`authextra`. The pubkey is all that matters for authentication at the transport layer.

#### Normalized Comparison

To avoid unnecessary restarts due to list ordering differences:

```python
def normalize_principals(principals_dict):
    """Normalize principals for comparison by sorting authorized_keys lists."""
    normalized = {}
    for authid, principal in principals_dict.items():
        normalized[authid] = {
            'realm': principal.get('realm'),
            'role': principal.get('role'),
            'authorized_keys': sorted(principal.get('authorized_keys', []))
        }
    return normalized

# Compare normalized versions
current_normalized = normalize_principals(current_principals)
desired_normalized = normalize_principals(desired_principals)
principals_changed = current_normalized != desired_normalized
```

#### Transport Restart with Timeouts

Since there's no dynamic update API, we must restart the transport:

```python
# Stop transport with 10-second timeout
stop_d = session.call('stop_router_transport', node_oid, worker_name, transport_id)
stop_d.addTimeout(10, _reactor)
try:
    yield stop_d
except TimeoutError:
    log.warn('Timeout stopping - may already be stopped')

# Start transport with updated config and 30-second timeout  
start_d = session.call('start_router_transport', 
                       node_oid, worker_name, transport_id, updated_config)
start_d.addTimeout(30, _reactor)
yield start_d
```

#### Enhanced Logging

Tracks three categories of principal changes:

```python
new_authids = set(desired) - set(current)           # New nodes added
removed_authids = set(current) - set(desired)       # Nodes removed
modified_authids = {authid for authid in (set(current) & set(desired))
                    if current_normalized[authid] != desired_normalized[authid]}
```

Logs example:
```
Updating transport tnp_workergroup_userapps_1 principals: 
  current=2, desired=4, adding=2, removing=0, modifying=2
New principals to add: ['proxy1', 'proxy2']
Principals to modify (authorized_keys changed): ['router_realm1', 'router_userapps']
Successfully restarted transport tnp_workergroup_userapps_1 with updated principals
```

## Files Modified

### `/Users/marko/git/crossbar/crossbar/master/arealm/arealm.py`

**Line 29**: Added imports
```python
from twisted.internet import reactor as _reactor
from twisted.internet.defer import inlineCallbacks, returnValue, TimeoutError
```

**Lines 207-219**: Modified `_check_and_apply()` to call principal update
```python
# Apply router cluster placements
yield self._apply_routercluster_placements(arealm, ...)

# Update transport principals (add new nodes dynamically)
if arealm.webcluster_oid:
    yield self._update_transport_principals(arealm, ...)

# Apply webcluster connections
yield self._apply_webcluster_connections(arealm, ...)
```

**Lines 674-900**: New `_update_transport_principals()` method
- Queries all nodes from global DB
- Queries all router placements from placement DB
- Builds desired principals for routers and webcluster nodes
- Extracts current principals correctly from `transport['config']['auth']`
- Performs normalized comparison
- Restarts transport with timeouts if principals changed
- Handles ApplicationError for not-yet-created transports

## Architectural Notes

### Why Transport Restart is Required

The cryptosign authentication system in Crossbar:

1. **Principals loaded at initialization**: `PendingAuthCryptosign.__init__()` loads principals from config and caches them in instance variables
2. **No hotload API**: There is no WAMP procedure or mechanism to update principals on a running authenticator
3. **Authenticator lifecycle**: The authenticator is created when the transport starts and destroyed when it stops

Therefore, the **only way** to update principals is:
```
stop_transport → destroy authenticator → start_transport → create new authenticator with new principals
```

### Transport Structure

- **One transport per router worker**: Named `tnp_{worker_name}`
- **Shared across all realms**: Same transport handles connections to all realms on that worker
- **TCP rawsocket**: Port auto-assigned from range [10000, 10100]
- **CBOR serializer**: Used for efficient binary serialization
- **Authentication**: cryptosign-proxy with static principals

### Two-Layer Authentication Model

1. **Transport Layer** (cryptosign-proxy):
   - Validates the connecting node's public key
   - Proves the node is a trusted member of the cluster
   - The principal's `realm` and `role` are **ignored** for cryptosign-proxy

2. **Session Layer** (forwarded credentials):
   - Actual realm, authid, and authrole come from `details.authextra`
   - Forwarded from the proxy's frontend connection
   - This is the client's real identity, not the proxy's

## Performance Impact

### Minimal Overhead
- Check runs every ~10 seconds (part of existing monitor iteration)
- Database queries are lightweight (indexed lookups)
- Only restarts when principals actually change (once per new node)
- Normalized comparison prevents spurious restarts

### Brief Disruption During Restart
When a transport is restarted:
- Existing connections are dropped
- Clients reconnect automatically (WAMP auto-reconnect)
- Downtime: ~1-2 seconds during restart
- Frequency: Only when new nodes are added (rare event)

## Future Improvements

### Potential Non-Disruptive Updates (Not Implemented)

Would require significant authentication system refactoring:

```python
# Hypothetical hotload API (doesn't exist)
@wamp.register(None)
def update_transport_principals(self, transport_id, principals):
    """Update principals without restarting transport."""
    transport = self.transports[transport_id]
    authenticator = transport.authenticator
    
    # Thread-safe update of cached principals
    with authenticator._lock:
        authenticator._config['principals'] = principals
        authenticator._pubkey_to_authid = {
            p['authorized_keys'][0]: authid 
            for authid, p in principals.items()
        }
```

**Why not implemented**:
- Requires thread-safety mechanisms (locks/atomics)
- Multiple caches would need updating (config, pubkey maps, etc.)
- Risk of inconsistent state during updates
- Current approach is proven and reliable

## Testing

### Verification Steps

1. **Check stable state** (no unnecessary restarts):
```bash
docker logs crossbar_master | grep "_update_transport_principals" | tail -20
```
Expected: Only updates when principals actually change

2. **Add a new node** and verify it gets added:
```bash
# After node comes online, check logs
docker logs crossbar_master | grep "New principals to add"
docker logs crossbar_master | grep "Successfully restarted transport"
```

3. **Verify no authentication errors**:
```bash
docker logs crossbar_master | grep "wamp.error.not_authorized"
```
Expected: No results after principals updated

4. **Check all monitors report success**:
```bash
docker logs crossbar_master | grep "check & apply run completed successfully" | tail -10
```

## Related Documentation

- See `fix-router-placement-rlink.md` for the router cluster placement fix
- Authentication system: `crossbar/router/auth/cryptosign.py`
- Transport management: `crossbar/worker/router.py`
- Proxy connections: `crossbar/worker/proxy.py`
