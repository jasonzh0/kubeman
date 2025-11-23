"""
Example PySpark job that processes data.

This is a simple example that demonstrates how to create a custom PySpark job.
You can modify this script to implement your own data processing logic.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, avg, max as spark_max, min as spark_min


def main():
    """Main function that runs the PySpark job."""
    spark = SparkSession.builder.appName("CustomPySparkJob").getOrCreate()

    try:
        print("Creating sample data...")
        data = [
            ("Alice", 25, "Engineering"),
            ("Bob", 30, "Marketing"),
            ("Charlie", 35, "Engineering"),
            ("Diana", 28, "Sales"),
            ("Eve", 32, "Engineering"),
        ]

        df = spark.createDataFrame(data, ["name", "age", "department"])

        print("Sample DataFrame:")
        df.show()

        print("\nDepartment statistics:")
        dept_stats = df.groupBy("department").agg(
            count("*").alias("count"),
            avg("age").alias("avg_age"),
            spark_max("age").alias("max_age"),
            spark_min("age").alias("min_age"),
        )
        dept_stats.show()

        print("\nEngineering team members:")
        engineering = df.filter(col("department") == "Engineering")
        engineering.show()

        print("\nJob completed successfully!")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
