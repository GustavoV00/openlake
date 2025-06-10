from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, avg, count, when
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

def create_spark_session():
    """Create Spark session."""
    return SparkSession.builder \
        .appName("PySpark-Delta-MinIO") \
        .getOrCreate()

def create_sample_data(spark):
    """Create a sample DataFrame with sales data."""
    schema = StructType([
        StructField("transaction_id", StringType(), True),
        StructField("customer_id", StringType(), True),
        StructField("product_category", StringType(), True),
        StructField("product_name", StringType(), True),
        StructField("quantity", IntegerType(), True),
        StructField("unit_price", DoubleType(), True),
        StructField("sales_date", StringType(), True),
        StructField("region", StringType(), True)
    ])
    
    sample_data = [
        ("TXN001", "CUST001", "Electronics", "Laptop", 2, 1200.00, "2024-01-15", "North"),
        ("TXN002", "CUST002", "Clothing", "T-Shirt", 5, 25.00, "2024-01-16", "South"),
        ("TXN003", "CUST001", "Electronics", "Mouse", 3, 35.00, "2024-01-17", "North"),
        ("TXN004", "CUST003", "Books", "Programming Guide", 1, 45.00, "2024-01-18", "East"),
        ("TXN005", "CUST004", "Electronics", "Keyboard", 2, 85.00, "2024-01-19", "West"),
        ("TXN006", "CUST002", "Clothing", "Jeans", 1, 75.00, "2024-01-20", "South"),
        ("TXN007", "CUST005", "Books", "Data Science", 2, 65.00, "2024-01-21", "North"),
        ("TXN008", "CUST003", "Electronics", "Monitor", 1, 300.00, "2024-01-22", "East"),
        ("TXN009", "CUST006", "Clothing", "Jacket", 1, 120.00, "2024-01-23", "West"),
        ("TXN010", "CUST004", "Books", "Machine Learning", 1, 80.00, "2024-01-24", "North")
    ]
    
    return spark.createDataFrame(sample_data, schema)

def process_sales_data(df):
    """
    Process sales data by adding calculated columns and creating summary aggregations.
    """
    # Add calculated columns and cast sales_date to date type
    df_processed = df.withColumn("total_amount", col("quantity") * col("unit_price")) \
                     .withColumn("sales_date", col("sales_date").cast("date"))
    
    # Create sales summary by category and region
    category_summary = df_processed.groupBy("product_category", "region") \
        .agg(
            spark_sum("total_amount").alias("total_sales"),
            avg("total_amount").alias("avg_order_value"),
            count("transaction_id").alias("transaction_count"),
            spark_sum("quantity").alias("total_quantity")
        ) \
        .withColumn("avg_order_value", col("avg_order_value").cast("decimal(10,2)")) \
        .withColumn("total_sales", col("total_sales").cast("decimal(10,2)"))
    
    # Create customer summary with segmentation
    customer_summary = df_processed.groupBy("customer_id", "region") \
        .agg(
            spark_sum("total_amount").alias("customer_total_spent"),
            count("transaction_id").alias("customer_order_count"),
            avg("total_amount").alias("customer_avg_order")
        ) \
        .withColumn("customer_segment", 
                      when(col("customer_total_spent") > 500, "High Value")
                      .when(col("customer_total_spent") > 200, "Medium Value")
                      .otherwise("Low Value")) \
        .withColumn("customer_total_spent", col("customer_total_spent").cast("decimal(10,2)")) \
        .withColumn("customer_avg_order", col("customer_avg_order").cast("decimal(10,2)"))
    
    return df_processed, category_summary, customer_summary

def write_to_minio_delta(df, path, partition_cols=None):
    """
    Write DataFrame to a MinIO path as a Delta table, with optional partitioning.
    """
    writer = df.write.format("delta") \
                     .mode("overwrite") \
                     .option("overwriteSchema", "true")

    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    
    writer.save(path)
    print(f"Successfully wrote Delta table to: {path}")

def main():
    """Main execution function."""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        print("Creating sample sales data...")
        sales_df = create_sample_data(spark)
        
        print("\nProcessing sales data...")
        processed_df, category_summary, customer_summary = process_sales_data(sales_df)
        
        # --- Show processed results ---
        print("\nCategory Summary by Region:")
        category_summary.orderBy(col("total_sales").desc()).show(truncate=False)
        
        print("\nCustomer Summary:")
        customer_summary.orderBy(col("customer_total_spent").desc()).show(truncate=False)
        
        # --- Define MinIO paths ---
        base_path = "s3a://data-lake"
        processed_sales_path = f"{base_path}/processed_sales"
        category_summary_path = f"{base_path}/category_summary"
        customer_summary_path = f"{base_path}/customer_summary"
        
        # --- Write dataframes to MinIO as Delta tables ---
        print("\nWriting data to MinIO as Delta tables...")
        
        # Write processed sales data partitioned by region and category
        write_to_minio_delta(processed_df, processed_sales_path, ["region", "product_category"])
        
        # Write category summary partitioned by region
        write_to_minio_delta(category_summary, category_summary_path, ["region"])
        
        # Write customer summary (not partitioned)
        write_to_minio_delta(customer_summary, customer_summary_path)
        
        print("\nData processing and writing completed successfully!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise
    
    finally:
        print("Stopping Spark session.")
        spark.stop()

if __name__ == "__main__":
    main()