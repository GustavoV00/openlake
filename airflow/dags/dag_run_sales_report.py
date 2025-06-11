from __future__ import annotations
import pendulum

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator

@dag(
    dag_id="spark_sales_report_static",
    start_date=pendulum.datetime(2025, 6, 11, tz="UTC"),
    schedule=None,
    catchup=False,
    doc_md="Runs a static Spark sales report job.",
    tags=["spark", "kubernetes", "static"],
)
def spark_sales_report_static_dag():
    """
    This DAG runs a completely static Spark job defined in a separate YAML file.
    """
    run_static_spark_report = SparkKubernetesOperator(
        task_id="run_static_sales_report_job",
        namespace="spark-operator", # Namespace where the Spark Operator is running
        # This now points to your static YAML file
        application_file="templates/sales_report_static_job.yaml",
        kubernetes_conn_id="kubernetes_default",
    )

spark_sales_report_static_dag()