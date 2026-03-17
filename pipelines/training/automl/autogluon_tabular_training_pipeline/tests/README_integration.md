# AutoML integration tests (RHOAI)

High-level tests that run the **AutoGluon tabular training pipeline** (AutoML) on a **Red Hat OpenShift AI (RHOAI)** cluster and validate success and artifacts. These tests live under `pipelines/training/automl/autogluon_tabular_training_pipeline/tests/`. When the required environment variables are not set, the AutoML integration tests are **skipped** (unit tests in this directory still run).

## Requirements

- RHOAI cluster with Data Science Pipelines enabled and a pipeline server running.
- S3-compatible storage (e.g. MinIO or AWS S3) for AutoML pipeline test data and artifacts.
- Optional: `kubectl/oc` access (or in-cluster config) to create a test project (namespace) and S3 connection secret.

## Environment variables

Set these to enable the AutoML integration tests; otherwise they are skipped. You can set them in the shell or via a **`.env`** file in the repo root or in this directory (`tests/`). Copy `.env.template` to `.env` and fill in your values. The module `integration_config.py` loads `.env` at import time and builds the config; the same config is used for both the skip condition and the fixtures.

| Variable | Required | Description |
|----------|----------|-------------|
| `RHOAI_URL` | Yes | Base URL of the OCP cluster (e.g. `https://api.example.com`). |
| `RHOAI_KFP_URL` | No | KFP server URL where the client connects (e.g. `https://ds-pipeline-dspa-<project>.apps...`). |
| `RHOAI_TOKEN` | Yes | API token; use a **service account token** for Jenkins/CI (long-lived, no oc or kubeconfig). |
| `RHOAI_PROJECT_NAME` | No | RHOAI Project/namespace name for the test run (default: `kfp-integration-test`). |
| `AWS_S3_ENDPOINT` | Yes | S3-compatible endpoint URL. |
| `AWS_ACCESS_KEY_ID` | Yes | S3 access key. |
| `AWS_SECRET_ACCESS_KEY` | Yes | S3 secret key. |
| `AWS_DEFAULT_REGION` | No | S3 region (default: `us-east-1`). |
| `RHOAI_TEST_DATA_BUCKET` | Yes | Bucket used for test data upload and pipeline input. |
| `RHOAI_TEST_ARTIFACTS_BUCKET` | No | Bucket where pipeline artifacts are written (default: same as data bucket). |
| `RHOAI_TEST_S3_SECRET_NAME` | No | Name of the Kubernetes secret holding S3 credentials in the project (default: `s3-connection`). |
| `RHOAI_PIPELINE_RUN_TIMEOUT` | No | Timeout in seconds for waiting on a run (default: `3600`). |

All required variables must be set for the AutoML integration tests to run; if any is missing, `RHOAI_INTEGRATION_CONFIG` is `None` and the tests are skipped with a reason pointing to `.env.template`.

### Authentication (service account token for Jenkins / CI)

