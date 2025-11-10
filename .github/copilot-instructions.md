# Crossbar.io AI Coding Instructions

## Project Overview
Crossbar.io is a decentralized WAMP (Web Application Messaging Protocol) router and application server. It implements real-time messaging patterns (PubSub, RPC) and serves as middleware for distributed/microservice applications.

## Architecture & Key Components

### Core Architecture
- **Node Controller** (`crossbar/node/controller.py`): Main process manager that spawns and manages workers
- **Workers**: Native processes that provide specific functionality:
  - **Router Workers** (`crossbar/worker/router.py`): Core WAMP routing (realms, transports, components)
  - **Proxy Workers** (`crossbar/worker/proxy.py`): Load balancing and connection proxying  
  - **Container Workers**: Host application components
- **Realms** (`crossbar/worker/types.py`): WAMP routing domains with roles/permissions
- **Transports** (`crossbar/worker/transport.py`): Network protocols (WebSocket, RawSocket, Web/HTTP)

### Configuration-Driven Design
All functionality is configured via JSON config files (`config.json`). The schema is in `crossbar.json`. Configuration drives:
- Worker creation and management
- Realm setup with authentication/authorization
- Transport endpoint configuration
- Component hosting and routing

### Worker Pattern
```python
# Workers inherit from WorkerController -> NativeProcess -> ApplicationSession
class RouterController(TransportController):
    WORKER_TYPE = 'router'
    # Registers WAMP procedures for dynamic management
    @wamp.register(None)
    def start_router_realm(self, realm_id, realm_config, details=None):
```

## Development Workflows

### Testing Strategy
- **Unit Tests**: Use Twisted Trial (`trial crossbar.router.test.test_authorize`)
- **Functional Tests**: pytest-based integration tests (`test/functests/`)
  - Run with: `pytest -sv test/functests/cbtests/`
  - Use `--slow` for long-running tests, `--keep` to preserve temp dirs
  - Tests spawn actual Crossbar processes and test end-to-end behavior
- **Management Tests**: Live testing with `test/management/` scripts

### Build & Install Commands
```bash
# Development install with pinned dependencies
make install

# Testing
make test           # Full test suite via tox
pytest -sv test/functests/cbtests/test_cb_proxy.py  # Specific functional test
trial crossbar.router.test.test_authorize           # Unit test

# Start node
crossbar start --cbdir=/path/to/.crossbar
```

### Key Files for Understanding
- `crossbar/__init__.py`: Entry point, monkey patches, CLI setup
- `crossbar/worker/router.py`: RouterController - main router logic
- `crossbar/router/router.py`: Core Router and RouterFactory classes
- `crossbar/interfaces.py`: Key interfaces (IPendingAuth, IRealmContainer)
- `crossbar/node/controller.py`: Node management and worker orchestration

## Project-Specific Patterns

### WAMP Procedure Registration
Controllers expose management APIs via WAMP decorators:
```python
@wamp.register(None)
def start_router_transport(self, transport_id, config, create_paths=False, details=None):
    # Management API for starting transports
```

### Monkey Patching Strategy
Heavy use of compatibility monkey patches in `__init__.py` for eth_abi, web3, etc. This maintains compatibility across Python/library versions.

### Session Factories and Authentication
- `RouterSessionFactory`: Creates WAMP sessions for realms
- Authentication flows through `IPendingAuth` interface
- Authorization via realm roles with URI-based permissions

### Error Handling Convention
Crossbar raises `ApplicationError` with specific error URIs:
```python
raise ApplicationError("crossbar.error.invalid_configuration", emsg)
```

### Configuration Validation
Uses `crossbar.common.checkconfig` module. Configuration is validated on startup and runtime changes.

## Critical Integration Points

### Worker Communication
- All workers connect to node controller via WAMP
- Management operations use WAMP RPC calls between controller and workers
- Event propagation for state changes (`.on_router_transport_started`)

### Transport Factory Creation
Complex factory pattern in `crossbar/worker/transport.py`:
- WebSocket: `WampWebSocketServerFactory`
- RawSocket: `WampRawSocketServerFactory` 
- Web: Creates Twisted Web resources with WAMP backing

### Twisted Integration
- Heavy use of `@inlineCallbacks` and `returnValue()`
- Reactor management for worker processes
- Deferred chains for async operations

## Testing Notes
- Functional tests require careful cleanup - single Crossbar instance shared across tests
- Use `start_crossbar()` helper from `test/functests/helpers.py`
- Tests must use `pytest.inlineCallbacks`, not Twisted's version
- Never import `twisted.internet.reactor` directly in tests

## Configuration Schema
Reference `crossbar.json` for full configuration schema. Key patterns:
- Workers array defines all processes
- Each worker has type-specific configuration
- Realms define WAMP routing domains
- Transports define network endpoints
- Components define hosted application code