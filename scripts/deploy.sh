#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load variables
cd "$PROJECT_ROOT/infra"

PROJECT_ID=$(terraform output -raw 2>/dev/null || true)
if [ -z "$PROJECT_ID" ]; then
  if [ -f terraform.tfvars ]; then
    PROJECT_ID=$(grep 'project_id' terraform.tfvars | cut -d'"' -f2)
  else
    echo "Error: Set project_id in infra/terraform.tfvars"
    exit 1
  fi
fi

REGION=$(grep 'region' terraform.tfvars 2>/dev/null | cut -d'"' -f2 || echo "us-central1")

echo "==> Building and pushing Docker image..."
"$SCRIPT_DIR/build-and-push.sh"

echo "==> Running terraform apply..."
cd "$PROJECT_ROOT/infra"
terraform init -input=false
terraform apply -auto-approve

SERVICE_URL=$(terraform output -raw service_url)
WEBHOOK_URL=$(terraform output -raw webhook_url)

echo ""
echo "==> Deployment complete!"
echo "    Service URL:  $SERVICE_URL"
echo "    Webhook URL:  $WEBHOOK_URL"
echo ""
echo "==> Next steps:"
echo "    1. Set WEBHOOK_BASE_URL=$SERVICE_URL in Cloud Run env and redeploy"
echo "    2. Open $SERVICE_URL in your phone browser"
