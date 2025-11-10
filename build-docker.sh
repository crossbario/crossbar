#!/bin/bash
set -e

# Get Crossbar version
VERSION=$(python -c "exec(open('crossbar/_version.py').read()); print(__version__)")
echo "Building Crossbar.io Docker image version: $VERSION"

# Build the image
docker build -f Dockerfile.working -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:latest -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:$VERSION .

echo "Build complete!"
echo "Available images:"
docker images europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar

echo ""
echo "To test the container:"
echo "  docker run --rm europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:latest crossbar version"
echo ""
echo "To run the container:"
echo "  docker run -p 8080:8080 europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:latest"
echo ""
echo "Or use docker-compose:"
echo "  docker-compose -f docker-compose.production.yml up"
echo ""
echo "To push to a registry (replace with your registry):"
echo "  docker tag crossbar:$VERSION your-registry/crossbar:$VERSION"
echo "  docker push your-registry/crossbar:$VERSION"