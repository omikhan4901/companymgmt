variable "project" {
  description = "Google Cloud project id"
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, images and secrets (close to Neon's region)"
  type        = string
  default     = "asia-southeast1"
}

variable "github_repository" {
  description = "owner/repo allowed to deploy"
  type        = string
  default     = "omikhan4901/companymgmt"
}

variable "billing_account" {
  description = "Billing account id for the budget alert (leave empty to skip)"
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Budget alert amount; alerts at 20/50/80/100%"
  type        = number
  default     = 50
}
