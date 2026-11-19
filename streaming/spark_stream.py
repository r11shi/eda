"""Spark Structured Streaming: Kafka -> parse + validate JSON -> derived measures -> windowed aggregation -> ClickHouse.

  python streaming/spark_stream.py [--starting-offsets earliest|latest]
Run with the PySpark virtualenv (runtime/venv-spark).
"""
import argparse, shutil
from datetime import datetime, timezone
from pathlib import Path
import clickhouse_connect
import pandas as pd
from pyspark.sql import SparkSession, functions as F, types as T

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--bootstrap", default="localhost:9092"); ap.add_argument("--topic", default="food_inspections")
ap.add_argument("--starting-offsets", default="latest"); ap.add_argument("--fresh", action="store_true", help="delete checkpoints first")
args = ap.parse_args()
CKPT = ROOT / "runtime" / "spark-checkpoints"
if args.fresh:
    shutil.rmtree(CKPT, ignore_errors=True)

spark = (SparkSession.builder.master("local[2]").appName("food-inspection-stream")
         .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1")
         .config("spark.sql.shuffle.partitions", "2").config("spark.sql.session.timeZone", "UTC").config("spark.ui.enabled", "false").getOrCreate())
spark.sparkContext.setLogLevel("WARN")
ch_client = lambda: clickhouse_connect.get_client(host="127.0.0.1", port=8123)   # one client per call: the four queries write concurrently
now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

schema = T.StructType([
    T.StructField("event_id", T.StringType()), T.StructField("source_mode", T.StringType()), T.StructField("replay_run_id", T.StringType()),
    T.StructField("emitted_at", T.StringType()), T.StructField("event_time", T.StringType()), T.StructField("inspection_id", T.LongType()),
    T.StructField("license_number", T.StringType()), T.StructField("dba_name", T.StringType()), T.StructField("facility_type", T.StringType()),
    T.StructField("facility_group", T.StringType()), T.StructField("risk_group", T.StringType()), T.StructField("inspection_type_group", T.StringType()),
    T.StructField("result", T.StringType()), T.StructField("result_group", T.StringType()), T.StructField("violation_count", T.IntegerType()),
    T.StructField("zip", T.StringType()), T.StructField("area_group", T.StringType())])

raw = (spark.readStream.format("kafka").option("kafka.bootstrap.servers", args.bootstrap).option("subscribe", args.topic)
       .option("startingOffsets", args.starting_offsets).option("failOnDataLoss", "false").load())
msgs = raw.select(F.col("value").cast("string").alias("raw"), F.col("timestamp").alias("ingest_ts")).withColumn("j", F.from_json("raw", schema))

# ---- validation rules (a rule that fails gives a reason; the first failing rule is reported)
j = F.col("j")
reason = (F.when(F.expr("try_parse_json(raw)").isNull(), "not valid JSON")
          .when(j.isNull(), "not valid JSON")
          .when(j["inspection_id"].isNull() | (j["inspection_id"] <= 0), "missing or invalid inspection_id")
          .when(F.to_date(j["event_time"], "yyyy-MM-dd").isNull(), "event_time is not a date")
          .when(~j["result_group"].isin("Pass", "Conditional Pass", "Fail"), "result_group not in (Pass, Conditional Pass, Fail)")
          .when(~j["risk_group"].isin("High", "Medium", "Low", "Unknown"), "risk_group not in documented list")
          .when(j["violation_count"].isNotNull() & ((j["violation_count"] < 0) | (j["violation_count"] > 100)), "violation_count out of range")
          .when(j["emitted_at"].isNull() | F.to_timestamp(j["emitted_at"]).isNull(), "emitted_at missing"))
checked = msgs.withColumn("reason", reason)
invalid = checked.filter(F.col("reason").isNotNull()).select("ingest_ts", "reason", "raw")
valid = (checked.filter(F.col("reason").isNull()).select("j.*", "ingest_ts")
         .withColumn("emitted_ts", F.to_timestamp("emitted_at")).withColumn("event_date", F.to_date("event_time"))
         # derived measures
         .withColumn("is_fail", (F.col("result_group") == "Fail").cast("int")).withColumn("is_pass", (F.col("result_group") == "Pass").cast("int"))
         .withColumn("is_conditional", (F.col("result_group") == "Conditional Pass").cast("int"))
         .withColumn("high_violation_flag", F.when(F.col("violation_count") >= 6, 1).otherwise(0)))


