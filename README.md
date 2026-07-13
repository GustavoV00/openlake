# OpenLake

Open-source data lakehouse on Kubernetes, GitOps-managed, that runs **identically**
on a local `kind` cluster and on AWS EKS. Spark for processing, Airflow for
orchestration, Trino for interactive SQL, Iceberg tables on S3.

> Full design: [`specs/platform.md`](specs/platform.md) · Status: **M1 (kind) implemented**

## How it works

Terraform provisions the cluster and bootstraps **ArgoCD**. After that, Git is the
source of truth — ArgoCD's app-of-apps syncs every platform component from
`gitops/app-manifests/`. The only thing that differs between local and cloud is the
Terraform env directory and a Helm values overlay; the manifests are the same.

```
Terraform ──► kind (local)  or  EKS (aws)
                └─ installs ArgoCD ──► syncs gitops/app-manifests/
                       ├─ deepstore    S3 (MinIO on kind | real S3 on aws)
                       ├─ metastore    Hive Metastore (shared Iceberg catalog)
                       ├─ processing   Spark Operator
                       ├─ orchestration Airflow (KubernetesExecutor)
                       └─ query        Trino
```

## Quick start (local, kind)

Prereqs: `docker`, `kind`, `kubectl`, `terraform`.

```bash
cd terraform/envs/kind
# repo_url in terraform.tfvars must point at your pushed, reachable repo.
# Private repo? Give ArgoCD a GitHub PAT (never commit it):
echo 'repo_token = "ghp_..."' > secret.auto.tfvars   # gitignored (*.auto.tfvars)
terraform init
terraform apply
```

This creates the kind cluster (topology in [`kind-cluster.yaml`](kind-cluster.yaml))
and installs ArgoCD with the app-of-apps root.

```bash
kubectl --context kind-arch-dev-cluster get pods -n gitops        # argocd running
kubectl -n gitops get applications                                # 'root' Synced/Healthy
kubectl -n gitops port-forward svc/argocd-server 8080:443         # UI at https://localhost:8080
```

Tear down: `terraform destroy`.

### Hive Metastore image (M2)

The Hive Metastore chart has no published image — build it from
[helm-hive-metastore](https://github.com/GustavoV00/helm-hive-metastore)'s
`docker/` dir (tag `hive-metastore:4.2.0`) and load it into kind before the app
can start:

```bash
scripts/load-hms-image.sh          # loads hive-metastore:4.2.0 into kind
```

MinIO and Postgres sync with no extra steps.

## Layout

```
specs/            design specs (platform.md = the lakehouse)
kind-cluster.yaml local cluster topology
terraform/
  modules/argocd/ ArgoCD install + app-of-apps (shared: kind now, aws at M6)
  envs/kind/      local env — kind + ArgoCD, applyable today
gitops/
  app-manifests/  ArgoCD child Applications (deepstore, metastore, ...)
  metastore/      raw manifests for the metastore infra (postgres, secrets)
scripts/          helpers (load HMS image into kind)
```

## Roadmap

| | Milestone | Status |
|--|--|--|
| M1 | Terraform kind + ArgoCD bootstrap | ✅ done |
| M2 | S3 (MinIO) + Hive Metastore via GitOps | ✅ done |
| M3 | Spark Operator + Iceberg-writing job | |
| M4 | Trino querying M3 tables | |
| M5 | Airflow DAG driving Spark + Trino | |
| M6 | AWS parity: EKS + IRSA + real S3 | |
| M7 | Monitoring (Prometheus) | |
