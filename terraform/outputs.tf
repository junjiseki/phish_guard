output "artifact_registry_repository" {
  description = "Artifact Registry repository resource name."
  value       = google_artifact_registry_repository.docker.name
}

output "cloud_run_service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.api.name
}

output "cloud_run_service_url" {
  description = "Cloud Run service URL."
  value       = google_cloud_run_v2_service.api.uri
}

output "line_webhook_callback_url" {
  description = "Webhook URL for the /callback development endpoint."
  value       = "${google_cloud_run_v2_service.api.uri}/callback"
}

output "line_webhook_url" {
  description = "Webhook URL for the main LINE endpoint."
  value       = "${google_cloud_run_v2_service.api.uri}/line/webhook"
}
