# OpenBrick — Open-Source Data Lakehouse on Kubernetes

> An open-source, GitOps-managed data lakehouse that runs identically on a local
> `kind` cluster and on AWS EKS. Spark for processing, Airflow for orchestration,
> Trino for interactive SQL, Iceberg tables on S3.

Status: **draft spec** · Target: reproducible platform, one repo, `terraform apply` + GitOps.

---

## 1. Goals

- **Same manifests everywhere.** kind (laptop) and AWS EKS run the *same* GitOps
  app manifests. Only Terraform env + a values overlay differ.
- **Everything as code.** Terraform provisions the cluster + bootstraps ArgoCD;
  ArgoCD owns every platform component thereafter.
- **S3-native storage.** All data on Iceberg tables over the S3A filesystem.
  Real AWS S3 in the cloud; MinIO-as-S3 only as the local kind backend (app code
  never knows the difference — same `s3a://` URIs, same endpoint env var).
- **Batch + orchestration + query.** Spark (jobs), Airflow (schedules/DAGs),
  Trino (ad-hoc SQL), Hive Metastore (shared catalog).

### Non-goals (v1)
- Multi-tenancy / RBAC hardening beyond namespace isolation. `ponytail: add when a second team uses it`
- Streaming ingestion (Kafka/Flink). Batch only for v1.
- Karpenter autoscaling — start with a fixed EKS managed node group. `add when cost/scale demands it`

---

## 2. Architecture

```
Terraform ──┬─ (kind)  local docker cluster + storage
            └─ (aws)   VPC + EKS + IAM/IRSA + S3 buckets
                │
                └─ bootstraps ArgoCD (Helm) ──► syncs app-manifests/ from Git
                                                   │
   ┌───────────────────────────────────────────────┼───────────────────────────────┐
   │ gitops        deepstore        metastore       processing      orchestration    query
   │ ArgoCD        S3 (MinIO|AWS)    Hive Metastore  Spark Operator  Airflow          Trino
   └───────────────────────────────────────────────────────────────────────────────┘
                                          │
                        Iceberg tables on  s3a://warehouse
```

**Namespaces:** `gitops`, `deepstore`, `metastore`, `processing`, `orchestration`, `query`, `monitoring`.

**Catalog:** Hive Metastore is the single shared catalog. Spark writes Iceberg
tables; Trino reads them through the same metastore + Iceberg connector.

---

## 3. Repository Structure

```
openbrick/
├── kind-cluster.yaml                  # exists — local cluster topology
├── SPEC.md                            # this file
├── terraform/
│   ├── modules/
│   │   ├── eks/                       # VPC, EKS, managed node group
│   │   ├── s3/                        # buckets: raw, warehouse
│   │   ├── irsa/                      # IAM roles for service accounts (Spark, Trino → S3)
│   │   └── argocd/                    # Helm release + git-repo secret + root app
│   └── envs/
│       ├── kind/                      # local: kind provider, MinIO tenant, no AWS
│       │   ├── main.tf  variables.tf  terraform.tfvars
│       └── aws/                       # cloud: real EKS + S3 + IRSA
│           ├── main.tf  variables.tf  terraform.tfvars
├── gitops/
│   ├── root-app.yaml                  # App-of-apps → points at app-manifests/
│   └── app-manifests/
│       ├── deepstore/                 # minio (kind) OR nothing (aws uses real S3)
│       ├── metastore/hive-metastore.yaml
│       ├── processing/spark-operator.yaml
│       ├── orchestration/airflow.yaml
│       ├── query/trino.yaml
│       └── monitoring/kube-prometheus.yaml
├── helm-values/
│   ├── base/                          # shared values per component
│   ├── kind/                          # overlay: MinIO endpoint, small resources
│   └── aws/                           # overlay: real S3 endpoint, IRSA annotations
└── jobs/
    ├── spark/                         # SparkApplication CRDs + pyspark apps
    └── airflow/dags/                  # DAGs that submit Spark jobs / trigger Trino
```

