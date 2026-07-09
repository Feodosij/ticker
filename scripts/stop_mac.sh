#!/usr/bin/env bash
# Stop and remove the FinAlly container on macOS/Linux.
# Idempotent: does nothing (successfully) if the container isn't there.
# The ./db data volume is left untouched — your portfolio persists.
set -euo pipefail

CONTAINER_NAME="finally"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Stopping and removing container '${CONTAINER_NAME}'..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "Stopped. Data in ./db is preserved."
else
  echo "No container named '${CONTAINER_NAME}' found. Nothing to do."
fi
