#!/usr/bin/env bash
# Local Postgres for the Hive Metastore — a plain Docker container, NOT a k8s
# workload. Runs on kind's docker network so the metastore pod reaches it by
# container name (database.host: metastore-pg in config/hive-metastore/kind.yaml).
# Creds match config/hive-metastore/manifests/secrets.yaml (hive/hive).
# ponytail: throwaway local DB; `docker rm -f metastore-pg` to drop it.
set -euo pipefail

NAME="${1:-metastore-pg}"
NETWORK="${2:-kind}"          # kind puts its nodes on the 'kind' docker network
IMAGE="${3:-postgres:16-alpine}"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "Container '$NAME' already exists — starting it."
  docker start "$NAME"
else
  # Publishes 5432 so you can also psql from the host; the metastore itself
  # reaches it over the kind network by container name, not this port.
  docker run -d --name "$NAME" --network "$NETWORK" \
    -e POSTGRES_DB=metastore_db \
    -e POSTGRES_USER=hive \
    -e POSTGRES_PASSWORD=hive \
    -p 5432:5432 \
    "$IMAGE"
  echo "Started '$NAME' on network '$NETWORK'."
fi

echo "hive-metastore reaches it at host '$NAME:5432'. IP if DNS fails:"
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$NAME"
