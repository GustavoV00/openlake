output "namespace" {
  description = "Namespace ArgoCD runs in."
  value       = helm_release.argocd.namespace
}

output "server_hint" {
  description = "How to reach the ArgoCD UI."
  value       = "kubectl -n ${var.namespace} port-forward svc/argocd-server 8080:443  # then https://localhost:8080"
}
