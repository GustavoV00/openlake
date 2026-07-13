# M1 (kind): stand up the local cluster, then install ArgoCD + app-of-apps.
# The kind topology lives in kind-cluster.yaml — consumed as-is via the kind CLI
# (the tehcyx/kind provider can't ingest an external YAML with kubeadm patches).
# ponytail: CLI-wrapped kind, swap to a provider if state-managed nodes ever matter.

locals {
  kubeconfig = "${path.module}/.kube/config"
}

resource "null_resource" "cluster" {
  triggers = {
    name        = var.cluster_name
    config_hash = filemd5(var.kind_config_path)
  }

  # Idempotent create: skip if the cluster already exists, then export kubeconfig.
  provisioner "local-exec" {
    command = <<-EOT
      set -e
      kind get clusters | grep -qx "${var.cluster_name}" \
        || kind create cluster --name "${var.cluster_name}" --config "${var.kind_config_path}"
      mkdir -p "${dirname(local.kubeconfig)}"
      kind export kubeconfig --name "${var.cluster_name}" --kubeconfig "${local.kubeconfig}"
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "kind delete cluster --name ${self.triggers.name}"
  }
}

provider "helm" {
  kubernetes {
    config_path = local.kubeconfig
  }
}

module "argocd" {
  source     = "../../modules/argocd"
  depends_on = [null_resource.cluster]

  repo_url        = var.repo_url
  target_revision = var.target_revision
  kubeconfig_path = local.kubeconfig
  repo_token      = var.repo_token
}

output "argocd_ui" {
  value = module.argocd.server_hint
}
