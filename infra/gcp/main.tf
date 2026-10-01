# Google Cloud resources for CompanyMgmt (OpenTofu).
#
# Creates: the APIs, an image registry that keeps only recent images, three service
# accounts with the least access each needs, GitHub OIDC (no JSON keys), empty secret
# containers, and a budget alert. Secret VALUES are never in this code or its state:
# add them with `gcloud secrets versions add` (see docs/runbooks/deploy.md).

terraform {
  required_version = ">= 1.8"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Remote state in a GCS bucket you create once (see the runbook):
  # backend "gcs" { bucket = "<project>-tofu-state" prefix = "companymgmt" }
}

provider "google" {
  project = var.project
  region  = var.region
}

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtasks.googleapis.com",
    "billingbudgets.googleapis.com",
  ]
  secrets = [
    "database-url",
    "migrations-database-url",
    "jwt-private-key",
    "field-encryption-keys",
    "smtp-url",
    "internal-token",
    "proxy-token",
    # Nightly backup: the cm_backup role's address, and Cloudflare R2 keys.
    "backup-database-url",
    "r2-access-key-id",
    "r2-secret-access-key",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---- Images -----------------------------------------------------------------------------

resource "google_artifact_registry_repository" "images" {
  repository_id = "companymgmt"
  location      = var.region
  format        = "DOCKER"
  description   = "CompanyMgmt API images"

  # Stay inside the 0.5 GB free tier: keep the 5 newest images, delete the rest.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "604800s"
    }
  }
  depends_on = [google_project_service.apis]
}

# ---- Service accounts ---------------------------------------------------------------------

# What the API and the migration job run as: reads its secrets, nothing else.
resource "google_service_account" "runtime" {
  account_id   = "companymgmt-run"
  display_name = "CompanyMgmt API runtime"
}

# What GitHub Actions deploys as.
resource "google_service_account" "deploy" {
  account_id   = "companymgmt-deploy"
  display_name = "CompanyMgmt deploys from GitHub"
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secrets)
  secret_id = each.value
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_reads" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "deploy_pushes" {
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

# Deploy Cloud Run services and jobs (not admin: can't change IAM policies).
resource "google_project_iam_member" "deploy_runs" {
  project = var.project
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Allowed to start services as the runtime account, and only that account.
resource "google_service_account_iam_member" "deploy_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# ---- GitHub OIDC (no long-lived keys) ------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Only this repository's main branch can deploy.
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"refs/heads/main\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_impersonates_deploy" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# ---- Budget alert ---------------------------------------------------------------------------

resource "google_billing_budget" "monthly" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "CompanyMgmt monthly"
  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }
  dynamic "threshold_rules" {
    for_each = [0.2, 0.5, 0.8, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }
}

data "google_project" "this" {}

# ---- Nightly jobs ---------------------------------------------------------------------
# Cloud Scheduler starts two Cloud Run Jobs that the deploy workflow creates:
#   companymgmt-maintenance  purges deleted workspaces and old audit entries
#   companymgmt-backup       pg_dump | age → Cloudflare R2, kept 30 days

resource "google_service_account" "scheduler" {
  account_id   = "companymgmt-scheduler"
  display_name = "CompanyMgmt starts its nightly jobs"
}

# Allowed to start Cloud Run jobs, nothing else.
resource "google_project_iam_member" "scheduler_runs_jobs" {
  project = var.project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "nightly" {
  for_each = {
    "companymgmt-maintenance" = "23 3 * * *"
    "companymgmt-backup"      = "47 3 * * *"
  }
  name             = each.key
  schedule         = each.value
  time_zone        = var.time_zone
  attempt_deadline = "320s"
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project}/locations/${var.region}/jobs/${each.key}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_project_service.apis]
}
