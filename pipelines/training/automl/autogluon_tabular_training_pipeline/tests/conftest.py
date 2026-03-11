"""Pytest fixtures for AutoGluon tabular training pipeline tests."""

import os
import sys
import tempfile
from pathlib import Path

# Ensure this directory is on path so test modules and integration_config can be imported
_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))

import pytest

from integration_config import RHOAI_INTEGRATION_CONFIG, get_rhoai_config

# .env is loaded by integration_config at import time.
# ---------------------------------------------------------------------------
# Integration test configuration (RHOAI + S3 + KFP)
# Set env vars to enable integration tests; otherwise they are skipped.
# ---------------------------------------------------------------------------


def _get_rhoai_config():
    """Build integration config from environment; None if not configured."""
    return get_rhoai_config()


@pytest.fixture(scope="session")
def rhoai_integration_config():
    """Session-scoped RHOAI integration config from env; None if not set."""
    return _get_rhoai_config()


@pytest.fixture(scope="session")
def integration_available(rhoai_integration_config):
    """True if RHOAI integration config is present."""
    return rhoai_integration_config is not None


@pytest.fixture(scope="session")
def s3_client(rhoai_integration_config):
    """Session-scoped S3 client for test data upload (and optional artifact checks)."""
    if rhoai_integration_config is None:
        return None
    try:
        import boto3
    except ImportError:
        pytest.skip("boto3 not installed; install with pip install boto3")
    c = rhoai_integration_config
    return boto3.client(
        "s3",
        endpoint_url=c["s3_endpoint"],
        aws_access_key_id=c["s3_access_key"],
        aws_secret_access_key=c["s3_secret_key"],
        region_name=c["s3_region"],
    )


@pytest.fixture(scope="session")
def rhoai_project(rhoai_integration_config, s3_client):
    """
    Ensure RHOAI test project exists: create Kubernetes namespace and S3 connection secret.

    Requires kubeconfig or in-cluster config so that the test runner can create
    resources. If kubernetes client is not available or creation fails, the
    fixture skips.
    """
    if rhoai_integration_config is None:
        yield None
        return
    project_name = rhoai_integration_config["rhoai_project"]
    secret_name = rhoai_integration_config["s3_secret_name"]
    try:
        from kubernetes import client, config
        from kubernetes.client.rest import ApiException
    except ImportError:
        pytest.skip("kubernetes client not installed; pip install kubernetes")
    try:
        config.load_kube_config()
    except Exception:
        try:
            config.load_incluster_config()
        except Exception:
            pytest.skip("Could not load kubeconfig or in-cluster config")
    v1 = client.CoreV1Api()
    namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=project_name))
    try:
        v1.create_namespace(namespace)
    except ApiException as e:
        if e.status != 409:
            raise
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name=secret_name),
        type="Opaque",
        string_data={
            "AWS_ACCESS_KEY_ID": rhoai_integration_config["s3_access_key"],
            "AWS_SECRET_ACCESS_KEY": rhoai_integration_config["s3_secret_key"],
            "AWS_S3_ENDPOINT": rhoai_integration_config["s3_endpoint"],
            "AWS_DEFAULT_REGION": rhoai_integration_config["s3_region"],
        },
    )
    try:
        v1.create_namespaced_secret(project_name, secret)
    except ApiException as e:
        if e.status != 409:
            v1.replace_namespaced_secret(secret_name, project_name, secret)
    yield project_name


@pytest.fixture(scope="session")
def test_data_uploaded(rhoai_integration_config, s3_client):
    """
    Upload minimal classification and regression CSV data to S3.

    Returns dict with keys: regression_bucket, regression_key, classification_bucket,
    classification_key; or None if integration not configured.
    """
    if rhoai_integration_config is None or s3_client is None:
        return None
    bucket = rhoai_integration_config["s3_bucket_data"]
    prefix = "kfp-integration-test"

    regression_csv = """feature_a,feature_b,price
1.0,2.0,10.5
2.0,3.0,20.0
3.0,4.0,30.5
4.0,5.0,41.0
5.0,6.0,51.5
6.0,7.0,62.0
7.0,8.0,72.5
8.0,9.0,83.0
9.0,10.0,93.5
10.0,11.0,104.0
"""
    classification_csv = """feature_a,feature_b,target
1.0,2.0,0
2.0,3.0,0
3.0,4.0,1
4.0,5.0,1
5.0,6.0,0
6.0,7.0,1
7.0,8.0,1
8.0,9.0,0
9.0,10.0,1
10.0,11.0,1
"""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=f"{prefix}/regression.csv",
            Body=regression_csv.encode("utf-8"),
            ContentType="text/csv",
        )
        s3_client.put_object(
            Bucket=bucket,
            Key=f"{prefix}/classification.csv",
            Body=classification_csv.encode("utf-8"),
            ContentType="text/csv",
        )
    except Exception as e:
        pytest.skip(f"Failed to upload test data to S3: {e}")

    return {
        "regression_bucket": bucket,
        "regression_key": f"{prefix}/regression.csv",
        "classification_bucket": bucket,
        "classification_key": f"{prefix}/classification.csv",
    }


@pytest.fixture(scope="session")
def kfp_client(rhoai_integration_config):
    """Session-scoped KFP client pointing to RHOAI pipeline API."""
    if rhoai_integration_config is None:
        return None
    import kfp

    host = rhoai_integration_config["rhoai_kfp_url"]
    if not host.endswith("/"):
        host = host + "/"

    client = kfp.Client(
        host=host,
        namespace=rhoai_integration_config["rhoai_project"],
        existing_token=rhoai_integration_config.get("rhoai_token"),
    )
    return client


@pytest.fixture(scope="session")
def compiled_pipeline_path():
    """Compile the AutoGluon tabular training pipeline to a temp YAML file."""
    from kfp import compiler

    from ..pipeline import autogluon_tabular_training_pipeline

    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    compiler.Compiler().compile(
        pipeline_func=autogluon_tabular_training_pipeline,
        package_path=path,
    )
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def pipeline_run_timeout():
    """Timeout in seconds for waiting on a pipeline run (override via env)."""
    return int(os.environ.get("RHOAI_PIPELINE_RUN_TIMEOUT", "3600"))
