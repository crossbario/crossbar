# Crossbar.io Docker Image

✅ **Working** - Successfully built Docker image for Crossbar.io v23.1.2

## Quick Start

### Build the Image

```bash
./build-docker.sh
# Or explicitly:
# docker build -f Dockerfile.working -t crossbar:latest .
```

### Test the Image

```bash
# Check version
docker run --rm crossbar:latest python3 -c "import crossbar; print('Crossbar:', crossbar.__version__)"
# Output: Crossbar: 23.1.2

# Run Crossbar router
docker run -p 8080:8080 crossbar:latest
```

## Image Details

- **Base**: python:3.11-slim-bookworm
- **Version**: Crossbar.io 23.1.2
- **Size**: ~2.1 GB
- **Includes**: Autobahn (master), Web3, XBR (21.2.1+)

## Available Dockerfiles

1. **Dockerfile.working** - ✅ Working version (RECOMMENDED)
2. **Dockerfile.production** - Multi-stage build (experimental)
3. **Dockerfile.simple** - Single-stage build (experimental)
4. **Dockerfile** - Development image (original)

See [DOCKER-TROUBLESHOOTING.md](DOCKER-TROUBLESHOOTING.md) for detailed build process and dependency information.

## Usage

### Default Configuration

```bash
docker run -p 8080:8080 crossbar:latest
```

### Custom Configuration

```bash
# Mount your config directory
docker run -p 8080:8080 -v /path/to/.crossbar:/opt/crossbar/.crossbar crossbar:latest
```

## Known Limitations

- Image size is large (~2.1GB) due to complete XBR/blockchain dependencies
- `crossbar version` command requires XBR, use Python import to check version instead
- web3.py may show pkg_resources deprecation warning (harmless)

## References

- [Crossbar.io Documentation](https://crossbar.io/docs/)
- [Build Troubleshooting](DOCKER-TROUBLESHOOTING.md)
- [WAMP Protocol](https://wamp-proto.org/)

## Quick Start

### Build the Image

```bash
# Build the latest version
./build-docker.sh

# Or build manually
docker build -f Dockerfile.simple -t crossbar:latest .
```

### Run the Container

```bash
# Simple run with default configuration
docker run -p 8080:8080 crossbar:latest

# Run with custom configuration
docker run -p 8080:8080 -v $(pwd)/examples:/opt/crossbar/.crossbar:ro crossbar:latest

# Run with Docker Compose
docker-compose -f docker-compose.production.yml up
```

## Configuration

The container expects a Crossbar.io configuration file at `/opt/crossbar/.crossbar/config.json`.

### Example Configuration

See `examples/config.json` for a basic configuration that:
- Sets up a router worker
- Creates a realm named "realm1" 
- Configures WebSocket transport on port 8080
- Allows anonymous access with full permissions

### Custom Configuration

Mount your configuration directory:

```bash
docker run -p 8080:8080 \
  -v /path/to/your/.crossbar:/opt/crossbar/.crossbar:ro \
  crossbar:latest
```

## Environment Variables

- `CROSSBAR_DIR` - Path to configuration directory (default: `/opt/crossbar/.crossbar`)

## Exposed Ports

- `8080` - Default WebSocket transport
- `8443` - Default secure WebSocket transport (if configured)

## Docker Compose

Use the provided `docker-compose.production.yml` for easy deployment:

```bash
# Start the service
docker-compose -f docker-compose.production.yml up -d

# View logs
docker-compose -f docker-compose.production.yml logs -f

# Stop the service
docker-compose -f docker-compose.production.yml down
```

## Publishing to Registry

```bash
# Tag for your registry
docker tag crossbar:23.1.2 your-registry.com/crossbar:23.1.2
docker tag crossbar:23.1.2 your-registry.com/crossbar:latest

# Push to registry
docker push your-registry.com/crossbar:23.1.2
docker push your-registry.com/crossbar:latest
```

## Health Check

The container includes a health check that runs `crossbar version` every 30 seconds.

## Troubleshooting

### Check if Crossbar.io is working
```bash
docker run --rm crossbar:latest crossbar version
```

### Debug inside container
```bash
docker run -it --entrypoint /bin/bash crossbar:latest
```

### View logs
```bash
docker logs <container-id>
```

## Security Notes

- The container runs as a non-root user (`crossbar`)
- Only necessary system packages are installed
- Use read-only mounts for configuration when possible