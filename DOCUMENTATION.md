# Quantivly Custom Crossbar Fork Documentation

## Overview

This document outlines the modifications made to the crossbar.io framework for use in Quantivly's custom implementation. The main changes include:

1. Removal of Tor/Onion routing support
2. Security upgrades to dependencies
3. Custom Docker setup
4. Build process configuration

## Modifications

### 1. Removal of Tor/Onion Routing Support

The primary code change removes all Tor-related functionality from the Crossbar codebase:

- Removed `txtorcon` dependency from all requirements files (customers have expressed concerns about this dependency)
- Removed Tor endpoint handling code from `crossbar/common/twisted/endpoint.py`

### 2. Security Updates to Dependencies

Several dependencies were updated to address security vulnerabilities:

```
- certifi: 2020.6.20 → 2023.7.22
- cryptography: 2.9.2 → 3.2
- Pygments: 2.6.1 → 2.7.4
- PyYAML: 5.3.1 → 5.4.1
- setuptools: 47.3.1 → 70.0.0
```

### 3. Docker Configuration

A custom Docker setup using Python `3.8-slim` as the base image with:

- Appropriate system dependencies for Crossbar
- Created a dedicated `crossbar` user with UID 242
- Set up volume mounting for `/node` directory
- Exposed ports 8080 and 8000
- Configured the entrypoint to run Crossbar with the appropriate configuration directory

### 4. Build Process

- Created a `build.sh` script that builds the Docker image with appropriate build arguments
- Switched from using minimum requirements to pinned requirements (changed in `setup.py`)
- Added a `run-tests.sh` script for testing the Crossbar implementation

### 5. Additional Changes

- Modified vmprof dependency to work only on compatible architectures
- Switched from open-ended requirements to pinned requirements in setup.py

## Maintenance Guide

### How to Update the Fork

1. **Updating the base Crossbar version**:

   - Pull the latest changes from the upstream Crossbar repository
   - Reapply the patches (Tor removal and dependency updates)
   - Resolve any conflicts that arise

2. **Updating Security Dependencies**:

   - Review the requirements files periodically for security updates
   - Apply updates to `requirements-pinned.txt` as needed
   - Rebuild the Docker image

3. **Building a New Version**:
   - Update the version in `versions.sh` (referenced in `build.sh`)
   - Run `./build.sh` to create a new Docker image
   - Tag and push the new image to your container registry

### Testing Changes

1. Run the included test script:

   ```bash
   ./run-tests.sh
   ```

2. Test the Docker container locally:

   ```bash
   docker run -p 8080:8080 -p 8000:8000 quantivly/crossbar:[VERSION]
   ```

### Key Files

- `Dockerfile.quantivly-custom`: Docker configuration file
- `build.sh`: Script to build the Docker image
- `run-tests.sh`: Script to run tests
- Modified requirements files:
  - `requirements-min.txt`
  - `requirements-pinned.txt`
  - `requirements-latest.txt`
  - `requirements.txt`

## Notes on Specific Changes

1. **Tor/Onion Support Removal**:

   - All code between lines 441-503 and 611-630 in `crossbar/common/twisted/endpoint.py` was removed
   - These sections contained the implementation for Tor onion services

2. **Requirements Management**:

   - Changed from using minimum requirements to pinned requirements in `setup.py`
   - This provides more consistent builds by locking dependency versions

3. **Docker Security**:
   - Running as a non-root user (crossbar)
   - Using a specific UID (242) for better security and predictability

## Future Considerations

1. **Dependency Updates**:

   - Regularly review and update dependencies for security fixes
   - Consider using automated dependency scanning tools

2. **Upstream Changes**:

   - Monitor the upstream Crossbar repository for important fixes and features
   - Consider cherry-picking specific commits rather than merging whole releases

3. **Testing**:
   - Expand test coverage as needed for your specific use cases
   - Consider adding integration tests that validate your specific configuration
