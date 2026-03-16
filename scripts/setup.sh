#!/usr/bin/env bash
# First-time GCP project setup: enables APIs, builds image, provisions infra, sets webhook.
# Usage: ./scripts/setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a; source "$PROJECT_ROOT/.env"; set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-molthome}"
REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="ai-doorbell"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/ai-doorbell"
IMAGE="${REGISTRY}/backend:latest"

echo "==> Setting up GCP project: $PROJECT_ID ($REGION)"

# 1. Set active project
gcloud config set project "$PROJECT_ID"

# 2. Enable required APIs
echo "==> Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com \
  --quiet

# 3. Create Terraform state bucket (if not exists)
TFSTATE_BUCKET="ai-doorbell-tfstate"
if ! gcloud storage buckets describe "gs://$TFSTATE_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
  echo "==> Creating Terraform state bucket..."
  gcloud storage buckets create "gs://$TFSTATE_BUCKET" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --quiet
  gcloud storage buckets update "gs://$TFSTATE_BUCKET" \
    --versioning --quiet
else
  echo "==> Terraform state bucket already exists"
fi

# 4. Generate terraform.tfvars from .env
TFVARS="$PROJECT_ROOT/infra/terraform.tfvars"
echo "==> Generating $TFVARS from .env..."
cat > "$TFVARS" <<EOF
project_id            = "$PROJECT_ID"
region                = "$REGION"
gemini_api_key        = "$GEMINI_API_KEY"
telegram_bot_token    = "$TELEGRAM_BOT_TOKEN"
telegram_chat_id      = "$TELEGRAM_CHAT_ID"
google_client_id      = "$GOOGLE_CLIENT_ID"
google_client_secret  = "$GOOGLE_CLIENT_SECRET"
google_refresh_token  = "$GOOGLE_REFRESH_TOKEN"
owner_name            = "${OWNER_NAME:-Kyuhee}"
language              = "${LANGUAGE:-en}"
delivery_instructions = "${DELIVERY_INSTRUCTIONS:-Please leave it at the door}"
EOF

# 5. Build & push Docker image (must exist before Cloud Run creation)
echo "==> Configuring Docker for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Create Artifact Registry if not exists (terraform may not have run yet)
if ! gcloud artifacts repositories describe ai-doorbell --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  echo "==> Creating Artifact Registry..."
  gcloud artifacts repositories create ai-doorbell \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --quiet
fi

echo "==> Building Docker image..."
cd "$PROJECT_ROOT"
docker build --platform linux/amd64 -t "$IMAGE" .

echo "==> Pushing to Artifact Registry..."
docker push "$IMAGE"

# 6. Terraform init
echo "==> Initializing Terraform..."
cd "$PROJECT_ROOT/infra"
terraform init -input=false

# 7. Import pre-existing secrets (ignore errors if already in state or don't exist)
echo "==> Importing pre-existing resources..."
for SECRET in gemini-api-key telegram-bot-token google-client-id google-client-secret google-refresh-token; do
  terraform import "google_secret_manager_secret.$(echo $SECRET | tr '-' '_')" \
    "projects/$PROJECT_ID/secrets/$SECRET" 2>/dev/null || true
done

# 8. Terraform apply
echo "==> Provisioning infrastructure with Terraform..."
terraform apply -auto-approve

# 9. Get service URL and set Telegram webhook
SERVICE_URL=$(terraform output -raw service_url)

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "==> Setting Telegram webhook..."
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${SERVICE_URL}/api/telegram/webhook\", \"allowed_updates\": [\"callback_query\", \"message\"]}" | python3 -m json.tool
fi

echo ""
echo "========================================="
echo "  AI Doorbell deployed!"
echo "  URL: $SERVICE_URL"
echo "========================================="
