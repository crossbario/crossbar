# Bug Fix: Caller Disconnect Causing Callee Exception

## Problem Description

When a WAMP client (caller) calls a remote procedure and exits/disconnects before the call returns, the callee receives an exception and may also exit. This should not happen - the callee should be able to complete the procedure execution normally, and the router should simply discard the result since the caller is no longer available.

## Root Cause

The bug is in `/crossbar/router/dealer.py` in the `detach()` method (lines 185-247).

When a caller disconnects during an in-flight invocation:

1. The router checks if the callee supports call canceling (`call_canceling` feature)
2. **If the callee does NOT support call canceling:**
   - **OLD BEHAVIOR (BUG)**: The code just does `continue` (line 204) without cleaning up
   - This leaves the invocation tracked in internal data structures:
     - `_invocations`
     - `_callee_to_invocations`
     - `_invocations_by_call`
   - When the callee later returns a result via `processYield()` or `processInvocationError()`, it finds the invocation_request still exists
   - The code tries to send to `invocation_request.caller._transport` which is now `None`
   - This causes an error that propagates to the callee

3. **If the callee DOES support call canceling:**
   - The code properly cleans up the invocation tracking
   - Sends an INTERRUPT message to the callee
   - Everything works correctly

## The Fix

The fix changes the logic to **always clean up the invocation tracking**, regardless of whether the callee supports call canceling or not. The difference is only whether an INTERRUPT message is sent:

```python
# OLD CODE (BUGGY):
if not callee_supports_canceling:
    log("INTERRUPT not supported")
    continue  # <-- BUG: Skip cleanup!

# Clean up tracking (only executed if callee supports canceling)
cleanup_invocation_tracking()
send_interrupt()
```

```python
# NEW CODE (FIXED):
# Always clean up the invocation tracking
cleanup_invocation_tracking()

# Only send INTERRUPT if callee supports it
if callee_supports_canceling:
    log("INTERRUPTing in-flight INVOKE")
    send_interrupt()
else:
    log("INTERRUPT not supported - invocation cleaned up but not interrupted")
```

## Changed Code

**File**: `/crossbar/router/dealer.py`  
**Method**: `Dealer.detach()`  
**Lines**: 192-229

### Before (buggy):
```python
outstanding = self._caller_to_invocations.get(session, [])
for invoke in outstanding:
    if invoke.canceled:
        continue
    if invoke.callee is invoke.caller:
        continue
    callee = invoke.callee
    
    # BUG: If callee doesn't support canceling, skip cleanup entirely
    if not callee_supports_call_canceling(callee):
        self.log.debug("INTERRUPT not supported...")
        continue  # <-- SKIPS CLEANUP!
    
    # Cleanup only happens if we get past the continue
    cleanup_invocation()
    send_interrupt()
```

### After (fixed):
```python
outstanding = self._caller_to_invocations.get(session, [])
for invoke in outstanding:
    if invoke.canceled:
        continue
    if invoke.callee is invoke.caller:
        continue
    callee = invoke.callee
    
    # ALWAYS clean up invocation tracking
    if invoke.timeout_call:
        invoke.timeout_call.cancel()
        invoke.timeout_call = None

    invokes = self._callee_to_invocations[callee]
    invokes.remove(invoke)
    if not invokes:
        del self._callee_to_invocations[callee]

    del self._invocations[invoke.id]
    del self._invocations_by_call[(invoke.caller_session_id, invoke.call.request)]
    
    # ONLY send INTERRUPT if callee supports it
    if callee_supports_call_canceling(callee):
        self.log.debug("INTERRUPTing in-flight INVOKE...")
        self._router.send(invoke.callee, message.Interrupt(...))
    else:
        self.log.debug("INTERRUPT not supported - invocation cleaned up but not interrupted")
```

## Impact

### What Changes:
- **Callee behavior when caller disconnects without call_canceling support:**
  - **BEFORE**: Invocation stays tracked, callee gets exception when returning result
  - **AFTER**: Invocation is cleaned up silently, callee can complete normally, result is discarded

### What Stays the Same:
- Callees that support `call_canceling` still receive INTERRUPT messages as before
- All other WAMP routing behavior unchanged
- Backward compatible with existing deployments

## Testing

Existing test coverage:
- `test_caller_detach_interrupt_cancel_not_supported` - Tests that no INTERRUPT is sent when callee doesn't support canceling
- `test_caller_detach_interrupt_cancel_supported` - Tests that INTERRUPT is sent when callee supports canceling

The fix preserves the behavior verified by these tests while fixing the cleanup issue.

## Recommendation

This is a critical bug fix that prevents callee crashes when callers disconnect. It should be:
1. Applied to the current development branch
2. Backported to any maintained release branches
3. Included in the next patch release

## Technical Details

### Data Structures Involved:
- `_caller_to_invocations[session]` - Maps caller session to list of in-flight invocations
- `_callee_to_invocations[session]` - Maps callee session to list of in-flight invocations
- `_invocations[invocation_id]` - Maps invocation ID to InvocationRequest
- `_invocations_by_call[(caller_session_id, call_request_id)]` - Maps call request to invocation

### WAMP Protocol Compliance:
According to the WAMP specification, when a caller disconnects during an RPC:
- If the callee supports call canceling, it should receive an INTERRUPT
- If the callee doesn't support call canceling, it continues execution normally
- In both cases, any result from the callee should be discarded by the router

The old code violated this by leaving stale invocation tracking that would cause errors when the callee tried to return a result.
