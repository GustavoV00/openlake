# OpenLake Airflow image — official Apache Airflow 3.2.2 (matches the vendored
# chart's appVersion) + the Trino provider for warehouse_smoke_dag's check task.
# apache-airflow-providers-cncf-kubernetes (SparkKubernetesOperator/Sensor) ships
# in the official image's default extras already — no need to add it here.
FROM apache/airflow:3.2.2

RUN pip install --no-cache-dir apache-airflow-providers-trino
