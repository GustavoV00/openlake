"""M5 smoke DAG: submit the M3 Spark warehouse-smoke job, then verify the row
count through Trino (M4) — orchestrating the manual steps in
jobs/spark/warehouse-smoke.yaml's header comment.

Reads jobs/spark/warehouse-smoke.yaml as the SparkApplication spec (repo-root
git-sync, see gitops/config/airflow/kind.yaml) so the DAG and the
manually-applied manifest never drift.
"""

from __future__ import annotations

import datetime

from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import (
    SparkKubernetesOperator,
)
from airflow.providers.cncf.kubernetes.sensors.spark_kubernetes import (
    SparkKubernetesSensor,
)
from airflow.providers.trino.hooks.trino import TrinoHook
from airflow.sdk import DAG, task

SPARK_APPLICATION_FILE = "jobs/spark/warehouse-smoke.yaml"  # relative to DAGS_FOLDER
SPARK_APPLICATION_NAME = "warehouse-smoke"
SPARK_NAMESPACE = "processing"
TRINO_TABLE = "iceberg.bronze.demo"
EXPECTED_ROWS = 3

with DAG(
    dag_id="warehouse_smoke_dag",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    tags=["m5", "smoke"],
) as dag:
    submit_spark_job = SparkKubernetesOperator(
        task_id="submit_spark_job",
        application_file=SPARK_APPLICATION_FILE,
        namespace=SPARK_NAMESPACE,
        random_name_suffix=False,
        delete_on_termination=False,
    )

    wait_for_spark_job = SparkKubernetesSensor(
        task_id="wait_for_spark_job",
        application_name=SPARK_APPLICATION_NAME,
        namespace=SPARK_NAMESPACE,
        attach_log=True,
    )

    @task
    def check_trino_row_count() -> None:
        # Uses the "trino_default" connection — create it in the Airflow UI/CLI
        # (Admin > Connections): host trino.query.svc.cluster.local, port 8080,
        # schema/catalog iceberg/bronze, no auth. Not wired via chart values.
        count = TrinoHook().get_first(f"SELECT count(*) FROM {TRINO_TABLE}")[0]
        print(f"TRINO CHECK: {TRINO_TABLE} has {count} rows")
        assert count == EXPECTED_ROWS, f"expected {EXPECTED_ROWS} rows, got {count}"

    submit_spark_job >> wait_for_spark_job >> check_trino_row_count()
