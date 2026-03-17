"""High-level integration tests for AutoGluon tabular training pipeline on RHOAI.

These tests require a Red Hat OpenShift AI (RHOAI) cluster with Data Science Pipelines
enabled, and environment variables set for cluster URL, credentials, and S3 storage.
See the conftest.py in this directory for required env vars. When not set, tests
are skipped. You can set vars via a .env file (see .env.template).

Scenarios:
- Classification: run pipeline with task_type=binary (or multiclass), validate success
  and artifacts (leaderboard, .pkl models, .ipynb notebooks).
- Regression: run pipeline with task_type=regression, same validations.
"""

import secrets
from datetime import datetime, timezone

import pytest

from integration_config import RHOAI_INTEGRATION_CONFIG

# Pipeline display name in KFP (from pipeline decorator)
PIPELINE_DISPLAY_NAME = "autogluon-tabular-training-pipeline"


def _make_automl_run_name():
    """Return a run name: automl-test-<6 hex chars>-<YYYYMMDD-HHMMSS>."""
    hex_part = secrets.token_hex(3)  # 3 bytes -> 6 hex chars
    time_part = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"automl-test-{hex_part}-{time_part}"


def _run_pipeline_and_wait(client, compiled_path, arguments, timeout):
    """Submit pipeline run and wait for completion; return run_id and run detail."""
    run_name = _make_automl_run_name()
    run = client.create_run_from_pipeline_package(
        compiled_path,
        arguments=arguments,
        run_name=run_name,
    )
    run_id = run.run_id
    detail = client.wait_for_run_completion(run_id, timeout=timeout)
    return run_id, detail


def _run_succeeded(detail):
    """Return True if the run finished successfully."""
    run = getattr(detail, "run", detail)
    state = getattr(run, "state", None)
    if state is None and hasattr(run, "status"):
        state = getattr(run.status, "state", None)
    if isinstance(state, str):
        return state.upper() == "SUCCEEDED"
    return False


def _find_artifacts_in_s3(s3_client, bucket, prefix):
    """
    List object keys under prefix; return lists of keys ending in .pkl, .ipynb,
    and keys containing 'leaderboard' or 'html_artifact'.
    """
    pkl_keys = []
    ipynb_keys = []
    leaderboard_keys = []
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.endswith(".pkl"):
                    pkl_keys.append(key)
                elif key.endswith(".ipynb"):
                    ipynb_keys.append(key)
                elif "leaderboard" in key.lower() or "html_artifact" in key.lower():
                    leaderboard_keys.append(key)
    except Exception:
        pass
    return pkl_keys, ipynb_keys, leaderboard_keys


@pytest.mark.integration
@pytest.mark.skipif(
    RHOAI_INTEGRATION_CONFIG is None,
    reason="RHOAI integration env not set (set RHOAI_URL, RHOAI_TOKEN, S3 vars; use SA token for Jenkins; see .env.template)",
)
class TestAutogluonPipelineIntegration:
    """Integration tests running the pipeline on RHOAI and validating outcomes."""

    def test_autogluon_pipeline_regression(
        self,
        rhoai_integration_config,
        rhoai_project,
        test_data_uploaded,
        kfp_client,
        compiled_pipeline_path,
        pipeline_run_timeout,
        s3_client,
    ):
        """Run pipeline for regression task; assert success and presence of artifacts."""
        if not test_data_uploaded or not kfp_client:
            pytest.skip("Integration prerequisites not available")
        data = test_data_uploaded
        config = rhoai_integration_config
        secret_name = config["s3_secret_name"]

        arguments = {
            "train_data_secret_name": secret_name,
            "train_data_bucket_name": data["regression_bucket"],
            "train_data_file_key": data["regression_key"],
            "label_column": "price",
            "task_type": "regression",
            "top_n": 2,
        }
        run_id, detail = _run_pipeline_and_wait(
            kfp_client, compiled_pipeline_path, arguments, pipeline_run_timeout
        )
        assert _run_succeeded(detail), (
            f"Pipeline run {run_id} did not succeed; state={getattr(detail, 'run', detail)}"
        )

        if s3_client and config.get("s3_bucket_artifacts"):
            bucket = config["s3_bucket_artifacts"]
            prefix = f"{PIPELINE_DISPLAY_NAME}/{run_id}"
            pkl_keys, ipynb_keys, leaderboard_keys = _find_artifacts_in_s3(
                s3_client, bucket, prefix
            )
            assert len(pkl_keys) >= 1, (
                f"Expected at least one .pkl model artifact under {prefix}; found {pkl_keys}"
            )
            assert len(ipynb_keys) >= 1, (
                f"Expected at least one .ipynb notebook under {prefix}; found {ipynb_keys}"
            )
            assert len(leaderboard_keys) >= 1, (
                f"Expected leaderboard/html artifact under {prefix}; found {leaderboard_keys}"
            )

    def test_autogluon_pipeline_classification(
        self,
        rhoai_integration_config,
        rhoai_project,
        test_data_uploaded,
        kfp_client,
        compiled_pipeline_path,
        pipeline_run_timeout,
        s3_client,
    ):
        """Run pipeline for classification task; assert success and presence of artifacts."""
        if not test_data_uploaded or not kfp_client:
            pytest.skip("Integration prerequisites not available")
        data = test_data_uploaded
        config = rhoai_integration_config
        secret_name = config["s3_secret_name"]

        arguments = {
            "train_data_secret_name": secret_name,
            "train_data_bucket_name": data["classification_bucket"],
            "train_data_file_key": data["classification_key"],
            "label_column": "target",
            "task_type": "binary",
            "top_n": 2,
        }
        run_id, detail = _run_pipeline_and_wait(
            kfp_client, compiled_pipeline_path, arguments, pipeline_run_timeout
        )
        assert _run_succeeded(detail), (
            f"Pipeline run {run_id} did not succeed; state={getattr(detail, 'run', detail)}"
        )

        if s3_client and config.get("s3_bucket_artifacts"):
            bucket = config["s3_bucket_artifacts"]
            prefix = f"{PIPELINE_DISPLAY_NAME}/{run_id}"
            pkl_keys, ipynb_keys, leaderboard_keys = _find_artifacts_in_s3(
                s3_client, bucket, prefix
            )
            assert len(pkl_keys) >= 1, (
                f"Expected at least one .pkl model artifact under {prefix}; found {pkl_keys}"
            )
            assert len(ipynb_keys) >= 1, (
                f"Expected at least one .ipynb notebook under {prefix}; found {ipynb_keys}"
            )
            assert len(leaderboard_keys) >= 1, (
                f"Expected leaderboard/html artifact under {prefix}; found {leaderboard_keys}"
            )
