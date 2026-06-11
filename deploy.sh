#!/bin/bash
# wfl-bot deploy script
# Kullanım: ./deploy.sh <dockerhub_kullanici_adi>
# Örnek:    ./deploy.sh lacixerd

set -e

DOCKER_USER="${1:?Kullanım: ./deploy.sh <dockerhub_kullanici_adi>}"
IMAGE_NAME="${DOCKER_USER}/wfl-bot:latest"

echo "🔨 Building image for linux/amd64 (Oracle Cloud)..."
docker build --platform linux/amd64 -t "$IMAGE_NAME" .

echo "📤 Pushing to Docker Hub..."
docker push "$IMAGE_NAME"

echo ""
echo "✅ Done! Image pushed: $IMAGE_NAME"
echo ""
echo "Sunucuda çalıştırmak için:"
echo "  DOCKER_IMAGE=$IMAGE_NAME docker compose pull"
echo "  DOCKER_IMAGE=$IMAGE_NAME docker compose up -d"
