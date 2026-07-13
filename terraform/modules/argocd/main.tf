# Installs ArgoCD via Helm, then hands control to Git by applying the app-of-apps
# root Application. Reused by both envs (kind now, aws at M6).
#
# The root app is applied with kubectl AFTER the Helm release completes (wait=true),
# not inside the release: bundling it as extraObjects races the Application CRD
# install ("no matches for kind Application"). A separate kubectl apply guarantees
# the CRD is registered first.

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = var.namespace
  create_namespace = true

  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.chart_version

  wait    = true
  timeout = 600
}

# App-of-apps: recurses the manifests path and syncs each child Application.
# Empty dir today = healthy no-op until M2 adds children.
resource "null_resource" "root_app" {
  depends_on = [helm_release.argocd]

  triggers = {
    manifest = local.root_app_yaml
    kubecfg  = var.kubeconfig_path
  }

  provisioner "local-exec" {
    command = "kubectl --kubeconfig '${var.kubeconfig_path}' apply -f - <<'EOF'\n${local.root_app_yaml}\nEOF"
  }
}

locals {
  root_app_yaml = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "root"
      namespace = var.namespace
    }
    spec = {
      project = "default"
      source = {
        repoURL        = var.repo_url
        targetRevision = var.target_revision
        path           = var.manifests_path
        directory      = { recurse = true }
      }
      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = var.namespace
      }
      syncPolicy = {
        automated   = { prune = true, selfHeal = true }
        syncOptions = ["CreateNamespace=true"]
      }
    }
  })
}
