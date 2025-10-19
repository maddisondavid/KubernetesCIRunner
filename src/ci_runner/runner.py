"""Core orchestration logic for the build-and-deploy agent."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from . import config, github_client, helm, kubernetes, repository, state

_LOGGER = logging.getLogger(__name__)


class Runner:
    def __init__(self, settings: config.RunnerSettings) -> None:
        self._settings = settings
        self._client = github_client.GitHubClient(
            settings.repo,
            settings.git_token,
            verify_ssl=settings.verify_ssl,
            ca_bundle_path=settings.ca_bundle_path,
        )

    def run(self) -> None:
        kubernetes.load_kube_config(
            verify_ssl=self._settings.verify_ssl,
            ca_bundle_path=self._settings.ca_bundle_path,
        )
        core_api = kubernetes.core_api()
        batch_api = kubernetes.batch_api()

        kubernetes.ensure_namespace(core_api, self._settings.cicd_namespace)
        kubernetes.ensure_namespace(core_api, self._settings.deploy_namespace)

        runner_state = state.load_state(self._settings.state_path)

        while True:
            try:
                self._iteration(batch_api, runner_state)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error: %s", exc)
            time.sleep(self._settings.interval)

    def _iteration(self, batch_api, runner_state: state.RunnerState) -> None:
        latest_commit = self._client.get_latest_commit(self._settings.branch)
        if latest_commit == runner_state.last_commit:
            _LOGGER.info("No new commits on %s", self._settings.branch)
            return

        archive_url = self._client.get_archive_url(latest_commit)
        _LOGGER.info("New commit detected: %s", latest_commit)

        success = self._trigger_build_and_deploy(batch_api, latest_commit, archive_url)
        if success:
            runner_state.last_commit = latest_commit
            state.save_state(self._settings.state_path, runner_state)

    def _trigger_build_and_deploy(self, batch_api, commit: str, archive_url: str) -> bool:
        for attempt in range(1, self._settings.max_retries + 1):
            job_name = None
            try:
                job_name = kubernetes.create_kaniko_job(
                    batch_api=batch_api,
                    settings=self._settings,
                    commit=commit,
                    registry_secret=self._settings.registry_secret,
                )
                completed = kubernetes.wait_for_job(
                    batch_api,
                    self._settings.cicd_namespace,
                    job_name,
                )
                if not completed:
                    raise RuntimeError("Kaniko job failed or timed out")

                repo_root, temp_dir = repository.download_and_extract(
                    archive_url,
                    verify_ssl=self._settings.verify_ssl,
                    ca_bundle_path=self._settings.ca_bundle_path,
                )
                try:
                    chart_dir = repo_root / Path(self._settings.chart_path)
                    if not chart_dir.exists():
                        raise RuntimeError(f'Chart path {chart_dir} does not exist in archive')

                    helm.upgrade_release(
                        release=self._settings.release,
                        chart_path=str(chart_dir),
                        namespace=self._settings.deploy_namespace,
                        image=self._settings.image,
                        tag=commit,
                    )
                finally:
                    temp_dir.cleanup()
                return True
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Attempt %s/%s failed: %s", attempt, self._settings.max_retries, exc
                )
                time.sleep(min(self._settings.interval, 30))
            finally:
                if job_name:
                    try:
                        kubernetes.delete_job(batch_api, self._settings.cicd_namespace, job_name)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.debug('Job cleanup already handled')
        return False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = config.load_settings()
    runner = Runner(settings)
    runner.run()


if __name__ == "__main__":
    main()
