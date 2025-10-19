#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/deploy.sh <storage-class-name>

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

REGISTRY=${REGISTRY:-localhost:5000}
IMAGE_NAME=${IMAGE_NAME:-kubernetes-ci-runner}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
CHART_PATH=${CHART_PATH:-charts/ci-runner}
RELEASE_NAME=${RELEASE_NAME:-ci-runner}
NAMESPACE=${NAMESPACE:-default}

IMAGE_REPO="${REGISTRY%/}/${IMAGE_NAME}"
FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

echo "Building Docker image ${FULL_IMAGE}..."
docker build -t "${FULL_IMAGE}" .

echo "Pushing Docker image ${FULL_IMAGE}..."
docker push "${FULL_IMAGE}"

echo "Deploying Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."
helm upgrade --install "${RELEASE_NAME}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set image.repository="${IMAGE_REPO}" \
  --set image.tag="${IMAGE_TAG}" \
  --set volumes.data.persistentVolumeClaim.enabled=true \
  --set volumes.data.persistentVolumeClaim.storageClass="${STORAGE_CLASS}"

cat <<DEPLOYED

Deployment complete!
- Release: ${RELEASE_NAME}
- Namespace: ${NAMESPACE}
- Image: ${FULL_IMAGE}
- StorageClass: ${STORAGE_CLASS}
DEPLOYED
