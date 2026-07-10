#!/usr/bin/env bash
# Build (if needed) and run the Ticker container on macOS/Linux.
# Idempotent: safe to re-run. Pass --build to force a rebuild.
#
#   ./scripts/start_mac.sh            # build if the image is missing, then run
#   ./scripts/start_mac.sh --build    # always rebuild the image first
set -euo pipefail

IMAGE_NAME="ticker:latest"
CONTAINER_NAME="ticker"
PORT=8000
URL="http://localhost:${PORT}"

# Resolve repo root regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

FORCE_BUILD=false
for arg in "$@"; do
  case "${arg}" in
    --build) FORCE_BUILD=true ;;
    *) echo "Unknown argument: ${arg}" >&2; exit 1 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Warning: no .env file found in ${ROOT_DIR}." >&2
  echo "         Copy .env.example to .env and add your keys (LLM chat needs OPENROUTER_API_KEY)." >&2
fi

# Build the image if forced or if it does not exist yet.
if [[ "${FORCE_BUILD}" == "true" ]] || ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Building image ${IMAGE_NAME}..."
  docker build -t "${IMAGE_NAME}" .
else
  echo "Image ${IMAGE_NAME} already exists (use --build to rebuild)."
fi

# If a container with our name is already running, we're done.
if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Container '${CONTAINER_NAME}' is already running."
  echo "Ticker is available at ${URL}"
  exit 0
fi

# Remove any stopped container with the same name so `docker run` won't clash.
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Removing stopped container '${CONTAINER_NAME}'..."
  docker rm "${CONTAINER_NAME}" >/dev/null
fi

RUN_ARGS=(
  -d
  --name "${CONTAINER_NAME}"
  -p "${PORT}:8000"
  -v "${ROOT_DIR}/db:/app/db"
)
if [[ -f .env ]]; then
  RUN_ARGS+=(--env-file .env)
fi

echo "Starting container '${CONTAINER_NAME}'..."
docker run "${RUN_ARGS[@]}" "${IMAGE_NAME}" >/dev/null

echo "Ticker is running at ${URL}"

# Open the browser on macOS if available.
if command -v open >/dev/null 2>&1; then
  open "${URL}" || true
fi
