# Build-and-Deploy Agent — Product Requirements Document

## 1. Purpose
The Build-and-Deploy Agent automates continuous integration and deployment for Kubernetes environments without relying on external CI/CD infrastructure.  
It runs **entirely within the cluster**, detecting new commits to a GitHub repository, building the application image with Kaniko, pushing it to a registry, and deploying the new version via Helm.

This enables self-updating development or test clusters that stay synchronized with the main development branch.

---

## 2. Objectives
- Provide an in-cluster automation loop that reacts to source-control updates.
- Remove dependency on external CI/CD services or Docker daemons.
- Ensure every commit to the main branch can be built and deployed reproducibly.
- Offer clear separation between build (Kaniko Job) and deploy (Helm upgrade).
- Run securely under restricted Kubernetes RBAC and ServiceAccounts.

---

## 3. Key Outcomes
- Code, Dockerfile, and Helm chart live in the same GitHub repository.
- On any new commit to the configured branch:
  - The cluster automatically builds a new image tagged with the commit SHA.
  - The image is pushed to the configured container registry.
  - The Helm release is upgraded to use that image.
- Rollbacks are handled by Helm’s built-in `--atomic` behaviour.
- No external credentials or kubeconfigs leave the cluster.

---

## 4. Users and Use Cases
**Primary Users**
- Platform engineers who maintain development or staging clusters.
- Architects or developers who want self-updating test environments.

**Typical Use Cases**
- Automatically deploy latest `main` branch to a shared dev cluster.
- Validate Helm chart integrity and image build correctness after every merge.
- Provide “live preview” environments for review.

---

## 5. High-Level Architecture
| Component | Responsibility |
|------------|----------------|
| **Runner Pod** | Monitors the Git branch, triggers build and deploy workflows. |
| **Kaniko Job** | Builds the Docker image from the repository and pushes to registry. |
| **Helm Client** | Upgrades or installs the target Helm release. |
| **ServiceAccount + RBAC** | Provides scoped permissions for job creation and application deployment. |
| **Registry Secret** | Supplies authentication for pushing images. |

All components reside in-cluster within a namespace such as `cicd`.

---

## 6. Functional Requirements
1. **Change Detection**
   - The agent must detect new commits on a specific GitHub branch.
   - Polling frequency configurable via environment variable.

2. **Image Build**
   - Uses Kaniko to build images based on the repository’s Dockerfile.
   - Supports both public and private repositories.
   - Tags each image with the commit SHA and `<branch>-latest`.

3. **Registry Push**
   - Pushes built images to a container registry (e.g., GHCR, ECR, Harbor).
   - Authenticates using a Kubernetes secret of type `dockerconfigjson`.

4. **Helm Deployment**
   - Clones the same repository to access the Helm chart.
   - Executes a Helm upgrade/install using the newly built image tag.
   - Creates namespaces automatically if not present.

5. **State Management**
   - Persists last deployed commit SHA to avoid redundant builds.

6. **Security**
   - Runs under a restricted ServiceAccount.
   - Uses in-cluster authentication and never exports kubeconfigs.
   - Cleans up build Jobs automatically after completion.

---

## 7. Non-Functional Requirements
| Attribute | Requirement |
|------------|-------------|
| **Performance** | Should detect and deploy within 5 minutes of new commit. |
| **Scalability** | Supports multiple concurrent runners for different repos. |
| **Reliability** | Builds retried up to 3 times on transient errors. |
| **Observability** | Logs available via `kubectl logs`; optional metrics in future. |
| **Security** | No privileged containers; no Docker daemon. |

---

## 8. Deployment Model
- The runner is deployed as a **Kubernetes Deployment** with one replica per repository.
- Each runner operates in its own namespace (e.g., `cicd`) and has:
  - A `ServiceAccount` (`deployer`)
  - Role/RoleBindings to create Jobs and perform Helm actions
  - Registry credentials secret
- Kaniko Jobs are ephemeral, run in the same namespace, and auto-delete after success.

---

## 9. Configuration Parameters
| Name | Description |
|------|--------------|
| `REPO` | GitHub repository name (`org/repo`) |
| `BRANCH` | Branch to monitor |
| `IMAGE` | Full registry path for built images |
| `CHART_PATH` | Relative path to Helm chart within repo |
| `RELEASE` | Helm release name |
| `CICD_NS` | Namespace for build jobs |
| `DEPLOY_NS` | Namespace for deployed workloads |
| `INTERVAL` | Polling interval (seconds) |

Optional:
- `GIT_TOKEN` (if repository is private)

---

## 10. Security and Access
- Runner pod authenticates to the API server via its ServiceAccount token.
- Kaniko uses only the registry secret for image push.
- GitHub access tokens stored as Kubernetes secrets.
- No external network access required beyond GitHub and registry endpoints.

---

## 11. Operational Behaviour
1. **Startup** – runner validates environment variables, ensures connectivity.
2. **Polling Loop** – checks GitHub for new commit.
3. **Build Phase** – creates Kaniko Job; waits for completion.
4. **Deploy Phase** – clones repo, runs Helm upgrade.
5. **Cleanup** – deletes Job, updates state file.
6. **Idle** – sleeps until next poll.

Failures (network, build errors, Helm failures) are logged and retried automatically on next interval.

---

## 12. Monitoring and Troubleshooting
- `kubectl logs deploy/build-deploy-agent -n cicd` – runner activity.
- `kubectl get jobs -n cicd` – list build jobs.
- `kubectl logs job/kaniko-<sha> -n cicd` – Kaniko build output.
- `helm history <release> -n <namespace>` – deployment history.

---

## 13. Future Enhancements
- Replace polling with GitHub webhooks.
- Support multiple branches per runner via CRD configuration.
- Add Slack/webhook notifications.
- Export Prometheus metrics for build/deploy durations.
- Introduce configurable approval gates for production environments.

---

## 14. Success Criteria
- Fully automated build-and-deploy loop functioning without manual triggers.
- No privileged containers or external CI dependencies.
- Builds traceable to commit SHAs.
- Mean deployment latency <5 minutes per commit.
- Zero leaked credentials outside cluster.

---

## 15. Deliverables
- Docker image: `your-registry/kaniko-helm-runner:latest`
- Kubernetes manifests:
  - Namespace, ServiceAccount, Roles/RoleBindings
  - Registry Secret
  - Runner Deployment
- Documentation (this file)

---

## 16. Summary
The Build-and-Deploy Agent is a self-contained CI/CD loop for Kubernetes clusters.  
It gives development teams continuous delivery capabilities with minimal infrastructure, ensuring that every commit to the main branch automatically results in a fresh deployment inside the cluster — secure, reproducible, and fully autonomous.