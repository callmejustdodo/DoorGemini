resource "google_storage_bucket" "screenshots" {
  name     = "${var.project_id}-doorbell-screenshots"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age                = 7
      matches_prefix     = ["screenshots/"]
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}
