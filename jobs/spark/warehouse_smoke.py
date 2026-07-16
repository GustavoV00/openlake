"""M3 smoke test: create an Iceberg table in the Hive Metastore backed by MinIO,
insert data, and verify it can be read back.

The Iceberg catalog (spark_catalog) and S3A configuration are provided via
sparkConf in warehouse-smoke.yaml.
"""

from pyspark.sql import SparkSession

TABLE_SCHEMA = "bronze"
TABLE_NAME = "demo"
FULL_TABLE_NAME = f"{TABLE_SCHEMA}.{TABLE_NAME}"
TABLE_LOCATION = "s3a://warehouse/iceberg/bronze/demo"


def ensure_table_registered(
    spark: SparkSession,
    schema: str,
    table: str,
    location: str,
) -> None:
    spark.sql(f"DROP TABLE IF EXISTS {schema}.{table}")
    spark.sql(
        f"""
        CREATE TABLE {schema}.{table} (
            id BIGINT,
            label STRING
        )
        USING ICEBERG
        LOCATION '{location}'
        """
    )
    spark.sql(
        f"INSERT INTO {schema}.{table} VALUES (1, 'hello'), (2, 'iceberg'), (3, 'openlake')"
    )


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("warehouse-smoke")
        .getOrCreate()
    )

    # Register the table in the Hive Metastore
    ensure_table_registered(
        spark,
        TABLE_SCHEMA,
        TABLE_NAME,
        TABLE_LOCATION,
    )

    # Read the table back through the Iceberg catalog (not the S3 path — HMS-backed
    # Iceberg tables lack version-hint.text, so path-based reads fail).
    count = spark.read.table(FULL_TABLE_NAME).count()

    print(f"SMOKE OK: {FULL_TABLE_NAME} has {count} rows")
    assert count == 3, f"expected 3 rows, got {count}"

    spark.stop()


if __name__ == "__main__":
    main()