def write_events(df, batch_id):
    pdf = df.toPandas()
    if pdf.empty:
        return
    t = now()
    out = pd.DataFrame({
        "event_id": pdf["event_id"], "replay_run_id": pdf["replay_run_id"].fillna(""), "inspection_id": pdf["inspection_id"].astype("uint64"),
        "event_date": pd.to_datetime(pdf["event_date"]).dt.date, "emitted_at": pdf["emitted_ts"], "ingest_ts": pdf["ingest_ts"], "written_at": t,
        "license_number": pdf["license_number"].fillna(""), "dba_name": pdf["dba_name"].fillna(""), "facility_type": pdf["facility_type"].fillna("Unknown"),
        "facility_group": pdf["facility_group"].fillna("Unknown"), "risk_group": pdf["risk_group"], "inspection_type_group": pdf["inspection_type_group"].fillna("Other"),
        "result": pdf["result"].fillna(""), "result_group": pdf["result_group"], "violation_count": pdf["violation_count"].astype("Int64"),
        "high_violation_flag": pdf["high_violation_flag"].astype("uint8"), "zip": pdf["zip"].fillna("Unknown"), "area_group": pdf["area_group"].fillna("Unknown"),
        "is_fail": pdf["is_fail"].astype("uint8"), "is_pass": pdf["is_pass"].astype("uint8"), "is_conditional": pdf["is_conditional"].astype("uint8")})
    ch_client().insert_df("food.inspection_events", out)


def write_invalid(df, batch_id):
    pdf = df.toPandas()
    if not pdf.empty:
        ch_client().insert_df("food.invalid_events", pdf[["ingest_ts", "reason", "raw"]])


def write_windows(df, batch_id):
    pdf = df.toPandas()
    if pdf.empty:
        return
    out = pd.DataFrame({"window_start": pdf["window_start"], "facility_group": pdf["facility_group"].fillna("Unknown"), "risk_group": pdf["risk_group"],
                        "area_group": pdf["area_group"].fillna("Unknown"), "result_group": pdf["result_group"], "inspections": pdf["inspections"].astype("uint32"),
                        "violations": pdf["violations"].fillna(0).astype("uint32"), "high_violation_inspections": pdf["high_violation_inspections"].astype("uint32"), "updated_at": now()})
    ch_client().insert_df("food.window_agg", out)


def write_daily(df, batch_id):
    pdf = df.toPandas()
    if pdf.empty:
        return
    out = pd.DataFrame({"event_day": pd.to_datetime(pdf["event_day"]).dt.date, "result_group": pdf["result_group"], "inspections": pdf["inspections"].astype("uint32"), "updated_at": now()})
    ch_client().insert_df("food.daily_event_time_agg", out)


windows = (valid.withWatermark("ingest_ts", "30 seconds")
           .groupBy(F.window("ingest_ts", "10 seconds").alias("w"), "facility_group", "risk_group", "area_group", "result_group")
           .agg(F.count("*").alias("inspections"), F.sum("violation_count").alias("violations"), F.sum("high_violation_flag").alias("high_violation_inspections"))
           .select(F.col("w.start").alias("window_start"), "facility_group", "risk_group", "area_group", "result_group", "inspections", "violations", "high_violation_inspections"))
daily = (valid.withColumn("event_ts", F.to_timestamp("event_date")).withWatermark("event_ts", "1 day")
         .groupBy(F.window("event_ts", "1 day").alias("w"), "result_group").agg(F.count("*").alias("inspections"))
         .select(F.to_date(F.col("w.start")).alias("event_day"), "result_group", "inspections"))

trigger = {"processingTime": "2 seconds"}
queries = [
    valid.writeStream.foreachBatch(write_events).option("checkpointLocation", str(CKPT / "events")).trigger(**trigger).start(),
    invalid.writeStream.foreachBatch(write_invalid).option("checkpointLocation", str(CKPT / "invalid")).trigger(**trigger).start(),
    windows.writeStream.outputMode("update").foreachBatch(write_windows).option("checkpointLocation", str(CKPT / "windows")).trigger(**trigger).start(),
    daily.writeStream.outputMode("update").foreachBatch(write_daily).option("checkpointLocation", str(CKPT / "daily")).trigger(**trigger).start(),
]
print("Streaming queries started: events, invalid, windows (10 s), daily (event time). Waiting ...", flush=True)
spark.streams.awaitAnyTermination()
