# AutoML integration tests (RHOAI)

High-level tests that run the **AutoGluon tabular training pipeline** (AutoML) on a **Red Hat OpenShift AI (RHOAI)** cluster and validate success and artifacts. These tests live under `pipelines/training/automl/autogluon_tabular_training_pipeline/tests/`. When the required environment variables are not set, the AutoML integration tests are **skipped** (unit tests in this directory still run).

## Requirements

- RHOAI cluster with Data Science Pipelines enabled and a pipeline server running.
- S3-compatible storage (e.g. MinIO or AWS S3) for AutoML pipeline test data and artifacts.
- Optional: `kubectl` access (or in-cluster config) to create a test project (namespace) and S3 connection secret.

## Environment variables

Set these to enable the AutoML integration tests; otherwise they are skipped. You can set them in the shell or via a **`.env`** file in the repo root or in this directory (`tests/`). Copy `.env.template` to `.env` and fill in your values. The module `integration_config.py` loads `.env` at import time and builds the config; the same config is used for both the skip condition and the fixtures.

| Variable | Required | Description |
|----------|----------|-------------|
| `RHOAI_URL` | Yes | Base URL of the pipeline API (e.g. `https://api.example.com`). |
| `RHOAI_KFP_URL` | Yes | KFP server URL where the client connects (e.g. `https://ds-pipeline-dspa-<project>.apps...`). |
| `RHOAI_TOKEN` | Yes | Auth token for the pipeline API (e.g. from RHOAI dashboard or service account). |
| `RHOAI_PROJECT_NAME` | No | Project/namespace name for the test run (default: `kfp-integration-test`). |
| `AWS_S3_ENDPOINT` | Yes | S3-compatible endpoint URL. |
| `AWS_ACCESS_KEY_ID` | Yes | S3 access key. |
| `AWS_SECRET_ACCESS_KEY` | Yes | S3 secret key. |
| `AWS_DEFAULT_REGION` | No | S3 region (default: `us-east-1`). |
| `RHOAI_TEST_DATA_BUCKET` | Yes | Bucket used for test data upload and pipeline input. |
| `RHOAI_TEST_ARTIFACTS_BUCKET` | No | Bucket where pipeline artifacts are written (default: same as data bucket). |
| `RHOAI_TEST_S3_SECRET_NAME` | No | Name of the Kubernetes secret holding S3 credentials in the project (default: `s3-connection`). |
| `RHOAI_PIPELINE_RUN_TIMEOUT` | No | Timeout in seconds for waiting on a run (default: `3600`). |

All required variables must be set for the AutoML integration tests to run; if any is missing, `RHOAI_INTEGRATION_CONFIG` is `None` and the tests are skipped with a reason pointing to `.env.template`.

## Test layout

- **`integration_config.py`** – Loads `.env`, defines `get_rhoai_config()`, and exposes `RHOAI_INTEGRATION_CONFIG` (single source of truth for AutoML integration skip and fixtures).
- **`conftest.py`** – Pytest fixtures for the AutoML pipeline tests; adds the `tests` directory to `sys.path` so `integration_config` can be imported.
- **`test_pipeline_integration.py`** – AutoML integration test class marked with `@pytest.mark.integration` and `@pytest.mark.skipif(RHOAI_INTEGRATION_CONFIG is None, ...)`.

## Fixtures (conftest.py)

Fixtures used by the AutoML pipeline integration tests:

| Fixture | Scope | Description |
|---------|--------|-------------|
| `rhoai_integration_config` | session | Config dict from env (or `None`). |
| `integration_available` | session | `True` when config is present. |
| `s3_client` | session | Boto3 S3 client for uploads and artifact checks; `None` if config missing or boto3 unavailable. |
| `rhoai_project` | session | Ensures Kubernetes namespace and S3 connection secret exist; skips if kubeconfig/in-cluster config unavailable. |
| `test_data_uploaded` | session | Uploads minimal regression and classification CSV data to S3; returns bucket/key dict or `None`. |
| `kfp_client` | session | KFP client pointing at RHOAI (`rhoai_kfp_url`) with token auth; `None` if config missing. |
| `compiled_pipeline_path` | session | Temp path to compiled AutoGluon tabular training pipeline YAML. |
| `pipeline_run_timeout` | function | Timeout in seconds (from `RHOAI_PIPELINE_RUN_TIMEOUT` or `3600`). |

## Test scenarios

1. **Regression** – Runs the AutoML pipeline with `task_type=regression`, label `price`, waits for completion, then asserts success and presence of leaderboard, `.pkl` models, and `.ipynb` notebooks in the artifact store.
2. **Classification** – Same flow with `task_type=binary` and label `target`.

## Running the tests

Install dependencies for the AutoML integration tests (includes base test deps; see `test_automl` extra in `pyproject.toml`):

```bash
uv sync --extra test_automl
# or: pip install -e ".[test_automl]"
```

Run only AutoML integration tests (from repo root):

```bash
pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/test_pipeline_integration.py -m integration -v
```

Run all AutoML pipeline tests (unit + integration; integration tests skip if env not set):

```bash
pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/ -v
```

Exclude AutoML integration tests:

```bash
pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/ -m "not integration" -v
```

To avoid the "Unknown pytest.mark.integration" warning, register the mark in `pyproject.toml` under `[tool.pytest.ini_options]`:

```ini
markers = ["integration: AutoML (RHOAI) integration tests (deselect with -m 'not integration')"]
```

## Pipeline server

The tests assume a pipeline server is already running in the cluster for the chosen project/namespace. RHOAI typically creates the server when you create a Data Science Project and enable pipelines. The fixture `rhoai_project` only creates the namespace and S3 secret; it does not start the AutoML pipeline server.
