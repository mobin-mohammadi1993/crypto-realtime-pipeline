"""
Spark Structured Streaming job. This is the "consumer" side of Kafka: it
reads the trade events the producer wrote, and does two things with them
at the same time:

  1. raw_trades_query  - writes every trade straight through to Postgres,
                          unchanged. Powers the "recent trades" table on
                          the dashboard.
  2. metrics_query      - groups trades into 1-minute windows per symbol
                          and computes avg/min/max price, total volume,
                          and trade count for each window, then writes
                          just those summary rows to Postgres. Powers the
                          price and volume charts.

Both are separate streaming queries running on one SparkSession, each
reading from the same Kafka topic independently.
"""
import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, from_json, max as spark_max, min as spark_min
from pyspark.sql.functions import sum as spark_sum, to_timestamp, window
from pyspark.sql.types import BooleanType, LongType, StringType, StructField, StructType

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "crypto_trades")
PG_URL = os.getenv("PG_JDBC_URL", "jdbc:postgresql://postgres:5432/warehouse")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Shape of the JSON messages the producer writes to Kafka. Spark can't
# infer a schema from a Kafka topic on its own (it just sees bytes), so we
# spell out exactly what fields to expect and what type each one is.
# price/quantity come in as strings (see producer.py for why) and get
# cast to double right after parsing, below.
TRADE_SCHEMA = StructType(
    [
        StructField("symbol", StringType()),
        StructField("trade_id", LongType()),
        StructField("price", StringType()),
        StructField("quantity", StringType()),
        StructField("trade_time", LongType()),
        StructField("is_buyer_maker", BooleanType()),
    ]
)

spark = SparkSession.builder.appName("crypto-streaming").getOrCreate()
spark.sparkContext.setLogLevel("WARN")  # Spark's default logging is very noisy otherwise.

# Kafka messages arrive as raw (key, value) bytes. "value" holds our JSON
# payload; everything else (offsets, partitions, etc.) we don't need here.
raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "latest")  # start from "now", not from the beginning of the topic
    .load()
)

trades = (
    raw.select(from_json(col("value").cast("string"), TRADE_SCHEMA).alias("t"))
    .select("t.*")
    .withColumn("price", col("price").cast("double"))
    .withColumn("quantity", col("quantity").cast("double"))
    .withColumn("event_time", to_timestamp(col("trade_time") / 1000))
    # Tells Spark: "once you've seen an event_time 2 minutes past some
    # point, assume no more late data will arrive before that point."
    # This is what lets the windowed aggregation below know when a
    # 1-minute window is actually finished and safe to write out once.
    .withWatermark("event_time", "2 minutes")
)


def jdbc_writer(table):
    """
    Returns a function that writes one micro-batch of rows to the given
    Postgres table. Structured Streaming calls this once per micro-batch
    via foreachBatch, which is the standard way to write a streaming
    DataFrame somewhere that doesn't have a native streaming sink (like
    Postgres over JDBC).
    """

    def write(batch_df, batch_id):
        (
            batch_df.write.format("jdbc")
            .option("url", PG_URL)
            .option("dbtable", table)
            .option("user", PG_USER)
            .option("password", PG_PASSWORD)
            .option("driver", "org.postgresql.Driver")
            .mode("append")
            .save()
        )

    return write


# Query 1: pass every trade straight through to Postgres.
raw_trades_query = (
    trades.writeStream.outputMode("append")
    .foreachBatch(jdbc_writer("raw_trades"))
    .trigger(processingTime="5 seconds")
    .option("checkpointLocation", "/tmp/checkpoints/raw_trades")
    .start()
)

# Query 2: roll trades up into 1-minute windows per symbol.
metrics = (
    trades.groupBy(window(col("event_time"), "1 minute"), col("symbol"))
    .agg(
        avg("price").alias("avg_price"),
        spark_min("price").alias("min_price"),
        spark_max("price").alias("max_price"),
        spark_sum("quantity").alias("total_volume"),
        count("*").alias("trade_count"),
    )
    .select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        "symbol",
        "avg_price",
        "min_price",
        "max_price",
        "total_volume",
        "trade_count",
    )
)

# outputMode("append") here means: only emit a window's row once the
# watermark above proves that window is closed. That gives us exactly one
# row per (symbol, window) in Postgres, instead of the same window being
# written over and over as more trades trickle in.
metrics_query = (
    metrics.writeStream.outputMode("append")
    .foreachBatch(jdbc_writer("price_metrics_1m"))
    .trigger(processingTime="10 seconds")
    .option("checkpointLocation", "/tmp/checkpoints/price_metrics_1m")
    .start()
)

# Block here and keep the process alive as long as either query is
# running. If one of them dies (e.g. Postgres goes down), this returns
# and the container exits, which lets Docker's restart policy bring it
# back up.
spark.streams.awaitAnyTermination()
