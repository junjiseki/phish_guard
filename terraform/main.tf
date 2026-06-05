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

  existing_secret_ids = {
    for key, value in {
      LINE_CHANNEL_SECRET       = var.line_channel_secret_secret_id
      LINE_CHANNEL_ACCESS_TOKEN = var.line_channel_access_token_secret_id
      GEMINI_API_KEY            = var.gemini_api_key_secret_id
    } : key => value if value != ""
  }

  enabled_secret_keys = toset([
    for key, value in local.secret_values : key if nonsensitive(value) != ""
  ])

  cloud_run_secret_ids = merge(
    {
      for key in local.enabled_secret_keys :
      key => google_secret_manager_secret.app[key].secret_id
    },
    local.existing_secret_ids,
  )

  cloud_run_secret_versions = merge(
    {
      for key in local.enabled_secret_keys :
      key => google_secret_manager_secret_version.app[key].version
    },
    {
      for key in keys(local.existing_secret_ids) :
      key => "latest"
    },
  )
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
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

resource "google_secret_manager_secret_iam_member" "cloud_run_existing" {
  for_each = local.existing_secret_ids

  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_firestore_user" {
  count = var.user_request_limit_store == "firestore" ? 1 : 0

  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
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
        name  = "DAILY_USER_REQUEST_LIMIT"
        value = tostring(var.daily_user_request_limit)
      }

      env {
        name  = "USER_REQUEST_LIMIT_STORE"
        value = var.user_request_limit_store
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = var.firestore_database_id
      }

      env {
        name  = "FIRESTORE_USAGE_COLLECTION"
        value = var.firestore_usage_collection
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
        for_each = local.cloud_run_secret_ids

        content {
          name = env.key

          value_source {
            secret_key_ref {
              secret  = env.value
              version = local.cloud_run_secret_versions[env.key]
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
    google_secret_manager_secret_iam_member.cloud_run_existing,
    google_project_iam_member.cloud_run_firestore_user,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_unauthenticated ? 1 : 0

  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
