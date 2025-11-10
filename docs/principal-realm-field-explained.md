# Why realm='proxy' Instead of realm=None

## Summary

When implementing dynamic principal updates for backend transport authentication, we discovered that using `realm=None` caused connection failures, while `realm='proxy'` works correctly.

## The Issue

Initial implementation used `realm=None` for proxy service session principals:

```python
desired_principals[wc_node.authid] = {
    'realm': None,  # ❌ This caused connection failures
    'role': 'system',
    'authorized_keys': [wc_node.pubkey],
}
```

**Result**: Proxy backend connections failed with "Connection refused" errors after the transport was restarted with updated principals.

## The Solution

Use `realm='proxy'` as a placeholder string instead:

```python
desired_principals[wc_node.authid] = {
    'realm': 'proxy',  # ✅ This works correctly
    'role': 'proxy',
    'authorized_keys': [wc_node.pubkey],
}
```

**Result**: All connections work correctly after transport restart.

## Why This Matters

While the `realm` and `role` fields in principals are **completely ignored** for cryptosign-proxy authentication (replaced by forwarded credentials), the system still requires valid string values in these fields.

### Root Cause

The connection configuration infrastructure expects string values for realm/role fields and may use them for:
1. Internal routing logic
2. Connection identification/logging
3. Configuration validation
4. State tracking

Using `None` likely caused issues in one of these areas, even though the authentication layer itself ignores these values.

## Current Principal Structure

### Router Rlink Principals
```python
{
    'authid': 'router_realm1',
    'realm': 'realm1',           # Actual realm name - used for realm-specific routing
    'role': 'rlink',             # Standard rlink role
    'authorized_keys': [all_router_pubkeys]  # Mutual authentication
}
```

### Proxy Service Session Principals
```python
{
    'authid': 'proxy1',
    'realm': 'proxy',            # Placeholder - distinguishes from rlink principals
    'role': 'proxy',             # Placeholder - ignored by cryptosign-proxy
    'authorized_keys': [proxy_node_pubkey]  # Individual authentication
}
```

## Authentication Flow

For **cryptosign-proxy** (used by proxy service sessions):

1. Transport authenticates based on **pubkey only** from the principal
2. The `realm` and `role` from the principal are **completely ignored**
3. Actual realm/role are extracted from forwarded credentials in `authextra`:
   ```python
   {
       'proxy_realm': 'realm1',      # From frontend session
       'proxy_authid': 'system',     # From frontend session
       'proxy_authrole': 'system',   # From frontend session
       'pubkey': '82836861...'       # From proxy node
   }
   ```

4. `PendingAuthCryptosignProxy.hello()` replaces the principal's realm/role with these forwarded values

## Key Insights

1. **Transport-level vs Realm-level**: The backend transport serves ALL realms on a worker
2. **Principal Distinction**: Using `realm='proxy'` distinguishes proxy principals from rlink principals
3. **String Requirements**: System infrastructure requires non-None string values even when ignored
4. **No Conflicts**: Multiple realms can share the same worker without principal conflicts because:
   - Rlinks use specific realm names (realm-specific connections)
   - Proxies use 'proxy' placeholder (transport-level connections)

## Lesson Learned

When dealing with configuration fields that are "ignored" by a specific authentication method, they may still be required by other parts of the system infrastructure. Always use valid placeholder values rather than `None` unless explicitly documented that `None` is supported.

## References

- **Code**: `crossbar/master/arealm/arealm.py::_update_transport_principals()`
- **Authentication**: `crossbar/router/auth/cryptosign.py::PendingAuthCryptosignProxy`
- **Documentation**: `docs/fix-dynamic-principal-updates.md`
