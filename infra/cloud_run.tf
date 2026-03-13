resource "google_cloud_run_v2_service" "doorbell" {
  name     = "ai-doorbell"
  location = var.region

  depends_on = [google_project_service.apis]

  template {
    service_account = google_service_account.doorbell.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    session_affinity = true
    timeout          = "300s"

    max_instance_request_concurrency = 1

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/ai-doorbell/backend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # Plain env vars
      env {
        name  = "OWNER_NAME"
        value = var.owner_name
      }
      env {
        name  = "LANGUAGE"
        value = var.language
      }
      env {
        name  = "DELIVERY_INSTRUCTIONS"
        value = var.delivery_instructions
      }
      env {
        name  = "TELEGRAM_CHAT_ID"
        value = var.telegram_chat_id
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.screenshots.name
      }

      # Secrets from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "TELEGRAM_BOT_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.telegram_bot_token.secret_id
            version = "latest"
          }
        }
      }

      # Set WEBHOOK_BASE_URL dynamically — use the Cloud Run URL
      # This is set after first deploy; re-run terraform apply after initial deploy
      env {
        name  = "WEBHOOK_BASE_URL"
        value = ""
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access (public doorbell frontend)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.doorbell.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