Set **`RHOAI_TOKEN`** to an OpenShift API token. Follow [Scenario 1](#scenario-1-automatic-project-creation) (automatic project creation) or [Scenario 2](#scenario-2-no-automatic-project-creation-existing-project) (existing project) below to create the ServiceAccount and obtain a token; in Jenkins, store the token as a secret and bind it to `RHOAI_TOKEN`. Service account tokens are long-lived; no `oc` or kubeconfig is needed at test time.

### Creating a service account for the tests

Choose **one** of the two scenarios below. Both produce a token for `RHOAI_TOKEN`; no `oc` or kubeconfig is needed when running the tests.

---

#### Scenario 1: Automatic project creation

The test creates the project via OpenShift ProjectRequest (same as `oc new-project`). Set `RHOAI_PROJECT_NAME` to the project name to create; it can be a new name each run (e.g. in CI). The ServiceAccount can live in any namespace (e.g. `default`).

**1. Create the ServiceAccount** (in any namespace):

```bash
export SA_NAMESPACE=default
export SA_NAME=kfp-integration-tests
oc create serviceaccount "${SA_NAME}" -n "${SA_NAMESPACE}"
```

**2. Grant self-provisioner** so the SA can create projects:

```bash
oc adm policy add-cluster-role-to-user self-provisioner -z "${SA_NAME}" -n "${SA_NAMESPACE}"
```

**3. (Optional) If your cluster does not grant the ProjectRequest creator admin** in the new project, the test will create a RoleBinding to grant the SA admin. For that, the SA needs permission to create RoleBindings. A cluster admin runs once:

```bash
oc create clusterrole kfp-integration-tests-rolebinding-creator \
  --verb=create,get,update,patch \
  --resource=rolebindings.rbac.authorization.k8s.io

oc adm policy add-cluster-role-to-user kfp-integration-tests-rolebinding-creator \
  -z "${SA_NAME}" -n "${SA_NAMESPACE}"
```

**4. Create a token** and configure:

```bash
oc create token "${SA_NAME}" -n "${SA_NAMESPACE}" --duration=8760h
```

Set `RHOAI_TOKEN` to the printed token and `RHOAI_PROJECT_NAME` to the project name the test should create (e.g. `automl-integration-tests`). Do not create that project beforehand.

---

#### Scenario 2: No automatic project creation (existing project)

The project already exists (e.g. created with `oc new-project` or an existing RHOAI Data Science project). The ServiceAccount is created **in that project** and granted **edit** in that project.

**1. Create or use the project:**

```bash
export RHOAI_PROJECT_NAME=automl-integration-tests
oc new-project "${RHOAI_PROJECT_NAME}"
```

**2. Create the ServiceAccount in that project:**

```bash
oc create serviceaccount kfp-integration-tests -n "${RHOAI_PROJECT_NAME}"
```

**3. Grant edit in the project** (Secrets, DSPA CR, Routes):

```bash
oc adm policy add-role-to-user edit -z kfp-integration-tests -n "${RHOAI_PROJECT_NAME}"
```

**4. Create a token** and configure:

```bash
oc create token kfp-integration-tests -n "${RHOAI_PROJECT_NAME}" --duration=8760h
```

Set `RHOAI_TOKEN` to the printed token and `RHOAI_PROJECT_NAME` to that project name. No self-provisioner or extra cluster roles are required.

---

#### Token and test configuration (both scenarios)

- Create token: `oc create token <sa-name> -n <sa-namespace> [--duration=8760h]`
- If the token is in a Secret: `oc get secret <name> -n <namespace> -o jsonpath='{.data.token}' | base64 -d`
- Set `RHOAI_TOKEN` and `RHOAI_PROJECT_NAME` in `.env` or Jenkins; no `oc` or kubeconfig needed at test time.

## Test layout

- **`integration_config.py`** – Loads `.env`, defines `get_rhoai_config()`, and exposes `RHOAI_INTEGRATION_CONFIG` (single source of truth for AutoML integration skip and fixtures).
- **`conftest.py`** – Pytest fixtures for the AutoML pipeline tests; adds the `tests` directory to `sys.path` so `integration_config` can be imported. When integration config is set, a **temporary kubeconfig** is created from `RHOAI_URL` and `RHOAI_TOKEN`; the Kubernetes client uses this file instead of `~/.kube/config`.
- **`test_pipeline_integration.py`** – AutoML integration test class marked with `@pytest.mark.integration` and `@pytest.mark.skipif(RHOAI_INTEGRATION_CONFIG is None, ...)`.

## Fixtures (conftest.py)

Fixtures used by the AutoML pipeline integration tests:

| Fixture | Scope | Description |
|---------|--------|-------------|
| `rhoai_integration_config` | session | Config dict from env (or `None`). |
| `integration_available` | session | `True` when config is present. |
| `temp_kubeconfig_path` | session | Temp kubeconfig file built from `RHOAI_URL` and `RHOAI_TOKEN`; used by all Kubernetes API calls so the default `~/.kube/config` is not used. Yields path or `None`. |
| `s3_client` | session | Boto3 S3 client for uploads and artifact checks; `None` if config missing or boto3 unavailable. |
| `rhoai_project` | session | Ensures Kubernetes namespace and S3 connection secret exist; skips if kubeconfig/in-cluster config unavailable. |
| `datascience_pipelines_application` | session | Optionally creates a **DataSciencePipelinesApplication** CR in the test namespace (see [Creating a DataSciencePipelinesApplication CR](#creating-a-datasciencepipelinesapplication-cr-dspa)). Yields the CR dict or `None`. |
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

Run only AutoML integration tests (from repo root, change path appropriately if run from somewhere else):

```bash
uv run pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/test_pipeline_integration.py -m integration -v
```

Run all AutoML pipeline tests (unit + integration; integration tests skip if env not set):

```bash
uv run pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/ -v
```

Exclude AutoML integration tests:

```bash
uv run pytest pipelines/training/automl/autogluon_tabular_training_pipeline/tests/ -m "not integration" -v
```

### Running in Jenkins

In the Jenkins job, set environment variables from your credential store (e.g. bind `RHOAI_TOKEN` to a “Secret text” credential holding the service account token):  
`RHOAI_URL`, `RHOAI_TOKEN`, `RHOAI_PROJECT_NAME`, S3 vars (`AWS_S3_ENDPOINT`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `RHOAI_TEST_DATA_BUCKET`), and optionally `RHOAI_KFP_URL`. No `oc` CLI or kubeconfig needed.

To avoid the "Unknown pytest.mark.integration" warning, register the mark in `pyproject.toml` under `[tool.pytest.ini_options]`:

```ini
markers = ["integration: AutoML (RHOAI) integration tests (deselect with -m 'not integration')"]
```

## Pipeline server

The tests assume a pipeline server is already running in the cluster for the chosen project/namespace. RHOAI typically creates the server when you create a Data Science Project and enable pipelines. The fixture `rhoai_project` only creates the namespace and S3 secret; it does not start the AutoML pipeline server.

## Creating a DataSciencePipelinesApplication CR (DSPA)

You can have the test flow **create a DataSciencePipelinesApplication** custom resource (Red Hat OpenShift AI / Open Data Hub) in the test namespace using the Kubernetes Python client (`CustomObjectsApi`). The Data Science Pipelines Operator (DSPO) will reconcile the CR and deploy the pipeline server in that namespace.

1. **Prerequisites:** The Data Science Pipelines Operator (or Open Data Hub operator) must be installed and the `DataSciencePipelinesApplication` CRD must exist on the cluster.
2. **Enable creation:** Set `RHOAI_CREATE_DSPA=true` (or `1`) in your environment or `.env`.
3. **Fixture:** Add the `datascience_pipelines_application` fixture to your test (or a dependent fixture). It runs after `rhoai_project` and creates one CR named `automl-test-dspa` in the same namespace. It yields the created CR dict (or `None` if creation is disabled or fails).
4. **CRD identity:** Defaults are API group `datasciencepipelinesapplications.opendatahub.io`, version `v1alpha1`, plural `datasciencepipelinesapplications`. Override with `RHOAI_DSPA_API_GROUP`, `RHOAI_DSPA_API_VERSION`, `RHOAI_DSPA_PLURAL` if your cluster uses a different CRD.
5. **Spec:** The created CR uses a minimal `spec: {}`; the operator applies defaults. To customize (e.g. external object storage), extend the `body` in `_create_datascience_pipelines_application()` in `conftest.py` or load a spec from env/file.
6. **KFP client URL:** When `RHOAI_CREATE_DSPA=true`, the **KFP client is configured from the OpenShift Route** created by the operator. The test flow lists `route.openshift.io/v1` Route resources in the DSPA namespace, picks the one whose name starts with `RHOAI_DSPA_ROUTE_NAME_PREFIX` (default: `ds-pipeline`), and uses `https://<route.spec.host>` as the API URL. It retries for up to `RHOAI_DSPA_ROUTE_WAIT_TIMEOUT` seconds (default: 300). You do not need to set `RHOAI_KFP_URL` when using DSPA creation unless the route cannot be resolved (e.g. different route name); then set `RHOAI_KFP_URL` as fallback or set `RHOAI_DSPA_ROUTE_NAME_PREFIX` to match your route.

Example test that ensures the DSPA CR exists before running (optional; if you use an existing pipeline server you don't need this):

```python
def test_autogluon_pipeline_regression(
    self,
    rhoai_integration_config,
    rhoai_project,
    datascience_pipelines_application,  # creates CR when RHOAI_CREATE_DSPA=true
    test_data_uploaded,
    kfp_client,
    ...
):
```

After the CR is created, the operator creates an OpenShift Route for the pipeline API. The `kfp_client` fixture waits up to `RHOAI_DSPA_ROUTE_WAIT_TIMEOUT` seconds for that route and configures the KFP client with its URL, so you do not need to set `RHOAI_KFP_URL` when using DSPA creation.
