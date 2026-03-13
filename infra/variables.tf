variable "project_id" {
  description = "GCP project ID"
  type        = string
}

# Use us-central1 for best availability/pricing.
# For Asia demo presentations, use asia-northeast3 (Seoul) for lower latency.
variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "gemini_api_key" {
  description = "Gemini API key"
  type        = string
  sensitive   = true
}

variable "telegram_bot_token" {
  description = "Telegram Bot API token"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Telegram chat ID for notifications"
  type        = string
}

variable "owner_name" {
  description = "Homeowner display name"
  type        = string
  default     = "Kyuhee"
}

variable "language" {
  description = "Doorbell language"
  type        = string
  default     = "en"
}

variable "delivery_instructions" {
  description = "Default delivery instructions"
  type        = string
  default     = "Please leave it at the door"
}
