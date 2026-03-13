output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.doorbell.uri
}

output "bucket_name" {
  description = "GCS bucket for screenshots"
  value       = google_storage_bucket.screenshots.name
}

output "webhook_url" {
  description = "Telegram webhook URL"
  value       = "${google_cloud_run_v2_service.doorbell.uri}/api/telegram/webhook"
}
