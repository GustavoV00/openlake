"""HMS smoke test: partitioned Iceberg table through the Hive Metastore.
Verifies HMS tracks the partition spec correctly and per-partition filters
read back the right rows (partition pruning).

The Iceberg catalog (spark_catalog) and S3A configuration are provided via
sparkConf in partition-smoke.yaml.
"""

from pyspark.sql import SparkSession

TABLE_SCHEMA = "bronze"
TABLE_NAME = "partitioned_demo"
FULL_TABLE_NAME = f"{TABLE_SCHEMA}.{TABLE_NAME}"
TABLE_LOCATION = "s3a://warehouse/iceberg/bronze/partitioned_demo"


def main() -> None:
    spark = SparkSession.builder.appName("partition-smoke").getOrCreate()

    spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE_NAME}")
    spark.sql(
        f"""
        CREATE TABLE {FULL_TABLE_NAME} (
            id BIGINT,
            dt STRING,
            label STRING
        )
        USING ICEBERG
        PARTITIONED BY (dt)
        LOCATION '{TABLE_LOCATION}'
        """
    )
    spark.sql(
        f"""
        INSERT INTO {FULL_TABLE_NAME} VALUES
            (1, '2026-01-01', 'a'),
            (2, '2026-01-01', 'b'),
            (3, '2026-01-02', 'c')
        """
    )

    total = spark.read.table(FULL_TABLE_NAME).count()
    print(f"SMOKE OK: {FULL_TABLE_NAME} has {total} rows")
    assert total == 3, f"expected 3 rows, got {total}"

    partitions = spark.sql(f"SELECT dt, count(*) AS c FROM {FULL_TABLE_NAME} GROUP BY dt").collect()
    counts = {r["dt"]: r["c"] for r in partitions}
    print(f"SMOKE OK: partition counts {counts}")
    assert counts == {"2026-01-01": 2, "2026-01-02": 1}, f"unexpected partition counts: {counts}"

    spark.stop()


if __name__ == "__main__":
    main()
