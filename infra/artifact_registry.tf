resource "google_artifact_registry_repository" "doorbell" {
  location      = var.region
  repository_id = "ai-doorbell"
  format        = "DOCKER"
  description   = "AI Doorbell Docker images"

  depends_on = [google_project_service.apis]
}
