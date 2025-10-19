"""Kubernetes interaction helpers."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from kubernetes import client, config
from kubernetes.client import V1DeleteOptions
from kubernetes.client.exceptions import ApiException

_LOGGER = logging.getLogger(__name__)


def load_kube_config() -> None:
    """Load in-cluster config; fall back to local kubeconfig."""

    try:
        config.load_incluster_config()
        _LOGGER.info("Loaded in-cluster Kubernetes configuration")
        _ensure_incluster_ca()
    except config.ConfigException:
        config.load_kube_config()
        _LOGGER.info("Loaded local kubeconfig configuration")


def _ensure_incluster_ca() -> None:
    """Ensure the Kubernetes client has a usable CA certificate path."""

    cfg = client.Configuration.get_default_copy()
    ca_path = cfg.ssl_ca_cert
    if ca_path and os.path.exists(ca_path):
        return

    fallback_paths = [
        "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
        "/var/run/secrets/kerbernetes.io/serviceaccount/ca.crt",
    ]

    for path in fallback_paths:
        if os.path.exists(path):
            cfg.ssl_ca_cert = path
            client.Configuration.set_default(cfg)
            _LOGGER.info("Using Kubernetes CA certificate from %s", path)
            return

    if ca_path:
        _LOGGER.warning(
            "Kubernetes CA certificate at %s is not accessible; TLS verification may fail",
            ca_path,
        )
    else:
        _LOGGER.warning(
            "Kubernetes CA certificate path is unset; checked %s", ", ".join(fallback_paths)
        )


def ensure_namespace(api: client.CoreV1Api, name: str) -> None:
    try:
        api.read_namespace(name)
        return
    except ApiException as exc:
        if exc.status == 403:
            _LOGGER.info(
                "Insufficient RBAC privileges to verify namespace %s; assuming it exists",
                name,
            )
            return
        if exc.status != 404:
            raise
    ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
    try:
        api.create_namespace(ns)
        _LOGGER.info("Namespace %s created", name)
    except ApiException as exc:
        if exc.status == 409:
            _LOGGER.info("Namespace %s already exists", name)
            return
        if exc.status == 403:
            _LOGGER.warning(
                "Insufficient RBAC privileges to create namespace %s; continuing without creating",
                name,
            )
            return
        raise


def create_kaniko_job(
    batch_api: client.BatchV1Api,
    settings,
    commit: str,
    registry_secret: Optional[str],
) -> str:
    job_name = f"kaniko-{commit[:7]}"
    annotations = {"commit": commit}

    context = f"git://github.com/{settings.repo}.git#{commit}"

    args = [
        "--dockerfile=Dockerfile",
        f"--context={context}",
        f"--destination={settings.image}:{commit}",
        f"--destination={settings.image}:{settings.branch}-latest",
        "--snapshotMode=time",
    ]

    env = []
    if settings.git_token:
        env.extend(
            [
                client.V1EnvVar(name="GIT_HTTPS_USERNAME", value="token"),
                client.V1EnvVar(name="GIT_HTTPS_PASSWORD", value=settings.git_token),
            ]
        )

    volume_mounts = []
    volumes = []

    if registry_secret:
        volume_mounts.append(
            client.V1VolumeMount(
                name="registry-creds", mount_path="/kaniko/.docker"
            )
        )
        volumes.append(
            client.V1Volume(
                name="registry-creds",
                secret=client.V1SecretVolumeSource(
                    secret_name=registry_secret,
                    items=[
                        client.V1KeyToPath(
                            key=".dockerconfigjson", path="config.json"
                        )
                    ],
                ),
            )
        )

    container = client.V1Container(
        name="kaniko",
        image="gcr.io/kaniko-project/executor:latest",
        args=args,
        env=env,
        volume_mounts=volume_mounts,
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"job-name": job_name}, annotations=annotations),
        spec=client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            service_account_name="deployer",
            volumes=volumes,
        ),
    )

    job_spec = client.V1JobSpec(template=template, backoff_limit=0)
    job = client.V1Job(
        metadata=client.V1ObjectMeta(name=job_name, annotations=annotations),
        spec=job_spec,
    )

    batch_api.create_namespaced_job(namespace=settings.cicd_namespace, body=job)
    _LOGGER.info("Kaniko job %s created", job_name)
    return job_name


def wait_for_job(
    batch_api: client.BatchV1Api,
    namespace: str,
    job_name: str,
    timeout: int = 1800,
    poll_interval: int = 10,
) -> bool:
    """Wait until the job succeeds or fails."""

    start = time.time()
    while time.time() - start < timeout:
        job = batch_api.read_namespaced_job(job_name, namespace)
        if job.status.succeeded:
            _LOGGER.info("Job %s succeeded", job_name)
            return True
        if job.status.failed:
            _LOGGER.error("Job %s failed", job_name)
            return False
        time.sleep(poll_interval)
    _LOGGER.error("Job %s timed out after %s seconds", job_name, timeout)
    return False


def delete_job(batch_api: client.BatchV1Api, namespace: str, job_name: str) -> None:
    try:
        batch_api.delete_namespaced_job(
            name=job_name,
            namespace=namespace,
            body=V1DeleteOptions(propagation_policy="Foreground"),
        )
        _LOGGER.info("Job %s deleted", job_name)
    except ApiException as exc:
        if exc.status != 404:
            _LOGGER.warning("Failed to delete job %s: %s", job_name, exc)


def core_api() -> client.CoreV1Api:
    return client.CoreV1Api()


def batch_api() -> client.BatchV1Api:
    return client.BatchV1Api()


def create_namespace_if_missing(namespace: str) -> None:
    api = core_api()
    ensure_namespace(api, namespace)