---

## 4. Components & Configuration

### 4.1 Terraform (two envs, shared modules)

| Env  | Cluster | Storage | Auth to S3 |
|------|---------|---------|------------|
| kind | `kind` provider creates cluster from `kind-cluster.yaml` | MinIO tenant (Helm) | static access/secret key in a K8s Secret |
| aws  | `eks` module: VPC + EKS + managed node group | `s3` module: real buckets | **IRSA** — pods assume IAM role, no static keys |

- `terraform/envs/<env>` is the only thing an operator applies. Modules are shared.
- Both envs end by installing the **argocd module**, which Helm-installs ArgoCD
  and applies `gitops/root-app.yaml`. After that, Git is the source of truth.
- Buckets: `raw` (source/landing) and `warehouse` (Iceberg tables).

### 4.2 GitOps — ArgoCD (app-of-apps)

- ArgoCD in `gitops` ns, installed by Terraform Helm release (chart pinned).
- **Root app** (`root-app.yaml`) syncs `gitops/app-manifests/*` — every component
  is one ArgoCD Application, `automated` sync with `prune: true`, `selfHeal: true`,
  `CreateNamespace: true`.
- Each Application references a Helm chart + a **values overlay chosen by env**
  (kind vs aws) so the same manifest works both places. Overlay selection via a
  per-cluster ArgoCD `values` file or ApplicationSet — decision below.
- Repo connection: HTTPS + token (simpler than SSH) unless the repo is private
  and SSH is required. `ponytail: default HTTPS token, switch to SSH deploy key if needed`

### 4.3 Storage — S3 (pluggable)

- **Contract:** every consumer talks S3A to a single endpoint env var
  (`S3_ENDPOINT`) with path-style access. Buckets `raw`, `warehouse`.
- **kind:** MinIO provides the S3 API in-cluster. Static creds via Secret. OpenLake
  uses the **standalone `minio` chart** (M2, simplest for single-node kind). The
  `databricks-spark` reference instead uses the MinIO **operator + tenant** charts
  (both v7.0.0, tenant CR declares buckets/creds).
  `ponytail: standalone now, switch to operator+tenant only if MinIO needs multi-node/managed.`
- **aws:** real S3; endpoint is the AWS regional endpoint; **no static creds** —
  Spark/Trino/Airflow service accounts are IRSA-annotated to assume an IAM role
  scoped to the two buckets.
- App/Helm values differ only in `helm-values/{kind,aws}/`.

### 4.4 Hive Metastore

- Deployed via the project's own POC Helm chart:
  **https://github.com/GustavoV00/helm-hive-metastore** (vendored as an ArgoCD App).
- Shared catalog in `metastore` ns. Backed by a Postgres (in-cluster for kind;
  managed RDS optional for aws — start in-cluster for both to keep it simple).
  `ponytail: in-cluster postgres both envs, move to RDS if durability matters`
- Both Spark and Trino register/read Iceberg tables here.

### 4.5 Spark Operator (`processing` ns)

- **Operator:** kubeflow `spark-operator` Helm chart **2.1.1** (appVersion 2.1.1),
  CRD API `sparkoperator.k8s.io/v1beta2`. Key values:
  `spark.jobNamespaces: [processing]`, SA `spark-operator-spark` (`rbac.create: true`),
  `webhook.enable: true` (port `9443`), `prometheus.metrics.enable: true` (port `8080`),
  `controller.replicas: 1` on kind / 3 on aws. The aws overlay adds a hardened
  container securityContext + `nodeAffinity` on
  `eks.amazonaws.com/capacityType In [ON_DEMAND]`.

