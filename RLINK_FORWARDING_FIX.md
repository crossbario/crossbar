# Router Link (rlink) Bidirectional Forwarding Fix

## Problem

When clients connect to different router workers in a router cluster, they experience intermittent `wamp.error.no_such_procedure` errors when calling procedures, even though the procedures ARE registered - just on a different router worker.

### Scenario
- Client A connects to Router Worker 1
- Client B connects to Router Worker 2  
- Service registers procedure `com.example.myproc` on Router Worker 1
- Client B tries to call `com.example.myproc` → **ERROR: wamp.error.no_such_procedure**

This affects ALL procedures, not just dynamic authenticators:
- Custom RPC endpoints
- Authentication procedures (e.g., `wamp.authenticate.ticket`)
- Any service that registers procedures

## Root Cause

Router links (rlinks) between router workers were configured with **unidirectional forwarding**:

```python
'forward_local_invocations': True,   # Local client → Remote procedure ✅
'forward_remote_invocations': False, # Remote client → Local procedure ❌
'forward_local_events': True,        # Local client → Remote subscription ✅
'forward_remote_events': False,      # Remote client → Local subscription ❌
```

This configuration only allows **one direction** of routing:
- Router A's clients CAN call procedures on Router B
- Router B's clients CANNOT call procedures on Router A

For a fully meshed router cluster, **both directions must be enabled**.

## Solution

Changed rlink configuration in `crossbar/master/arealm/arealm.py` (lines ~1128-1139) to enable **bidirectional forwarding**:

```python
'forward_local_invocations': True,   # Local client → Remote procedure ✅
'forward_remote_invocations': True,  # Remote client → Local procedure ✅
'forward_local_events': True,        # Local client → Remote subscription ✅
'forward_remote_events': True,       # Remote client → Local subscription ✅
```

### What This Fixes

1. ✅ **Procedures**: Clients on ANY router can call procedures registered on ANY other router
2. ✅ **Subscriptions**: Clients on ANY router receive events published on ANY other router
3. ✅ **Dynamic Authenticators**: Authentication services work regardless of which router handles the connection
4. ✅ **Service Discovery**: The cluster behaves as a single logical router

## Impact

### Before Fix
```
Router Worker 1:
  - Client A connects
  - Service registers com.example.proc
  - Client A calls com.example.proc → ✅ Works
  
Router Worker 2:
  - Client B connects
  - Client B calls com.example.proc → ❌ wamp.error.no_such_procedure
```

### After Fix
```
Router Worker 1:
  - Client A connects
  - Service registers com.example.proc
  - Client A calls com.example.proc → ✅ Works
  
Router Worker 2:
  - Client B connects  
  - Client B calls com.example.proc → ✅ Works (forwarded via rlink)
```

## Why Was It Disabled?

The unidirectional configuration was likely intended for:
- **Hub-and-spoke topologies**: Edge routers forward to central router but not vice versa
- **Specialized routing scenarios**: Where you want asymmetric call routing
- **Performance optimization**: Reducing unnecessary routing overhead in specific setups

However, for a **general-purpose router cluster** where clients should be able to reach any service regardless of which router they connect to, bidirectional forwarding is essential.

## Testing

After this fix, verify:

1. Register a procedure on Router Worker 1
2. Connect client to Router Worker 2
3. Call the procedure → Should succeed

For authentication:
1. Authentication service registers on Router Worker 1
2. Client connects to Router Worker 2 via proxy
3. Client authenticates → Should succeed consistently

## Related Files

- `crossbar/master/arealm/arealm.py` - rlink configuration
- `crossbar/router/router.py` - Router invocation forwarding logic
- `crossbar/worker/rlink.py` - Router link implementation

## Configuration Options

Rlink forwarding options:
- `forward_local_invocations`: Forward calls from local clients to remote procedures
- `forward_remote_invocations`: Forward calls from remote clients to local procedures  
- `forward_local_events`: Forward publishes from local clients to remote subscribers
- `forward_remote_events`: Forward publishes from remote clients to local subscribers

For a fully meshed cluster, **all should be True**.

## Performance Considerations

Enabling bidirectional forwarding adds minimal overhead:
- Calls are only forwarded when the procedure is not locally registered
- Router maintains registration mappings to avoid unnecessary forwarding
- Serialization/deserialization happens once regardless of direction

The benefits (consistent behavior, no missing procedures) far outweigh the minimal performance cost.
