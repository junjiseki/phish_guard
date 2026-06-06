variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Google Cloud region for Artifact Registry and Cloud Run."
  type        = string
  default     = "asia-northeast1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "phish-guard-api"
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "phish-guard"
}

variable "image" {
  description = "Container image URI deployed to Cloud Run."
  type        = string
}

variable "allow_unauthenticated" {
  description = "Allow public unauthenticated access. Required for LINE webhook."
  type        = bool
  default     = true
}

variable "app_env" {
  description = "APP_ENV value."
  type        = string
  default     = "production"
}

variable "app_debug" {
  description = "APP_DEBUG value."
  type        = bool
  default     = false
}

variable "app_log_level" {
  description = "APP_LOG_LEVEL value."
  type        = string
  default     = "INFO"
}

variable "line_signature_verification_enabled" {
  description = "Enable LINE webhook signature verification."
  type        = bool
  default     = true
}

variable "daily_user_request_limit" {
  description = "Daily image analysis request limit per LINE user."
  type        = number
  default     = 10
}

variable "user_request_limit_store" {
  description = "Request limit storage backend. Use memory for local/dev or firestore for Cloud Run."
  type        = string
  default     = "firestore"

  validation {
    condition     = contains(["memory", "firestore"], var.user_request_limit_store)
    error_message = "user_request_limit_store must be memory or firestore."
  }
}

variable "firestore_database_id" {
  description = "Firestore database ID used for request limit storage."
  type        = string
  default     = "(default)"
}

variable "firestore_usage_collection" {
  description = "Firestore collection used for request limit storage."
  type        = string
  default     = "line_user_request_usage"
}

variable "gemini_model" {
  description = "Gemini model name."
  type        = string
  default     = "gemini-2.5-flash"
}

variable "request_timeout_seconds" {
  description = "External API request timeout seconds."
  type        = number
  default     = 30
}

variable "max_image_bytes" {
  description = "Maximum image size accepted by the application."
  type        = number
  default     = 10485760
}

variable "line_channel_secret" {
  description = "LINE Channel secret. Empty string skips creating this secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "line_channel_secret_secret_id" {
  description = "Existing Secret Manager secret ID for LINE_CHANNEL_SECRET. Used when line_channel_secret is empty."
  type        = string
  default     = ""
}

variable "line_channel_access_token" {
  description = "LINE Channel access token. Empty string skips creating this secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "line_channel_access_token_secret_id" {
  description = "Existing Secret Manager secret ID for LINE_CHANNEL_ACCESS_TOKEN. Used when line_channel_access_token is empty."
  type        = string
  default     = ""
}

variable "gemini_api_key" {
  description = "Gemini API key. Empty string skips creating this secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "gemini_api_key_secret_id" {
  description = "Existing Secret Manager secret ID for GEMINI_API_KEY. Used when gemini_api_key is empty."
  type        = string
  default     = ""
}