- **Custom Spark image** — extends the `databricks-spark` reference recipe:
  - Base `spark:3.5.3` (official Apache).
  - S3A jars: `hadoop-common:3.3.4`, `hadoop-aws:3.3.4`, `aws-java-sdk-bundle:1.12.431`.
    `ponytail: pin one aws-sdk version — reference apps also referenced 1.11.900 via`
    `spark.jars.packages; use the baked 1.12.431 to avoid classpath skew.`
  - `jmx_prometheus_javaagent:0.11.0` at `/prometheus/`.
  - Baked metrics config at `/etc/metrics/conf/{metrics.properties,prometheus.yaml}`.
  - **OpenLake adds (not in the reference, which is Parquet-only):**
    `iceberg-spark-runtime-3.5_2.12` + Iceberg/Hive-Metastore catalog config so jobs
    write Iceberg to `s3a://warehouse` and register in HMS.

- **S3A config** (in `sparkConf`; endpoint templated per env, creds via Secret not inline):
  `spark.hadoop.fs.s3a.endpoint`, `…path.style.access=true`,
  `…impl=org.apache.hadoop.fs.s3a.S3AFileSystem`.

- Jobs pull code via **git-sync init container** (no per-job image rebuilds).

- **SparkApplication CRD skeleton** (adapted from the reference `labs/lab-7`):

  ```yaml
  apiVersion: sparkoperator.k8s.io/v1beta2
  kind: SparkApplication
  metadata: { name: <job>, namespace: processing }
  spec:
    type: Python
    mode: cluster
    image: <openlake-spark-image>
    mainApplicationFile: "local:///app/<job>.py"
    sparkVersion: "3.5.3"
    sparkConf:
      spark.hadoop.fs.s3a.endpoint: "<S3_ENDPOINT>"
      spark.hadoop.fs.s3a.path.style.access: "true"
      spark.hadoop.fs.s3a.impl: "org.apache.hadoop.fs.s3a.S3AFileSystem"
      spark.metrics.conf: "/etc/metrics/conf/metrics.properties"
      # + OpenLake Iceberg catalog conf (spark.sql.catalog.*, HMS thrift URI)
    driver:   { cores: 1, memory: 1024m, serviceAccount: spark-operator-spark, envSecretKeyRefs: {...} }
    executor: { instances: 1, cores: 2, memory: 1024m, envSecretKeyRefs: {...} }
    dynamicAllocation: { enabled: true, initialExecutors: 1, minExecutors: 1, maxExecutors: 8 }
    monitoring:
      exposeDriverMetrics: true
      exposeExecutorMetrics: true
      prometheus: { jmxExporterJar: /prometheus/jmx_prometheus_javaagent-0.11.0.jar, port: 8090 }
  ```

  MinIO/S3 creds injected via `envSecretKeyRefs` → Secret `minio-spark-secret`
  (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`); SA `spark-operator-spark`.

### 4.6 Airflow (`orchestration` ns)

- Official Helm chart. **KubernetesExecutor** (no Celery/Redis — fewer moving parts).
  `ponytail: KubernetesExecutor, revisit only if scheduler throughput is a problem`
- DAGs delivered via **git-sync** from `jobs/airflow/dags/`.
- DAGs submit SparkApplication CRDs (SparkKubernetesOperator) and/or run Trino SQL.
- IRSA (aws) / static-key Secret (kind) for any direct S3 access.

### 4.7 Trino (`query` ns)

- Trino Helm chart, 1 coordinator + N workers (N=1 on kind).
- **Iceberg connector** pointed at the same Hive Metastore + S3 warehouse.
- Serves interactive SQL over the tables Spark produces.

### 4.8 Monitoring (`monitoring` ns)

- `kube-prometheus-stack` **69.3.2** (appVersion v0.80.0 = Prometheus Operator).
  Grafana + default dashboards enabled. Retention 10d, **ephemeral by default** —
  `ponytail: add PVCs for Prometheus/Grafana if durable metrics/dashboards matter.`
- **Spark scrape** via `prometheus.prometheusSpec.additionalScrapeConfigs` — 3 static
  jobs (5s interval) in ns `processing`:
  `spark-operator → operator-metrics:8080`, `spark-job → job-metrics:8090`,
  `spark-webhook → webhook-metrics:8080`. These are HTTP metrics endpoints; Spark
  also exposes its own `prometheusServlet` paths
  (`/metrics/{driver,executor,applications}/prometheus`). Plus Trino/Airflow metrics.
- **Sync ordering:** child apps use `argocd.argoproj.io/sync-wave` (monitoring runs
  after storage, e.g. wave 3) — this is the ordering mechanism for the root app's children.

### 4.9 Pinned versions (from the `databricks-spark` reference)

| Component | Version |
|---|---|
| Apache Spark (base image + `sparkVersion`) | 3.5.3 |
| hadoop-common / hadoop-aws | 3.3.4 |
| aws-java-sdk-bundle | 1.12.431 |
| jmx_prometheus_javaagent | 0.11.0 |
| iceberg-spark-runtime-3.5_2.12 | *(OpenLake add — pin at build)* |
| kubeflow spark-operator chart | 2.1.1 |
| kube-prometheus-stack chart | 69.3.2 (appVersion v0.80.0) |
| MinIO operator/tenant chart *(reference only)* | 7.0.0 |
| argo-cd chart | 7.8.14 (reference) — OpenLake pins 7.7.11, can bump |

### 4.10 What NOT to copy from the reference

The `databricks-spark` reference is a useful recipe source but diverges from OpenLake —
do not carry these over:

- **minikube**, not kind (its `modules/minikube` is minikube-specific).
- **Parquet, no Iceberg, no catalog** — apps write raw Parquet via S3A. OpenLake keeps
  Iceberg + Hive Metastore; the reference image recipe is only a base to extend.
- **No app-of-apps** — its ArgoCD leaf apps are applied out-of-band. OpenLake has a real
  root app (M1).
- **Vendored charts** referenced by in-repo path. OpenLake pulls charts from remote repos.
- **Committed live secrets** (an SSH private key + plaintext `minio/minio123` + argocd admin
  hash). OpenLake keeps secrets out of git — sealed-secrets/SOPS/external-secrets, IRSA on aws.

---

## 5. Deployment Flow

**Local (kind):**
1. `cd terraform/envs/kind && terraform apply` → kind cluster + MinIO + ArgoCD + root app.
2. ArgoCD syncs all components. Done. Access via ingress on localhost:80/443.

**AWS:**
1. `cd terraform/envs/aws && terraform apply` → VPC + EKS + S3 + IRSA + ArgoCD + root app.
2. ArgoCD syncs the same manifests with the `aws` values overlay.
3. Submit jobs: apply SparkApplication / enable Airflow DAGs.

Identical component set both times — the only divergence is the Terraform env
directory and the `helm-values/{kind,aws}/` overlay.

---

## 6. Open Decisions (need a call before implementation)

1. **Env overlay mechanism:** plain per-env `values` files referenced by each
   ArgoCD App, **or** ApplicationSet with a cluster generator. → *recommend plain
   values files first; ApplicationSet only when there's >1 real cluster.*
2. **Local S3:** MinIO-as-S3 on kind (recommended, zero cost) vs. point kind at a
   real AWS bucket. → *recommend MinIO on kind.*
3. **Repo auth for ArgoCD:** HTTPS token vs SSH deploy key. → *HTTPS token unless private+SSH-only.*
4. **Metastore DB:** in-cluster Postgres both envs vs RDS on aws. → *in-cluster first.*
5. **Autoscaling:** fixed node group v1, Karpenter later? → *fixed first.*

---

## 7. Milestones

1. **M1 — Terraform skeleton:** kind + aws envs stand up bare clusters + ArgoCD.
2. **M2 — Storage + catalog:** S3 (MinIO/real) + Hive Metastore synced via GitOps.
3. **M3 — Spark:** operator + one Iceberg-writing SparkApplication, verified on kind.
4. **M4 — Trino:** query the M3 tables via Iceberg connector.
5. **M5 — Airflow:** a DAG that submits the Spark job and runs a Trino check.
6. **M6 — AWS parity:** same stack green on EKS with IRSA + real S3.
7. **M7 — Monitoring:** Prometheus wired, minimal dashboards.
