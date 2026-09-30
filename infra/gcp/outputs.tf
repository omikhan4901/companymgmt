output "workload_identity_provider" {
  description = "Set as the GitHub variable GCP_WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Set as the GitHub variable GCP_DEPLOY_SA"
  value       = google_service_account.deploy.email
}

output "runtime_service_account" {
  description = "Set as the GitHub variable GCP_RUNTIME_SA"
  value       = google_service_account.runtime.email
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.images.repository_id}"
}
