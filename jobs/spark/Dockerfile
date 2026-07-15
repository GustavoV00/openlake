# OpenLake Spark image — official Apache Spark 4.0.2 + the jars the base lacks for
# S3A and Iceberg. Spark 4.0.2 ships Hadoop 3.4.1 client + Scala 2.13. S3A jars
# pinned to the versions the user runs in their Spark 4.0 env (proven-good):
#   - hadoop-aws 3.4.0
#   - AWS SDK v2 bundle 2.40.9 (Hadoop 3.4 dropped v1 aws-java-sdk-bundle for
#     software.amazon.awssdk:bundle; SDK v2 is forward-compatible with the client)
#   - iceberg-spark-runtime for Spark 4.0 / Scala 2.13 (OpenLake is Iceberg, not Delta)
# Pinned to avoid the classpath skew the databricks-spark reference hit by
# resolving jars at runtime via spark.jars.packages.
FROM spark:4.0.2

USER root

# ADD fetches from Maven Central at build (no curl/wget in the base image).
ADD https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.0/hadoop-aws-3.4.0.jar \
    https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.40.9/bundle-2.40.9.jar \
    https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.0_2.13/1.11.0/iceberg-spark-runtime-4.0_2.13-1.11.0.jar \
    ${SPARK_HOME}/jars/

ADD https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.11.0/jmx_prometheus_javaagent-0.11.0.jar \
    /prometheus/jmx_prometheus_javaagent-0.11.0.jar

# ponytail: smoke job baked in for M3's first-run verification. git-sync delivery
# (spec §4.5, no per-job rebuilds) lands at M5 when Airflow drives real jobs.
COPY warehouse_smoke.py /app/warehouse_smoke.py

RUN chmod 0644 ${SPARK_HOME}/jars/hadoop-aws-3.4.0.jar \
      ${SPARK_HOME}/jars/bundle-2.40.9.jar \
      ${SPARK_HOME}/jars/iceberg-spark-runtime-4.0_2.13-1.11.0.jar \
      /prometheus/jmx_prometheus_javaagent-0.11.0.jar

USER spark
