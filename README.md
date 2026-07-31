# OpenLake

An open-source **data lakehouse** that runs on Kubernetes. You write data with
**Spark**, schedule it with **Airflow**, and query it with **Trino** — all over
**Iceberg** tables stored on **S3**. Everything is managed by **GitOps** (ArgoCD),
so the cluster's state is whatever this Git repo says it should be.

The whole thing runs **identically** on your laptop (a local `kind` cluster with
MinIO standing in for S3) and on AWS EKS (real S3). Only the Terraform env
directory and a values file differ.

> Full design doc: [`specs/platform.md`](specs/platform.md)
> Status: **M1–M5 done** (local `kind` fully working, end-to-end). M6 (AWS) & M7 (monitoring) pending.

---

## Table of contents

1. [What are all these pieces?](#1-what-are-all-these-pieces)
2. [How it fits together](#2-how-it-fits-together)
3. [Prerequisites — install these first](#3-prerequisites--install-these-first)
4. [Repository layout](#4-repository-layout)
5. [First run, step by step](#5-first-run-step-by-step-local-kind)
6. [Checking that it's up](#6-checking-that-its-up)
7. [Opening the web UIs](#7-opening-the-web-uis)
8. [Running your first data job](#8-running-your-first-data-job)
9. [Configuration reference](#9-configuration-reference)
10. [Troubleshooting](#10-troubleshooting)
11. [Tearing it down](#11-tearing-it-down)
12. [Roadmap](#12-roadmap)

---

## 1. What are all these pieces?

If you're new to the lakehouse world, here's the cast in plain language:

| Piece | What it is | Why it's here |
|---|---|---|
| **Kubernetes (kind)** | Runs containers. `kind` = "Kubernetes IN Docker", a throwaway cluster on your laptop. | The platform everything runs on. |
| **Terraform** | Infrastructure-as-code. | Creates the cluster and installs ArgoCD. That's *all* it does — the one command you run by hand. |
| **ArgoCD (GitOps)** | Watches this Git repo and makes the cluster match it. | After Terraform, you never `kubectl apply` platform components by hand — you commit to Git and ArgoCD syncs. |
| **MinIO** | An S3-compatible object store. | Stands in for AWS S3 on your laptop. Same `s3a://` URLs, same API. |
| **Hive Metastore (HMS)** | A catalog: "table X lives at path Y with columns Z". | The *shared* catalog. Spark and Trino both use it, so they agree on what tables exist. |
| **Iceberg** | A table format on top of S3 files. | Gives you real tables (schema, evolution, partitions) instead of loose Parquet. |
| **Spark** | Distributed data processing. | Writes/transforms the data. Jobs run as `SparkApplication` CRDs via the Spark Operator. |
| **Trino** | A fast SQL query engine. | Interactive `SELECT` over the Iceberg tables Spark produced. |
| **Airflow** | A scheduler / orchestrator. | Runs DAGs that submit Spark jobs and check results in Trino. |

**The data flow:** Spark writes an Iceberg table to `s3a://warehouse`, registers it
in the Hive Metastore → Trino reads it back through that same metastore → Airflow
ties the steps together on a schedule.

---

## 2. How it fits together

```
  YOU run:  terraform apply
      │
      ▼
  ┌─────────────────────────────────────────────────────────┐
  │ kind cluster (local Docker)                              │
  │                                                          │
  │  Terraform installs ──► ArgoCD ──► reads gitops/ in Git  │
  │                            │                             │
  │                            ▼  (syncs every component)    │
  │   ┌──────────────────────────────────────────────────┐  │
  │   │ wave -1  minio-operator   (MinIO CRDs)            │  │
  │   │ wave  0  minio-tenant     (S3: buckets raw+warehouse) │
  │   │ wave  0  hive-metastore   (shared catalog)        │  │
  │   │ wave  1  spark-operator   (runs Spark jobs)       │  │
  │   │ wave  2  trino            (SQL engine)            │  │
  │   │ wave  3  airflow          (scheduler)            │  │
  │   └──────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────┘

  Namespaces: gitops · deepstore · metastore · processing · query · orchestration
```

**Sync waves** are ArgoCD's ordering knob — lower numbers sync first, so storage
is up before Spark, and Spark+Trino are up before Airflow (whose DAG uses them).

---

## 3. Prerequisites — install these first

You need four CLI tools on your machine. On Linux/WSL:

| Tool | Check | Install hint |
|---|---|---|
| **Docker** | `docker ps` | [docs.docker.com](https://docs.docker.com/engine/install/) — must be running |
| **kind** | `kind version` | `go install sigs.k8s.io/kind@latest` or your package manager |
| **kubectl** | `kubectl version --client` | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| **terraform** | `terraform version` | [developer.hashicorp.com](https://developer.hashicorp.com/terraform/install) |

Nice to have: **`mc`** (MinIO client, for uploading Spark scripts) and **`helm`**
(only if you want to inspect charts). Neither is strictly required for the happy path.

> **Resources:** the cluster runs MinIO + HMS + Spark + Trino + Airflow. Give
> Docker at least **6 GB RAM** or pods will get OOM-killed.

---

## 4. Repository layout

```
openbrick/
├── kind-cluster.yaml           # local cluster topology (1 control-plane + 2 workers, ports 80/443)
├── specs/platform.md           # the full design spec — read this for the "why"
│
├── terraform/
│   ├── modules/argocd/         # installs ArgoCD + applies the app-of-apps root (shared: kind now, aws later)
│   └── envs/kind/              # THE thing you `terraform apply`. Points ArgoCD at the Git repo.
│
├── gitops/                     # everything ArgoCD syncs (this is the "desired state")
│   ├── app-manifests/          # one ArgoCD Application per component (minio, hms, spark, trino, airflow)
│   ├── helm-charts/            # vendored upstream Helm charts (pinned, pristine)
│   └── config/                 # per-component values overlays (the *-/kind.yaml files) + raw manifests (secrets, rbac)
│
├── docker/hive-metastore/      # HMS image build context (also see the helm-hive-metastore repo)
│
├── jobs/
│   ├── spark/                  # SparkApplication CRDs + the pyspark scripts + the custom Spark image
│   └── airflow/                # the DAGs + the custom Airflow image
│
└── scripts/                    # helpers: build+load local images into kind, run the metastore Postgres
```

**Key idea:** an ArgoCD Application (in `app-manifests/`) points at a *chart*
(in `helm-charts/`) **plus** a *values file* (in `config/<component>/kind.yaml`).
To change how a component is configured on kind, you edit its `config/.../kind.yaml`
and commit — ArgoCD does the rest.

---

## 5. First run, step by step (local `kind`)

### Step 0 — the Git repo ArgoCD reads

ArgoCD pulls manifests over HTTPS from the repo in
[`terraform/envs/kind/terraform.tfvars`](terraform/envs/kind/terraform.tfvars)
(`repo_url`, default `github.com/GustavoV00/openlake.git`). **Whatever you push
must be reachable by ArgoCD**, and it syncs `HEAD` — so commit and push your
changes before expecting them to appear.

- Public repo → nothing else to do.
- Private repo → give ArgoCD a GitHub Personal Access Token, never committed:
  ```bash
  cd terraform/envs/kind
  echo 'repo_token = "ghp_xxxxxxxx"' > secret.auto.tfvars   # *.auto.tfvars is gitignored
  ```

### Step 1 — build the local images (Docker has no registry here)

kind can't pull `hive-metastore`, `openlake-spark`, or `openlake-airflow` from
any registry — they're built locally and side-loaded. Run these once (rebuild
when you change the Dockerfiles or job code):

```bash
# Hive Metastore — build from the chart's repo first (see script header), then load:
scripts/load-hms-image.sh              # loads hive-metastore:3.1.3 into kind

# Spark and Airflow — the scripts build AND load from jobs/*/Dockerfile:
scripts/load-spark-image.sh            # openlake-spark:4.0.2
scripts/load-airflow-image.sh          # openlake-airflow:3.2.2
```

> The HMS chart has no published image. Build it once from
> [helm-hive-metastore](https://github.com/GustavoV00/helm-hive-metastore)'s
> `docker/` dir (`docker build -t hive-metastore:3.1.3 .`), then the load script
> above pushes it into the cluster. See `scripts/load-hms-image.sh` for the exact steps.

### Step 2 — start the metastore's Postgres

The Hive Metastore needs a database. On kind it's a **plain Docker container** on
kind's network (not a k8s pod), so the metastore reaches it by name:

```bash
scripts/local-postgres.sh              # starts container 'metastore-pg' (db/user/pass = metastore_db/hive/hive)
```

### Step 3 — create the cluster + install ArgoCD

This is the one Terraform command. It creates the kind cluster and installs
ArgoCD with the app-of-apps root; ArgoCD then syncs everything else on its own.

```bash
cd terraform/envs/kind
terraform init
terraform apply                        # type 'yes'
```

That's it. Give ArgoCD a few minutes to pull charts and bring pods up.

---

## 6. Checking that it's up

The kind context is `kind-arch-dev-cluster`.

```bash
# ArgoCD itself is running:
kubectl --context kind-arch-dev-cluster -n gitops get pods

# Every component Application should reach Synced / Healthy:
kubectl -n gitops get applications
# NAME             SYNC STATUS   HEALTH STATUS
# root             Synced        Healthy
# minio-operator   Synced        Healthy
# minio-tenant     Synced        Healthy
# hive-metastore   Synced        Healthy
# spark-operator   Synced        Healthy
# trino            Synced        Healthy
# airflow          Synced        Healthy

# Pods across the data-plane namespaces:
kubectl get pods -A | grep -E 'deepstore|metastore|processing|query|orchestration'
```

If `hive-metastore` is `ImagePullBackOff`, you skipped **Step 1** (build/load the image).

---

## 7. Opening the web UIs

Everything is inside the cluster; reach it with `kubectl port-forward`.

**ArgoCD** (see sync status visually):
```bash
kubectl -n gitops port-forward svc/argocd-server 8080:443
# → https://localhost:8080   user: admin
# password:
kubectl -n gitops get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

**MinIO console** (browse the S3 buckets `raw` / `warehouse`):
```bash
kubectl -n deepstore port-forward svc/deepstore-console 9090:9090
# → http://localhost:9090   login: minioadmin / minioadmin
```

**Trino** (run SQL):
```bash
kubectl -n query port-forward svc/trino 8081:8080
# → http://localhost:8081   (no auth; catalog 'iceberg')
```

**Airflow** (trigger/inspect DAGs):
```bash
kubectl -n orchestration port-forward svc/airflow-api-server 8082:8080
# → http://localhost:8082
```

> Credentials are plaintext `minioadmin`/`minioadmin` etc. — **fine for local
> kind only.** On AWS these become IRSA / a real secret store.

---

## 8. Running your first data job

There are two ways to run the end-to-end smoke test (Spark writes an Iceberg
table → Trino reads it): **manually**, or **via the Airflow DAG** that automates
those same steps.

### 8a. Manually (understand the moving parts)

```bash
# 1. S3 creds for the Spark pods (matches MinIO root creds):
kubectl apply -f jobs/spark/minio-spark-secret.yaml

# 2. Upload the pyspark script to MinIO — the job loads it from s3a, so editing
#    the script needs NO image rebuild, just a re-upload. (Needs the `mc` client
#    aliased to the port-forwarded MinIO, or run it from a pod.)
mc cp jobs/spark/warehouse_smoke.py local/warehouse/scripts/warehouse_smoke.py

# 3. Submit the Spark job:
kubectl apply -f jobs/spark/warehouse-smoke.yaml

# 4. Watch it — look for "SMOKE OK" in the logs:
kubectl logs -n processing warehouse-smoke-driver -f
```

Then query it in Trino (UI from §7, or the CLI):
```sql
SELECT * FROM iceberg.bronze.demo;      -- 3 rows
```

Other example jobs in `jobs/spark/`: `partition-smoke.*` (partitioned writes) and
`schema-evolution-smoke.*` (add a column to an existing Iceberg table).

### 8b. Via Airflow (the orchestrated version)

The DAG [`warehouse_smoke_dag`](jobs/airflow/dags/warehouse_smoke_dag.py) does all
of §8a for you: submits the Spark job, waits for it, then asserts Trino returns 3 rows.

1. One-time: create a Trino connection in Airflow (**Admin → Connections**),
   id `trino_default`, host `trino.query.svc.cluster.local`, port `8080`, no auth.
2. In the Airflow UI (§7), un-pause `warehouse_smoke_dag` and **Trigger** it.
3. All three tasks (`submit_spark_job → wait_for_spark_job → check_trino_row_count`)
   should go green.

---

## 9. Configuration reference

### Endpoints & credentials (kind)

| What | Value |
|---|---|
| S3 endpoint (in-cluster) | `http://minio.deepstore.svc.cluster.local:80` (the tenant Service; **:80**, not :9000) |
| S3 buckets | `raw`, `warehouse` |
| S3 / MinIO creds | `minioadmin` / `minioadmin` |
| Hive Metastore (thrift) | `thrift://hive-metastore.metastore.svc.cluster.local:9083` |
| Metastore Postgres | container `metastore-pg`, db `metastore_db`, `hive` / `hive` |
| Trino (in-cluster) | `trino.query.svc.cluster.local:8080`, catalog `iceberg` |
| kind context / cluster | `kind-arch-dev-cluster` / `arch-dev-cluster` |

### Namespaces

`gitops` (ArgoCD) · `deepstore` (MinIO) · `metastore` (HMS) · `processing`
(Spark) · `query` (Trino) · `orchestration` (Airflow) · `monitoring` (M7, not yet).

### Where things are configured

- **Component config** → `gitops/config/<component>/kind.yaml` (edit + commit + push; ArgoCD syncs).
- **Secrets (kind)** → `gitops/config/hive-metastore/manifests/secrets.yaml`,
  `jobs/spark/minio-spark-secret.yaml`. Plaintext, local-only.
- **Which Git repo/branch ArgoCD reads** → `terraform/envs/kind/terraform.tfvars`.
- **Cluster shape** → `kind-cluster.yaml`.

### Pinned versions

| Component | Version |
|---|---|
| Kubernetes (kind node) | v1.29.2 |
| MinIO operator + tenant chart | 7.1.1 |
| Hive Metastore image | 3.1.3 |
| Spark image (`openlake-spark`) | 4.0.2 |
| kubeflow spark-operator chart | 2.1.1 |
| Trino chart / Trino | 1.42.2 / 480 |
| Airflow chart / Airflow | 1.22.0 / 3.2.2 |

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `hive-metastore` pod `ImagePullBackOff` | Image not loaded. Run `scripts/load-hms-image.sh` (build it first — see script header). |
| `openlake-spark` / `openlake-airflow` `ErrImageNeverPull` | Same — run the matching `scripts/load-*-image.sh`. |
| HMS pod crashes: can't reach DB | Postgres not running. `scripts/local-postgres.sh`. Confirm `docker ps` shows `metastore-pg`. |
| ArgoCD app `OutOfSync` / stale | Did you **push** to the repo ArgoCD reads? It syncs `HEAD` of the remote, not your working tree. Force: **Refresh/Sync** in the ArgoCD UI. |
| Spark job can't read/write S3 | Endpoint must be `:80` (tenant Service), not `:9000`. Creds env from `minio-spark-secret`. |
| Trino query says table not found | The Spark job hasn't written it yet, or HMS is down. Check `iceberg.bronze.demo` exists. |
| Pods OOM-killed / pending | Docker has too little RAM. Give it ≥6 GB. |
| Airflow DAG Trino task fails to connect | Create the `trino_default` connection (see §8b step 1). |

---

## 11. Tearing it down

```bash
cd terraform/envs/kind
terraform destroy                      # deletes the kind cluster

docker rm -f metastore-pg              # drop the metastore Postgres container
```

The images side-loaded into kind vanish with the cluster.

---

## 12. Roadmap

| | Milestone | Status |
|--|--|--|
| M1 | Terraform kind + ArgoCD bootstrap | ✅ done |
| M2 | S3 (MinIO) + Hive Metastore via GitOps | ✅ done |
| M3 | Spark Operator + Iceberg-writing job | ✅ done |
| M4 | Trino querying M3 tables | ✅ done |
| M5 | Airflow DAG driving Spark + Trino | ✅ done |
| M6 | AWS parity: EKS + IRSA + real S3 | ⬜ pending |
| M7 | Monitoring (Prometheus/Grafana) | ⬜ pending |
