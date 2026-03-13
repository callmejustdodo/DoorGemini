#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Destroying all Terraform-managed resources..."
cd "$PROJECT_ROOT/infra"
terraform destroy -auto-approve

echo "==> All resources destroyed."
