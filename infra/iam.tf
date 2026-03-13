resource "google_service_account" "doorbell" {
  account_id   = "ai-doorbell-sa"
  display_name = "AI Doorbell Service Account"
  project      = var.project_id
}

# GCS access for screenshots
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.doorbell.email}"
}

# Secret Manager access
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.doorbell.email}"
}
