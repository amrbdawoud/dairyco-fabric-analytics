# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "b283782d-8f21-401a-86d7-4aa51f744a72",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "13f3caf0-07d5-45b6-aba0-319b493a9692"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_01_bronze_ingest
# **Layer:** Bronze (raw, append-only) · **Default lakehouse:** `lh_bronze`
# 
# Metadata-driven ingestion. Every entity is described once in `Files/config/ingestion_config.json`
# (source system, file, format, target table, load type, business key, sensitivity, owner).
# The notebook scans `Files/landing/<source>/load_date=YYYY-MM-DD/` and ingests every file that is not
# yet recorded in `_ingestion_log`, so re-running is idempotent and a new `load_date` folder is picked up
# automatically (file-based incremental ingestion).
# 
# Bronze rules: no business logic, no type coercion (CSV read as strings = schema-on-read, so a bad value
# can never fail the load), audit columns added, append only.

# PARAMETERS CELL ********************

# Parameters (overridden by the pipeline)
load_date_filter = ""   # optional: only ingest this load_date, e.g. "2026-09-01"
batch_id = ""           # pipeline run id; generated when run interactively

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json, uuid, datetime
from pyspark.sql import functions as F

batch_id = batch_id or f"manual-{datetime.datetime.utcnow():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
cfg = json.loads("".join(r.value for r in spark.read.text("Files/config/ingestion_config.json").collect()))
entities = cfg["entities"]

spark.sql("""
CREATE TABLE IF NOT EXISTS _ingestion_log (
  source STRING, source_file STRING, bronze_table STRING, load_date STRING, batch_id STRING,
  rows_ingested BIGINT, status STRING, message STRING, ingested_at TIMESTAMP) USING DELTA""")
already = {r.source_file for r in spark.table("_ingestion_log").where("status = 'SUCCEEDED'").select("source_file").collect()}
print(f"batch {batch_id}: {len(entities)} entities configured, {len(already)} files already ingested")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

def landing_files(entity):
    """Yield (load_date, path) for every landing file of an entity, oldest first."""
    root = f"Files/landing/{entity['source']}"
    try:
        dirs = notebookutils.fs.ls(root)
    except Exception:
        return []
    out = []
    for d in dirs:
        if not d.name.startswith("load_date="):
            continue
        ld = d.name.split("=", 1)[1].strip("/")
        if load_date_filter and ld != load_date_filter:
            continue
        p = f"{root}/{d.name.strip('/')}/{entity['file']}"
        if notebookutils.fs.exists(p):
            out.append((ld, p))
    return sorted(out)


def read_raw(entity, path):
    if entity["format"] == "csv":
        return spark.read.option("header", True).option("inferSchema", False).option("multiLine", False).csv(path)
    # JSONL / API-style: keep the payload shape, stringify so a type drift upstream cannot break the load
    df = spark.read.json(path)
    return df.select([F.col(c).cast("string").alias(c) for c in df.columns])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

log_rows = []
for e in entities:
    for ld, path in landing_files(e):
        if path in already:
            continue
        try:
            df = (read_raw(e, path)
                  .withColumn("_source_system", F.lit(e["source"]))
                  .withColumn("_source_file", F.lit(path))
                  .withColumn("_load_date", F.lit(ld))
                  .withColumn("_batch_id", F.lit(batch_id))
                  .withColumn("_ingested_at", F.current_timestamp()))
            n = df.count()
            (df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(e["bronze_table"]))
            log_rows.append((e["source"], path, e["bronze_table"], ld, batch_id, n, "SUCCEEDED", "", datetime.datetime.utcnow()))
            print(f"OK   {e['bronze_table']:<28} {ld} {n:>7} rows")
        except Exception as ex:  # log and continue: one bad file must not block the other sources
            log_rows.append((e["source"], path, e["bronze_table"], ld, batch_id, 0, "FAILED", str(ex)[:1000], datetime.datetime.utcnow()))
            print(f"FAIL {e['bronze_table']}: {ex}")

if log_rows:
    spark.createDataFrame(log_rows, spark.table("_ingestion_log").schema).write.mode("append").saveAsTable("_ingestion_log")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

failed = [r for r in log_rows if r[6] == "FAILED"]
summary = {"batch_id": batch_id, "files_ingested": len(log_rows) - len(failed), "files_failed": len(failed)}
print(summary)
if failed:
    raise RuntimeError(f"{len(failed)} file(s) failed ingestion - see _ingestion_log for batch {batch_id}")
notebookutils.notebook.exit(json.dumps(summary))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
