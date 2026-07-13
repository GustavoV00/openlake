variable "namespace" {
  description = "Namespace ArgoCD is installed into."
  type        = string
  default     = "gitops"
}

variable "chart_version" {
  description = "Pinned argo-cd Helm chart version."
  type        = string
  default     = "7.7.11" # argoproj/argo-helm; app ~ v2.13
}

variable "repo_url" {
  description = "Git repo ArgoCD syncs manifests from (public HTTPS for M1)."
  type        = string
}

variable "target_revision" {
  description = "Git ref the root app tracks."
  type        = string
  default     = "HEAD"
}

variable "kubeconfig_path" {
  description = "Path to the kubeconfig used to apply the root Application."
  type        = string
}

variable "repo_token" {
  description = "GitHub PAT for a private repo (HTTPS). Empty = public repo, no credential applied."
  type        = string
  default     = ""
  sensitive   = true
}

variable "repo_username" {
  description = "Username paired with repo_token (any non-empty value for a GitHub PAT)."
  type        = string
  default     = "git"
}

variable "manifests_path" {
  description = "Path within the repo holding child Application manifests."
  type        = string
  default     = "gitops/app-manifests"
}
