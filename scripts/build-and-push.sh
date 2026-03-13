#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Read project_id and region from terraform.tfvars
TFVARS="$PROJECT_ROOT/infra/terraform.tfvars"
if [ ! -f "$TFVARS" ]; then
  echo "Error: $TFVARS not found. Copy from terraform.tfvars.example."
  exit 1
fi

PROJECT_ID=$(grep 'project_id' "$TFVARS" | cut -d'"' -f2)
REGION=$(grep 'region' "$TFVARS" | cut -d'"' -f2)
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/ai-doorbell"
IMAGE="${REGISTRY}/backend:latest"

echo "==> Configuring Docker for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Building Docker image..."
cd "$PROJECT_ROOT"
docker build -t "$IMAGE" .

echo "==> Pushing to Artifact Registry..."
docker push "$IMAGE"

echo "==> Image pushed: $IMAGE"
