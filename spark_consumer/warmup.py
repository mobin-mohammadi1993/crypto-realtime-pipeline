"""
Build-time only: forces Ivy to resolve and cache the Kafka + Postgres
packages into the image, so the running container never needs network
access just to start the streaming job.
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("warmup").master("local[1]").getOrCreate()
spark.stop()
print("warmup complete")
