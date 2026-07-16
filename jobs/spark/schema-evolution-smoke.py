"""HMS smoke test: Iceberg schema evolution (ADD COLUMN) through the Hive
Metastore. Verifies HMS correctly tracks the updated schema pointer after an
ALTER TABLE, and that old rows read back with a null for the new column.

The Iceberg catalog (spark_catalog) and S3A configuration are provided via
sparkConf in schema-evolution-smoke.yaml.
"""

from pyspark.sql import SparkSession

TABLE_SCHEMA = "bronze"
TABLE_NAME = "schema_evolution"
FULL_TABLE_NAME = f"{TABLE_SCHEMA}.{TABLE_NAME}"
TABLE_LOCATION = "s3a://warehouse/iceberg/bronze/schema_evolution"


def main() -> None:
    spark = SparkSession.builder.appName("schema-evolution-smoke").getOrCreate()

    spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE_NAME}")
    spark.sql(
        f"""
        CREATE TABLE {FULL_TABLE_NAME} (
            id BIGINT,
            label STRING
        )
        USING ICEBERG
        LOCATION '{TABLE_LOCATION}'
        """
    )
    spark.sql(f"INSERT INTO {FULL_TABLE_NAME} VALUES (1, 'before'), (2, 'before')")

    # HMS must persist the new schema pointer for this ALTER to be visible below.
    spark.sql(f"ALTER TABLE {FULL_TABLE_NAME} ADD COLUMN note STRING")
    spark.sql(f"INSERT INTO {FULL_TABLE_NAME} VALUES (3, 'after', 'evolved')")

    rows = spark.read.table(FULL_TABLE_NAME).orderBy("id").collect()
    count = len(rows)
    print(f"SMOKE OK: {FULL_TABLE_NAME} has {count} rows")
    assert count == 3, f"expected 3 rows, got {count}"

    old_notes = [r["note"] for r in rows if r["id"] in (1, 2)]
    new_note = [r["note"] for r in rows if r["id"] == 3][0]
    assert all(n is None for n in old_notes), f"expected old rows' note to be null, got {old_notes}"
    assert new_note == "evolved", f"expected new row's note to be 'evolved', got {new_note}"
    print(f"SMOKE OK: schema evolution visible via HMS ({FULL_TABLE_NAME})")

    spark.stop()


if __name__ == "__main__":
    main()
