variable "cluster_name" {
  description = "kind cluster name (must match kind-cluster.yaml)."
  type        = string
  default     = "arch-dev-cluster"
}

variable "kind_config_path" {
  description = "Path to the kind cluster topology file."
  type        = string
  default     = "../../../kind-cluster.yaml"
}

variable "repo_url" {
  description = "Git repo ArgoCD syncs from (public HTTPS for M1)."
  type        = string
}

variable "target_revision" {
  description = "Git ref the root app tracks."
  type        = string
  default     = "HEAD"
}

variable "repo_token" {
  description = "GitHub PAT for the private repo. Set via TF_VAR_repo_token or a gitignored *.auto.tfvars."
  type        = string
  default     = ""
  sensitive   = true
}
