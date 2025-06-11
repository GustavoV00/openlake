from __future__ import annotations
import pendulum

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator

# This constant can stay here for clarity
SPARK_SCRIPT_PATH = "s3a://spark-apps/spark-test.py"

@dag(
    dag_id="spark_sales_report_generator_v2",
    start_date=pendulum.datetime(2025, 6, 11, tz="UTC"),
    schedule=None,
    catchup=False,
    doc_md="Runs a Spark sales report job using a YAML template from the filesystem.",
    tags=["spark", "kubernetes", "reporting"],
    # params={
    #     "spark_job_namespace": "spark-job",
    #     "minio_endpoint_url": "http://minio.minio:9000",
    #     "spark_image": "localhost:5000/spark-s3:3.5.1",
    #     "main_application_file": SPARK_SCRIPT_PATH, 
    # },
)
def spark_sales_report_dag_v2():
    """
    This DAG defines a task to run the Spark sales report job.
    It uses a clean, templated approach for the SparkApplication definition.
    """
    run_spark_report = SparkKubernetesOperator(
        task_id="run_sales_report_job",
        namespace="spark-operator",
        application_file="templates/sales_report_job.yaml.j2",
        # 'template_vars' has been removed from here
        kubernetes_conn_id="kubernetes_default",
    )

spark_sales_report_dag_v2()