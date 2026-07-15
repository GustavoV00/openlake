# Hive Metastore 3.1.3 for OpenBrick kind — a thin layer over the official
# apache/hive:3.1.3 image, reshaped to satisfy the helm-hive-metastore chart's
# standalone-metastore contract (/opt/hive-metastore/bin/{entrypoint,render-config,
# start-metastore} + gomplate-rendered conf, schematool on PATH, S3A on classpath).
#
# Why not the chart's own standalone-metastore Dockerfile at 3.1.3? There is no
# hive-standalone-metastore-3.1.3 tarball — Apache only ships standalone-metastore
# 3.0.0 / 4.1.0 / 4.2.0. HMS 4.2.0's Thrift API is incompatible with Spark's bundled
# Hive 2.3.9 client (get_table), so we roll back to the last widely-compatible full
# Hive, 3.1.3, via its official image. It already bundles a matched hadoop-aws-3.1.0
# + aws-java-sdk-bundle (S3A) and resolves the Hive 3.1.3 guava conflict.
#
# Build + load into kind (tag must match gitops/config/hive-metastore/kind.yaml):
#   docker build -t hive-metastore:3.1.3 docker/hive-metastore
#   scripts/load-hms-image.sh hive-metastore:3.1.3
FROM apache/hive:3.1.3

USER root

ENV METASTORE_HOME=/opt/hive-metastore \
    HIVE_CONF_DIR=/opt/hive-metastore/conf \
    HADOOP_CLASSPATH=/opt/hadoop/share/hadoop/tools/lib/*

# PG16 negotiates scram-sha-256; the bundled 9.4 JDBC driver (2016) can't auth. Swap it.
RUN rm -f /opt/hive/lib/postgresql-9.4.1208.jre7.jar
COPY postgresql-42.7.7.jar /opt/hive/lib/

# gomplate renders conf/templates/*.tpl -> conf/ (see render-config.sh).
COPY gomplate /usr/local/bin/gomplate

RUN mkdir -p ${METASTORE_HOME}/bin ${METASTORE_HOME}/conf/templates
# Chart renders conf/metastore-site.xml, but full-Hive schematool/HiveConf read
# hive-site.xml — point one at the other so both the metastore service and
# schematool pick up the rendered DB + S3 config.
RUN ln -sf metastore-site.xml ${METASTORE_HOME}/conf/hive-site.xml
COPY entrypoint.sh render-config.sh start-metastore ${METASTORE_HOME}/bin/
RUN chmod +x /usr/local/bin/gomplate ${METASTORE_HOME}/bin/* && \
    chown -R hive:hive ${METASTORE_HOME}

USER hive
EXPOSE 9083
WORKDIR ${METASTORE_HOME}
CMD ["bin/entrypoint.sh"]
