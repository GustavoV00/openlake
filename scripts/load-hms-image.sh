#!/usr/bin/env bash
# Load a locally-built Hive Metastore image into the kind cluster so the
# hive-metastore ArgoCD app can pull it (pullPolicy: IfNotPresent, no registry).
#
# Build the image first from the chart's docker/ dir, staging the Hadoop/Hive
# artifacts its Dockerfile documents, tagged to match hive-metastore.yaml:
#   git clone https://github.com/GustavoV00/helm-hive-metastore
#   cd helm-hive-metastore/docker  # stage tarballs+jars per Dockerfile comments
#   docker build -t hive-metastore:4.2.0 .
# ponytail: image build lives with the chart, not here — this only loads it.
set -euo pipefail

IMAGE="${1:-hive-metastore:4.2.0}"
CLUSTER="${2:-arch-dev-cluster}"

kind load docker-image "$IMAGE" --name "$CLUSTER"
echo "Loaded $IMAGE into kind cluster '$CLUSTER'."
