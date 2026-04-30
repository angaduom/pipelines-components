import os

DEFAULT_AUTOML_IMAGE = "quay.io/opendatahub/odh-automl:odh-stable"
DEFAULT_AUTORAG_IMAGE = "quay.io/angsinghorg/odh-autorag:quickfix-kfp-20260430-1"

AUTOML_IMAGE = os.getenv("RELATED_IMAGE_MPI_AUTOML_RUNTIME", DEFAULT_AUTOML_IMAGE)
AUTORAG_IMAGE = os.getenv("RELATED_IMAGE_MPI_AUTORAG_RUNTIME", DEFAULT_AUTORAG_IMAGE)
