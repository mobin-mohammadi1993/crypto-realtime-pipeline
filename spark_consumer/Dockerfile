# The official Apache Spark image (python3 variant = PySpark preinstalled).
# Tried bitnami's image first; it ships as one ~1GB layer that kept
# failing to pull over a slow/flaky connection. This one is smaller and
# split across more layers, so a dropped connection loses less progress.
FROM apache/spark:3.5.1-python3
USER root

COPY warmup.py /app/warmup.py
COPY streaming_job.py /app/streaming_job.py

# This image sets $SPARK_HOME but doesn't put spark-submit on PATH, so we
# call it by full path.
# Resolve the Kafka + Postgres JDBC packages once at build time so the
# container never needs internet access to run the streaming job.
RUN /opt/spark/bin/spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.4 \
    --master local[1] /app/warmup.py

CMD ["/opt/spark/bin/spark-submit", \
     "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.4", \
     "--master", "local[*]", \
     "/app/streaming_job.py"]
