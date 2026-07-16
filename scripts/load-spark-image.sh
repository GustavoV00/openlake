#!/usr/bin/env bash
# Build the OpenLake Spark image (jobs/spark/Dockerfile) and load it into kind so
# SparkApplications can pull it (imagePullPolicy: IfNotPresent, no registry).
set -euo pipefail

IMAGE="${1:-openlake-spark:4.0.2}"
CLUSTER="${2:-arch-dev-cluster}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../jobs/spark" && pwd)"

docker build -t "$IMAGE" "$DIR"
kind load docker-image "$IMAGE" --name "$CLUSTER"
echo "Built and loaded $IMAGE into kind cluster '$CLUSTER'."
