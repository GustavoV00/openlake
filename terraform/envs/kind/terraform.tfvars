cluster_name     = "arch-dev-cluster"
kind_config_path = "../../../kind-cluster.yaml"

# ArgoCD pulls manifests from here — must be reachable (public) before the root
# app can sync. Confirm/replace with your actual repo URL.
repo_url        = "https://github.com/GustavoV00/openbrick.git"
target_revision = "HEAD"
