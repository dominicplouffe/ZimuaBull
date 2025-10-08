#!/bin/bash

# Docker Build, Tag, and Push Script
# Usage: ./docker-push.sh <dockerhub-username> <version>
# Example: ./docker-push.sh myusername v1.0.0

set -e  # Exit on error

# Check if required arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Error: Missing required arguments"
    echo "Usage: $0 <dockerhub-username> <version>"
    echo "Example: $0 myusername v1.0.0"
    exit 1
fi

USERNAME=$1
VERSION=$2
IMAGE_NAME="zimuabull"

echo "========================================="
echo "Docker Build, Tag & Push"
echo "========================================="
echo "Username: $USERNAME"
echo "Version: $VERSION"
echo "Image: $IMAGE_NAME"
echo "========================================="
echo ""

# Step 1: Build the Docker image
echo "Step 1: Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .
echo "✓ Build complete"
echo ""

# Step 2: Tag with version
echo "Step 2: Tagging with version..."
docker tag ${IMAGE_NAME}:latest ${IMAGE_NAME}:${VERSION}
echo "✓ Tagged as ${IMAGE_NAME}:${VERSION}"
echo ""

# Step 3: Tag for Docker Hub with latest
echo "Step 3: Tagging for Docker Hub (latest)..."
docker tag ${IMAGE_NAME}:latest ${USERNAME}/${IMAGE_NAME}:latest
echo "✓ Tagged as ${USERNAME}/${IMAGE_NAME}:latest"
echo ""

# Step 4: Tag for Docker Hub with version
echo "Step 4: Tagging for Docker Hub (${VERSION})..."
docker tag ${IMAGE_NAME}:latest ${USERNAME}/${IMAGE_NAME}:${VERSION}
echo "✓ Tagged as ${USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""

# Step 5: Push latest to Docker Hub
echo "Step 5: Pushing to Docker Hub (latest)..."
docker push ${USERNAME}/${IMAGE_NAME}:latest
echo "✓ Pushed ${USERNAME}/${IMAGE_NAME}:latest"
echo ""

# Step 6: Push version to Docker Hub
echo "Step 6: Pushing to Docker Hub (${VERSION})..."
docker push ${USERNAME}/${IMAGE_NAME}:${VERSION}
echo "✓ Pushed ${USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""

echo "========================================="
echo "✓ All done!"
echo "========================================="
echo "Images pushed:"
echo "  - ${USERNAME}/${IMAGE_NAME}:latest"
echo "  - ${USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "========================================="
