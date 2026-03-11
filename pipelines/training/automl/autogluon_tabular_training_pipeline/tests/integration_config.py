"""RHOAI integration test config: load .env and build config from environment.

Used by conftest.py (fixtures) and test_pipeline_integration.py (skipif) so
skip logic and fixtures share one source of truth. Import this module instead
of conftest to avoid resolving the repo-root conftest when running tests.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root (cwd) and from this directory
load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env")

RHOAI_URL_ENV = "RHOAI_URL"
RHOAI_KFP_URL_ENV = "RHOAI_KFP_URL"
RHOAI_TOKEN_ENV = "RHOAI_TOKEN"
RHOAI_PROJECT_ENV = "RHOAI_PROJECT_NAME"
S3_ENDPOINT_ENV = "AWS_S3_ENDPOINT"
S3_ACCESS_KEY_ENV = "AWS_ACCESS_KEY_ID"
S3_SECRET_KEY_ENV = "AWS_SECRET_ACCESS_KEY"
S3_REGION_ENV = "AWS_DEFAULT_REGION"
S3_BUCKET_DATA_ENV = "RHOAI_TEST_DATA_BUCKET"
S3_BUCKET_ARTIFACTS_ENV = "RHOAI_TEST_ARTIFACTS_BUCKET"
S3_SECRET_NAME_ENV = "RHOAI_TEST_S3_SECRET_NAME"


def get_rhoai_config():
    """Build integration config from environment; None if not configured."""
    url = os.environ.get(RHOAI_URL_ENV)
    kfp_url = os.environ.get(RHOAI_KFP_URL_ENV)
    token = os.environ.get(RHOAI_TOKEN_ENV)
    project = os.environ.get(RHOAI_PROJECT_ENV)
    endpoint = os.environ.get(S3_ENDPOINT_ENV)
    access = os.environ.get(S3_ACCESS_KEY_ENV)
    secret = os.environ.get(S3_SECRET_KEY_ENV)
    region = os.environ.get(S3_REGION_ENV, "us-east-1")
    bucket_data = os.environ.get(S3_BUCKET_DATA_ENV)
    bucket_artifacts = os.environ.get(S3_BUCKET_ARTIFACTS_ENV)
    secret_name = os.environ.get(S3_SECRET_NAME_ENV, "s3-connection")

    if not all([url, token, endpoint, access, secret, bucket_data]):
        return None
    return {
        "rhoai_url": url.rstrip("/"),
        "rhoai_kfp_url": kfp_url.rstrip("/"),
        "rhoai_token": token,
        "rhoai_project": project or "kfp-integration-test",
        "s3_endpoint": endpoint,
        "s3_access_key": access,
        "s3_secret_key": secret,
        "s3_region": region,
        "s3_bucket_data": bucket_data,
        "s3_bucket_artifacts": bucket_artifacts or bucket_data,
        "s3_secret_name": secret_name,
    }


# Single source of truth for skipif: tests run only when this is not None.
RHOAI_INTEGRATION_CONFIG = get_rhoai_config()
