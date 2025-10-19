#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/deploy.sh <storage-class-name> <repository>

Builds the project Docker image, pushes it to the configured Docker registry,
and deploys the Helm chart with the specified storage class for the runner's
persistent volume claim.

Environment variables:
  REGISTRY        Docker registry to push to (default: localhost:5000)
  IMAGE_NAME      Image name without tag (default: kubernetes-ci-runner)
  IMAGE_TAG       Tag for the image (default: current git commit short SHA)
  CHART_PATH      Path to the Helm chart (default: charts/ci-runner)
  RELEASE_NAME    Helm release name (default: ci-runner)
  NAMESPACE       Kubernetes namespace for the release (default: default)
  RUNNER_BRANCH   Git branch the runner should track (default: main)
  APP_IMAGE       Target application image repository (required)
  APP_CHART_PATH  Path to the target Helm chart within the repository (required)
  APP_RELEASE     Helm release name for the target application (required)
USAGE
}

if [[ "${1-}" == "-h" || "${1-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "Error: storage class name is required." >&2
  echo >&2
  usage >&2
  exit 1
fi

STORAGE_CLASS=$1

if [[ $# -lt 2 ]]; then
  echo "Error: repository (org/repo) is required." >&2
  echo >&2
  usage >&2
  exit 1
fi

REPOSITORY=$2

REGISTRY=${REGISTRY:-localhost:5000}
IMAGE_NAME=${IMAGE_NAME:-kubernetes-ci-runner}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
CHART_PATH=${CHART_PATH:-charts/ci-runner}
RELEASE_NAME=${RELEASE_NAME:-ci-runner}
NAMESPACE=${NAMESPACE:-default}
RUNNER_BRANCH=${RUNNER_BRANCH:-main}
APP_IMAGE=${APP_IMAGE-}
APP_CHART_PATH=${APP_CHART_PATH-}
APP_RELEASE=${APP_RELEASE-}

if [[ -z "${APP_IMAGE}" ]]; then
  echo "Error: APP_IMAGE environment variable is required." >&2
  exit 1
fi

if [[ -z "${APP_CHART_PATH}" ]]; then
  echo "Error: APP_CHART_PATH environment variable is required." >&2
  exit 1
fi

if [[ -z "${APP_RELEASE}" ]]; then
  echo "Error: APP_RELEASE environment variable is required." >&2
  exit 1
fi

detect_container_runtime() {
  if [[ -n "${CONTAINER_RUNTIME-}" ]]; then
    if command -v "${CONTAINER_RUNTIME}" >/dev/null 2>&1; then
      echo "${CONTAINER_RUNTIME}"
      return 0
    else
      echo "Error: specified CONTAINER_RUNTIME '${CONTAINER_RUNTIME}' not found in PATH." >&2
      return 1
    fi
  fi

  if command -v docker >/dev/null 2>&1; then
    echo docker
  elif command -v podman >/dev/null 2>&1; then
    echo podman
  else
    echo "Error: neither docker nor podman found in PATH. Set CONTAINER_RUNTIME if installed elsewhere." >&2
    return 1
  fi
}

CONTAINER_RUNTIME=$(detect_container_runtime)
echo "Using container runtime: ${CONTAINER_RUNTIME}" 

IMAGE_REPO="${REGISTRY%/}/${IMAGE_NAME}"
FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

echo "Building image ${FULL_IMAGE}..."
"${CONTAINER_RUNTIME}" build -t "${FULL_IMAGE}" .

echo "Pushing image ${FULL_IMAGE}..."
"${CONTAINER_RUNTIME}" push "${FULL_IMAGE}"

echo "Deploying Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."
helm upgrade --install "${RELEASE_NAME}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set image.repository="${IMAGE_REPO}" \
  --set image.tag="${IMAGE_TAG}" \
  --set runner.repo="${REPOSITORY}" \
  --set runner.branch="${RUNNER_BRANCH}" \
  --set runner.image="${APP_IMAGE}" \
  --set runner.chartPath="${APP_CHART_PATH}" \
  --set runner.release="${APP_RELEASE}" \
  --set volumes.data.persistentVolumeClaim.enabled=true \
  --set volumes.data.persistentVolumeClaim.storageClass="${STORAGE_CLASS}"

cat <<DEPLOYED

Deployment complete!
- Release: ${RELEASE_NAME}
- Namespace: ${NAMESPACE}
- Image: ${FULL_IMAGE}
- Repository: ${REPOSITORY}
- Branch: ${RUNNER_BRANCH}
- StorageClass: ${STORAGE_CLASS}
DEPLOYED
