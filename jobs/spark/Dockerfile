# OpenLake Spark image — official Apache Spark 4.0.2 + the jars the base lacks for
# S3A and Iceberg. Spark 4.0.2 ships Hadoop 3.4.1 client + Scala 2.13. S3A jars:
#   - hadoop-aws 3.4.1 — MUST match the base image's hadoop-client (3.4.1) exactly.
#     3.4.0 caused a NoSuchMethodError on VectoredReadUtils during Parquet vectored
#     reads (surfaced by schema-evolution/partition smoke jobs doing collect()/
#     GROUP BY reads — the plain count() in warehouse-smoke.py didn't hit that path).
#   - AWS SDK v2 bundle 2.40.9 (Hadoop 3.4 dropped v1 aws-java-sdk-bundle for
#     software.amazon.awssdk:bundle; SDK v2 is forward-compatible with the client)
#   - iceberg-spark-runtime for Spark 4.0 / Scala 2.13 (OpenLake is Iceberg, not Delta)
# Pinned to avoid the classpath skew the databricks-spark reference hit by
# resolving jars at runtime via spark.jars.packages.
FROM spark:4.0.2

USER root

# ADD fetches from Maven Central at build (no curl/wget in the base image).
ADD https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.jar \
    https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.40.9/bundle-2.40.9.jar \
    https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.0_2.13/1.11.0/iceberg-spark-runtime-4.0_2.13-1.11.0.jar \
    ${SPARK_HOME}/jars/

ADD https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.11.0/jmx_prometheus_javaagent-0.11.0.jar \
    /prometheus/jmx_prometheus_javaagent-0.11.0.jar

# Job code is NOT baked in — it's delivered from outside (s3a, see warehouse-smoke.yaml)
# so script edits don't force an image rebuild.

RUN chmod 0644 ${SPARK_HOME}/jars/hadoop-aws-3.4.1.jar \
      ${SPARK_HOME}/jars/bundle-2.40.9.jar \
      ${SPARK_HOME}/jars/iceberg-spark-runtime-4.0_2.13-1.11.0.jar \
      /prometheus/jmx_prometheus_javaagent-0.11.0.jar

USER spark
