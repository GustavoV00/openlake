"""M3 smoke test: write an Iceberg table to s3a://warehouse, register it in the
Hive Metastore, read it back. All catalog/S3 config comes from sparkConf (see
warehouse-smoke.yaml) so this stays env-agnostic — same code on kind and aws.
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("warehouse-smoke").getOrCreate()

spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.smoke")
spark.sql("DROP TABLE IF EXISTS warehouse.smoke.demo")
spark.sql(
    "CREATE TABLE warehouse.smoke.demo (id BIGINT, label STRING) USING iceberg"
)
spark.sql(
    "INSERT INTO warehouse.smoke.demo VALUES (1, 'hello'), (2, 'iceberg'), (3, 'openlake')"
)

count = spark.table("warehouse.smoke.demo").count()
print(f"SMOKE OK: warehouse.smoke.demo has {count} rows")
assert count == 3, f"expected 3 rows, got {count}"

spark.stop()
