# Kubernetes CI Runner

The Kubernetes CI Runner is an in-cluster automation agent that detects new commits on a GitHub repository, builds the latest code with Kaniko, pushes the resulting image to a registry, and upgrades a Helm release to deploy the new version. This project implements the requirements described in [`plans/spec.md`](plans/spec.md).

## Features

- Polls a GitHub branch for new commits using the GitHub API.
- Stores the last deployed commit to avoid duplicate work.
- Launches ephemeral Kaniko Kubernetes Jobs to build container images tagged with both the commit SHA and `<branch>-latest`.
- Optionally mounts a registry secret for authenticated pushes.
- Performs a Helm `upgrade --install --atomic` using the freshly built image.
- Automatically creates the build and deploy namespaces if they do not already exist.
- Retries failed build/deploy attempts a configurable number of times.

## Configuration

The runner is configured entirely through environment variables:

| Variable | Description | Required | Default |
| --- | --- | --- | --- |
| `REPO` | GitHub repository (`org/repo`). | ✅ | — |
| `BRANCH` | Branch to monitor. | ❌ | `main` |
| `IMAGE` | Full image repository (e.g. `ghcr.io/org/app`). | ✅ | — |
| `CHART_PATH` | Path to the Helm chart within the checkout. | ✅ | — |
| `RELEASE` | Helm release name. | ✅ | — |
| `CICD_NS` | Namespace for Kaniko build jobs. | ❌ | `cicd` |
| `DEPLOY_NS` | Namespace for deployed workloads. | ❌ | `default` |
| `INTERVAL` | Polling interval in seconds (minimum 5). | ❌ | `300` |
| `MAX_RETRIES` | Build/deploy retries per commit (minimum 1). | ❌ | `3` |
| `GIT_TOKEN` | Personal access token for private repositories. | ❌ | — |
| `REGISTRY_SECRET` | Name of dockerconfigjson secret for registry auth. | ❌ | — |
| `STATE_PATH` | File path for runner state persistence. | ❌ | `/data/runner-state.json` |
| `VERIFY_SSL` | Require TLS certificate verification for Kubernetes and GitHub connections (`false` disables verification). | ❌ | `true` |

## Running Locally

Install dependencies and run the entrypoint:

```bash
pip install -r requirements.txt
python main.py
```

When executed outside of a cluster the runner falls back to the local kubeconfig.

## Kubernetes Deployment

The runner is intended to run as a Kubernetes Deployment. At a minimum you will need:

- A namespace for the runner (for example `cicd`).
- A `ServiceAccount` named `deployer` with permissions to create Jobs in the CI namespace and perform Helm actions in the deployment namespace.
- (Optional) A docker registry secret referenced by `REGISTRY_SECRET` if the registry requires authentication.
- Access to the Helm chart referenced by `CHART_PATH`.

A minimal Deployment manifest might look like:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: build-deploy-runner
  namespace: cicd
spec:
  replicas: 1
  selector:
    matchLabels:
      app: build-deploy-runner
  template:
    metadata:
      labels:
        app: build-deploy-runner
    spec:
      serviceAccountName: deployer
      containers:
        - name: runner
          image: ghcr.io/example/kubernetes-ci-runner:latest
          env:
            - name: REPO
              value: "example/my-app"
            - name: BRANCH
              value: "main"
            - name: IMAGE
              value: "ghcr.io/example/my-app"
            - name: CHART_PATH
              value: "charts/my-app"
            - name: RELEASE
              value: "my-app"
            - name: INTERVAL
              value: "300"
            - name: CICD_NS
              value: "cicd"
            - name: DEPLOY_NS
              value: "my-app"
          volumeMounts:
            - name: state
              mountPath: /data
      volumes:
        - name: state
          emptyDir: {}
```

### Helm Chart

A production-ready Helm chart is available under [`charts/ci-runner`](charts/ci-runner). Set the required `runner` values (`repo`,
`image`, `chartPath`, and `release`) before installing:

```bash
helm install build-deploy-runner charts/ci-runner \
  --namespace cicd --create-namespace \
  --set runner.repo="example/my-app" \
  --set runner.image="ghcr.io/example/my-app" \
  --set runner.chartPath="charts/my-app" \
  --set runner.release="my-app"
```

Adjust `runner.cicdNamespace` and `runner.deployNamespace` if your build or deployment targets use non-default namespaces. The
chart provisions a `ServiceAccount` and namespace-scoped RBAC roles that grant the runner permission to launch Kaniko Jobs in
the CI namespace and perform Helm upgrades in the deployment namespace. Configure `runner.gitTokenSecretName` to reference a
secret containing a `token` key when authenticating to private Git repositories, and enable the optional PersistentVolumeClaim
if you need the runner state to persist across pod restarts.

## Development

The project code lives under `src/ci_runner`. The main entrypoint is `ci_runner/runner.py`, which coordinates configuration loading, GitHub polling, Kaniko job creation, Helm upgrades, and state persistence.

Unit tests are not included in this initial implementation, but the code is structured for straightforward mocking of external dependencies.
