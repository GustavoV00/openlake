#!/usr/bin/env bash
# Build the OpenLake Airflow image (jobs/airflow/Dockerfile) and load it into
# kind so the Airflow chart can pull it (imagePullPolicy: IfNotPresent, no
# registry). Mirrors scripts/load-spark-image.sh.
set -euo pipefail

IMAGE="${1:-openlake-airflow:3.2.2}"
CLUSTER="${2:-arch-dev-cluster}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../jobs/airflow" && pwd)"

docker build -t "$IMAGE" "$DIR"
kind load docker-image "$IMAGE" --name "$CLUSTER"
echo "Built and loaded $IMAGE into kind cluster '$CLUSTER'."
