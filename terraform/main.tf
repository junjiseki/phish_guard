locals {
  labels = {
    app     = "phish-guard"
    managed = "terraform"
  }

  secret_values = {
    LINE_CHANNEL_SECRET       = var.line_channel_secret
    LINE_CHANNEL_ACCESS_TOKEN = var.line_channel_access_token
    GEMINI_API_KEY            = var.gemini_api_key
  }

  enabled_secret_keys = toset([
    for key, value in local.secret_values : key if nonsensitive(value) != ""
  ])
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  description   = "Docker images for phish guard"
  format        = "DOCKER"
  labels        = local.labels

  depends_on = [google_project_service.required]
}

resource "google_service_account" "cloud_run" {
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime for ${var.service_name}"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "app" {
  for_each = local.enabled_secret_keys

  secret_id = lower(replace(each.value, "_", "-"))
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "app" {
  for_each = local.enabled_secret_keys

  secret      = google_secret_manager_secret.app[each.value].id
  secret_data = local.secret_values[each.value]
}

resource "google_secret_manager_secret_iam_member" "cloud_run" {
  for_each = local.enabled_secret_keys

  secret_id = google_secret_manager_secret.app[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.image

      ports {
        container_port = 8000
      }

      env {
        name  = "APP_ENV"
        value = var.app_env
      }

      env {
        name  = "APP_DEBUG"
        value = tostring(var.app_debug)
      }

      env {
        name  = "APP_LOG_LEVEL"
        value = var.app_log_level
      }

      env {
        name  = "LINE_SIGNATURE_VERIFICATION_ENABLED"
        value = tostring(var.line_signature_verification_enabled)
      }

      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }

      env {
        name  = "REQUEST_TIMEOUT_SECONDS"
        value = tostring(var.request_timeout_seconds)
      }

      env {
        name  = "MAX_IMAGE_BYTES"
        value = tostring(var.max_image_bytes)
      }

      dynamic "env" {
        for_each = local.enabled_secret_keys

        content {
          name = env.value

          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = google_secret_manager_secret_version.app[env.value].version
            }
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }

        cpu_idle = true
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.cloud_run,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_unauthenticated ? 1 : 0

  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
