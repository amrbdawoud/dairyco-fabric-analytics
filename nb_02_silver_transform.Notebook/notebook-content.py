# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "f3de4535-b563-4c1a-8c44-c2ce71db6984",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "13f3caf0-07d5-45b6-aba0-319b493a9692"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_02_silver_transform
# **Layer:** Silver (cleaned, typed, conformed) · **Default lakehouse:** `lh_silver` · reads `lh_bronze`
# 
# * **Typing & naming** – every column cast to its business type, snake_case names.
# * **Conformance** – one region vocabulary (6 regions), customer duplicates resolved to a *master* customer,
#   CRM customer IDs repaired (float → int, blanks matched by name), distributor SKUs mapped to ERP ProductID.
# * **Load patterns** – `full` entities take the latest bronze extract and overwrite;
#   `incremental` entities (Sales) take only bronze rows newer than the silver watermark and `MERGE` on the
#   business key, so late-arriving corrections update in place and re-runs are idempotent.
# * **Data quality** – anomalies are *flagged, not silently fixed*. Every rule writes violating keys to
#   `dq_issues` (current state) and a count to `dq_run_history` (trend for monitoring).
# 
# Payroll / attendance / employees remain employee-level here; this lakehouse is restricted to the data
# engineering role. Only aggregates are published to gold.

# PARAMETERS CELL ********************

batch_id = ""
full_reload = "false"   # "true" ignores the watermark and rebuilds incremental entities

# CELL ********************

import datetime, uuid, json
from pyspark.sql import functions as F, Window as W
from delta.tables import DeltaTable

batch_id = batch_id or f"manual-{datetime.datetime.utcnow():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
run_ts = datetime.datetime.utcnow()
BRONZE = "lh_bronze"

REGION_MAP = {"cairo": "Cairo", "alexandria": "Alexandria", "alex.": "Alexandria", "alex": "Alexandria",
              "giza": "Giza", "delta": "Delta", "canal": "Canal", "upper egypt": "Upper Egypt",
              "upperegypt": "Upper Egypt"}
region_map_expr = F.create_map(*[F.lit(x) for kv in REGION_MAP.items() for x in kv])

def std_region(col):
    return F.coalesce(region_map_expr[F.lower(F.trim(col))], F.lit("Unknown"))

def month_start(col):
    return F.to_date(F.concat(F.col(col), F.lit("-01")))

def latest(tbl):
    """Latest full extract of a 'full' entity from bronze."""
    df = spark.table(f"{BRONZE}.{tbl}")
    mx = df.agg(F.max("_load_date")).first()[0]
    return df.where(F.col("_load_date") == mx)

def save(df, name, comment=""):
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)
    print(f"{name:<26} {spark.table(name).count():>7} rows")

DQ = []   # list of DataFrames: entity, rule_id, rule, severity, record_key, detail
def dq(entity, rule_id, rule, severity, df, key_expr, detail_expr):
    DQ.append(df.select(F.lit(entity).alias("entity"), F.lit(rule_id).alias("rule_id"), F.lit(rule).alias("rule"),
                        F.lit(severity).alias("severity"), F.concat_ws("|", *key_expr).alias("record_key"),
                        detail_expr.cast("string").alias("detail")))

# MARKDOWN ********************

# ## Master data

# CELL ********************

products = latest("erp_products").select(
    F.col("ProductID").cast("int").alias("product_id"), F.col("SKU").alias("sku"),
    F.col("ProductName").alias("product_name"), F.col("Brand").alias("brand"), F.col("Category").alias("category"),
    F.col("PackSize").alias("pack_size"), F.col("ListPrice").cast("decimal(12,2)").alias("list_price"),
    F.col("StandardCost").cast("decimal(12,2)").alias("standard_cost"),
    F.col("ShelfLifeDays").cast("int").alias("shelf_life_days"), F.col("Status").alias("status"))
save(products, "products")

cust_raw = latest("erp_customers").select(
    F.col("CustomerID").cast("int").alias("customer_id"), F.trim("CustomerName").alias("customer_name"),
    F.col("Channel").alias("channel"), F.col("Region").alias("region_raw"), F.col("SalesTerritory").alias("sales_territory"),
    (F.col("StrategicAccount").cast("int") == 1).alias("is_strategic"), F.col("Status").alias("status"))
# Duplicate rule: same name ignoring case; the proper-case record (not ALL CAPS) is the surviving master.
w = W.partitionBy(F.upper("customer_name"))
customers = (cust_raw
    .withColumn("_is_caps", F.col("customer_name") == F.upper("customer_name"))
    .withColumn("master_customer_id", F.coalesce(
        F.min(F.when(~F.col("_is_caps"), F.col("customer_id"))).over(w), F.min("customer_id").over(w)))
    .withColumn("is_duplicate", F.col("master_customer_id") != F.col("customer_id"))
    .withColumn("region", std_region(F.col("region_raw")))
    .drop("_is_caps"))
save(customers, "customers")
dq("customers", "CUS-01", "Duplicate customer (same name, different case/ID)", "High",
   customers.where("is_duplicate"), [F.col("customer_id").cast("string")],
   F.concat(F.lit("duplicate of "), F.col("master_customer_id")))
# Territory codes: prefix should identify the region uniquely
terr = customers.withColumn("prefix", F.split("sales_territory", "-")[1]).groupBy("prefix").agg(F.collect_set("region").alias("regions"))
dq("customers", "CUS-02", "Sales territory prefix shared by multiple regions", "Low",
   terr.where(F.size("regions") > 1), [F.col("prefix")], F.concat_ws(",", "regions"))

save(latest("erp_distributors").select(F.col("DistributorID").cast("int").alias("distributor_id"),
     F.col("DistributorName").alias("distributor_name"), std_region(F.col("PrimaryRegion")).alias("region")), "distributors")
save(latest("erp_warehouses").select(F.col("WarehouseID").cast("int").alias("warehouse_id"),
     F.col("WarehouseName").alias("warehouse_name"), std_region(F.col("Region")).alias("region")), "warehouses")

promotions = latest("erp_promotions").select(
    F.col("PromotionID").cast("int").alias("promotion_id"), F.col("ProductID").cast("int").alias("product_id"),
    std_region(F.col("Region")).alias("region"), F.col("PromotionType").alias("promotion_type"),
    F.to_date("StartDate").alias("start_date"), F.to_date("EndDate").alias("end_date"),
    F.col("DiscountPct").cast("decimal(5,4)").alias("discount_pct"), F.col("SupportCost").cast("decimal(14,2)").alias("support_cost"))
save(promotions, "promotions")
p2 = promotions.alias("a").join(promotions.alias("b"), (F.col("a.product_id") == F.col("b.product_id")) &
     (F.col("a.region") == F.col("b.region")) & (F.col("a.promotion_id") < F.col("b.promotion_id")) &
     (F.col("a.start_date") <= F.col("b.end_date")) & (F.col("b.start_date") <= F.col("a.end_date")))
dq("promotions", "PRM-01", "Overlapping promotions on same product/region", "Medium", p2,
   [F.col("a.promotion_id").cast("string"), F.col("b.promotion_id").cast("string")], F.lit("overlap"))

targets = latest("erp_sales_targets").select(
    month_start("Month").alias("month_start"), std_region(F.col("Region")).alias("region"), F.col("Category").alias("category"),
    F.col("RevenueTarget").cast("decimal(16,2)").alias("revenue_target"), F.col("VolumeTarget").cast("double").alias("volume_target"))
save(targets, "sales_targets")

# MARKDOWN ********************

# ## Sales (incremental: watermark + MERGE)

# CELL ********************

spark.sql("CREATE TABLE IF NOT EXISTS _watermarks (entity STRING, watermark TIMESTAMP, batch_id STRING, updated_at TIMESTAMP) USING DELTA")
wm_row = spark.table("_watermarks").where("entity = 'sales'").agg(F.max("watermark")).first()[0]
wm = None if (full_reload == "true" or not spark.catalog.tableExists("sales")) else wm_row
bronze_sales = spark.table(f"{BRONZE}.erp_sales")
new = bronze_sales if wm is None else bronze_sales.where(F.col("_ingested_at") > F.lit(wm))
# latest version of each invoice line within the new slice
new = new.withColumn("_rn", F.row_number().over(W.partitionBy("InvoiceID").orderBy(F.col("_ingested_at").desc()))).where("_rn = 1")

cust_lookup = customers.select("customer_id", "master_customer_id", F.col("region").alias("customer_region"))
sales_new = (new.select(
        F.col("InvoiceID").cast("bigint").alias("invoice_id"), F.to_date("InvoiceDate").alias("invoice_date"),
        F.col("CustomerID").cast("int").alias("customer_id"), F.col("ProductID").cast("int").alias("product_id"),
        F.col("DistributorID").cast("int").alias("distributor_id"), F.col("Quantity").cast("int").alias("quantity"),
        F.col("GrossSales").cast("decimal(14,2)").alias("gross_sales"), F.col("DiscountAmount").cast("decimal(14,2)").alias("discount_amount"),
        F.col("NetSales").cast("decimal(14,2)").alias("net_sales"), F.col("COGS").cast("decimal(14,2)").alias("cogs"),
        F.col("Region").alias("region_raw"), F.col("Channel").alias("channel"),
        F.col("_batch_id").alias("source_batch_id"), F.col("_ingested_at").alias("source_ingested_at"))
    .join(cust_lookup, "customer_id", "left")
    # Conformed region comes from the customer master; the line-level label is kept for audit only.
    .withColumn("region", F.coalesce("customer_region", std_region(F.col("region_raw")))).drop("customer_region")
    .withColumn("silver_updated_at", F.current_timestamp()))
n_new = sales_new.count()

if wm is None:
    save(sales_new, "sales")
else:
    (DeltaTable.forName(spark, "sales").alias("t")
       .merge(sales_new.alias("s"), "t.invoice_id = s.invoice_id")
       .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    print(f"sales MERGE: {n_new} new/changed lines, table now {spark.table('sales').count()} rows")
if n_new:
    new_wm = new.agg(F.max("_ingested_at")).first()[0]
    spark.createDataFrame([("sales", new_wm, batch_id, run_ts)], spark.table("_watermarks").schema).write.mode("append").saveAsTable("_watermarks")

sales = spark.table("sales")
dq("sales", "SAL-01", "Non-standard region label on invoice line", "Medium",
   sales.where(F.col("region_raw") != F.col("region")), [F.col("invoice_id").cast("string")],
   F.concat(F.col("region_raw"), F.lit(" -> "), F.col("region")))
dq("sales", "SAL-02", "Invoice booked to a duplicate customer ID", "High",
   sales.where(F.col("customer_id") != F.col("master_customer_id")), [F.col("invoice_id").cast("string")],
   F.concat(F.col("customer_id"), F.lit(" -> "), F.col("master_customer_id")))
dq("sales", "SAL-03", "NetSales <> GrossSales - DiscountAmount", "High",
   sales.where(F.abs(F.col("gross_sales") - F.col("discount_amount") - F.col("net_sales")) > 0.01),
   [F.col("invoice_id").cast("string")], F.col("net_sales"))
cogs_chk = sales.join(products.select("product_id", "standard_cost"), "product_id") \
    .withColumn("ratio", F.round(F.col("cogs") / (F.col("quantity") * F.col("standard_cost")), 3))
dq("sales", "SAL-04", "COGS deviates from Qty x StandardCost (stale standard cost)", "High",
   cogs_chk.where(F.abs(F.col("ratio") - 1) > 0.005), [F.col("invoice_id").cast("string")],
   F.concat(F.lit("COGS/std = "), F.col("ratio")))

# CELL ********************

last_sale = sales.agg(F.max("invoice_date")).first()[0]
returns = latest("erp_sales_returns").select(
    F.col("ReturnID").cast("bigint").alias("return_id"), F.col("InvoiceID").cast("bigint").alias("invoice_id"),
    F.to_date("ReturnDate").alias("return_date"), F.col("CustomerID").cast("int").alias("customer_id"),
    F.col("ProductID").cast("int").alias("product_id"), F.col("BatchID").alias("batch_id"),
    F.col("ReturnedQuantity").cast("int").alias("returned_quantity"), F.col("ReturnValue").cast("decimal(14,2)").alias("return_value"),
    F.col("ReturnReason").alias("return_reason")) \
  .join(cust_lookup.select("customer_id", "master_customer_id", F.col("customer_region").alias("region")), "customer_id", "left")
save(returns, "sales_returns")
dq("sales_returns", "RET-01", "Return dated after last available sales date", "Low",
   returns.where(F.col("return_date") > F.lit(last_sale)), [F.col("return_id").cast("string")], F.col("return_date"))
orph = returns.join(sales.select("invoice_id"), "invoice_id", "left_anti")
# Warning, not blocking: a return can arrive before its invoice line is loaded (late-arriving fact).
dq("sales_returns", "RET-02", "Return references invoice not (yet) in sales", "Medium", orph, [F.col("return_id").cast("string")], F.col("invoice_id"))

# MARKDOWN ********************

# ## Warehouse inventory (weekly batch snapshots)

# CELL ********************

inv = latest("wms_inventory_snapshots").select(
    F.to_date("SnapshotDate").alias("snapshot_date"), F.col("WarehouseID").cast("int").alias("warehouse_id"),
    F.col("ProductID").cast("int").alias("product_id"), F.col("BatchID").alias("batch_id"),
    F.col("QuantityOnHand").cast("int").alias("qty_on_hand"), F.col("ReservedQuantity").cast("int").alias("qty_reserved"),
    F.col("AvailableQuantity").cast("int").alias("qty_available_reported"),
    F.to_date("ProductionDate").alias("production_date"), F.to_date("ExpiryDate").alias("expiry_date"),
    F.col("InventoryStatus").alias("inventory_status")) \
  .withColumn("qty_available_calc", F.greatest(F.col("qty_on_hand") - F.col("qty_reserved"), F.lit(0))) \
  .withColumn("days_to_expiry", F.datediff("expiry_date", "snapshot_date"))
save(inv, "inventory_snapshots")
dq("inventory_snapshots", "INV-01", "Available <> OnHand - Reserved", "Medium",
   inv.where(F.col("qty_available_reported") != F.col("qty_on_hand") - F.col("qty_reserved")),
   [F.col("snapshot_date").cast("string"), F.col("warehouse_id").cast("string"), F.col("product_id").cast("string")],
   F.col("qty_available_reported") - (F.col("qty_on_hand") - F.col("qty_reserved")))
dq("inventory_snapshots", "INV-02", "Negative quantity on hand", "High", inv.where("qty_on_hand < 0"),
   [F.col("snapshot_date").cast("string"), F.col("warehouse_id").cast("string"), F.col("product_id").cast("string")], F.col("qty_on_hand"))
dq("inventory_snapshots", "INV-03", "Near-expiry stock (<=3 days) still status 'Available'", "Medium",
   inv.where("days_to_expiry <= 3 and inventory_status = 'Available'"),
   [F.col("snapshot_date").cast("string"), F.col("warehouse_id").cast("string"), F.col("product_id").cast("string")], F.col("days_to_expiry"))

# MARKDOWN ********************

# ## Salesforce CRM

# CELL ********************

cust_by_name = customers.select(F.upper("customer_name").alias("_n"), "master_customer_id").distinct()
acc = latest("crm_accounts").select(
    F.col("SFAccountID").alias("sf_account_id"), F.col("CustomerID").alias("customer_id_raw"),
    F.col("CustomerName").alias("customer_name"), std_region(F.col("Region")).alias("region"),
    F.col("Channel").alias("channel"), (F.col("StrategicAccount").cast("int") == 1).alias("is_strategic")) \
  .withColumn("_id", F.col("customer_id_raw").cast("double").cast("int")) \
  .join(customers.select(F.col("customer_id").alias("_id"), F.col("master_customer_id").alias("_m_id")), "_id", "left") \
  .join(cust_by_name.withColumnRenamed("master_customer_id", "_m_name"), F.upper(F.col("customer_name")) == F.col("_n"), "left") \
  .withColumn("customer_id", F.coalesce("_m_id", "_m_name")) \
  .withColumn("match_method", F.when(F.col("_m_id").isNotNull(), "id").when(F.col("_m_name").isNotNull(), "name").otherwise("unmatched")) \
  .drop("_id", "_m_id", "_m_name", "_n")
save(acc, "crm_accounts")
dq("crm_accounts", "CRM-01", "CRM CustomerID stored as float text", "Low",
   acc.where(F.col("customer_id_raw").contains(".")), [F.col("sf_account_id")], F.col("customer_id_raw"))
dq("crm_accounts", "CRM-02", "CRM account missing ERP CustomerID (matched by name)", "Medium",
   acc.where(F.col("customer_id_raw").isNull()), [F.col("sf_account_id")], F.col("match_method"))

opps = latest("crm_opportunities").select(
    F.col("OpportunityID").alias("opportunity_id"), F.col("SFAccountID").alias("sf_account_id"),
    month_start("CreatedMonth").alias("created_month"), F.col("OpportunityValue").cast("decimal(16,2)").alias("opportunity_value"),
    F.col("Stage").alias("stage"), F.to_date("ExpectedCloseDate").alias("expected_close_date"), F.col("OpportunityType").alias("opportunity_type")) \
  .withColumn("is_open", ~F.col("stage").isin("Closed Won", "Closed Lost")) \
  .withColumn("is_stale", F.col("is_open") & (F.col("expected_close_date") < F.lit(last_sale)))
save(opps, "crm_opportunities")
dq("crm_opportunities", "CRM-03", "Open opportunity past expected close date", "Low",
   opps.where("is_stale"), [F.col("opportunity_id")], F.col("expected_close_date"))
save(latest("crm_activities").select(F.col("ActivityID").alias("activity_id"), F.col("SFAccountID").alias("sf_account_id"),
     F.to_date("ActivityDate").alias("activity_date"), F.col("ActivityType").alias("activity_type"),
     F.col("DurationMinutes").cast("int").alias("duration_minutes")), "crm_activities")

# MARKDOWN ********************

# ## Distributor platform (JSONL API feeds)

# CELL ********************

sku_to_pid = F.regexp_extract(F.col("distributor_sku"), r"(\d{4})$", 1).cast("int")
sku_status = F.when(F.col("distributor_sku").startswith("D-"), "mapped").when(sku_to_pid.isNotNull(), "recovered_from_unknown").otherwise("unmapped")

so = latest("dist_sellout").select(
    month_start("transaction_month").alias("month_start"), F.col("distributor_id").cast("int").alias("distributor_id"),
    "distributor_sku", "outlet_code", F.col("quantity_sold").cast("int").alias("quantity_sold"),
    F.col("sellout_value").cast("decimal(14,2)").alias("sellout_value"), std_region(F.col("region")).alias("region")) \
  .withColumn("product_id", sku_to_pid).withColumn("sku_mapping_status", sku_status)
save(so, "dist_sellout")
dq("dist_sellout", "DST-01", "Distributor SKU not in agreed D-#### format", "Medium",
   so.where("sku_mapping_status <> 'mapped'"), [F.col("month_start").cast("string"), F.col("distributor_id").cast("string"),
   F.col("distributor_sku"), F.col("outlet_code")], F.col("sku_mapping_status"))

di = latest("dist_inventory").select(
    month_start("month").alias("month_start"), F.col("distributor_id").cast("int").alias("distributor_id"), "distributor_sku",
    F.col("receipts_qty").cast("int").alias("receipts_qty"), F.col("sellout_qty").cast("int").alias("sellout_qty"),
    F.col("closing_inventory_qty").cast("int").alias("closing_inventory_qty")) \
  .withColumn("product_id", sku_to_pid).withColumn("sku_mapping_status", sku_status)
wd = W.partitionBy("distributor_id", "product_id").orderBy("month_start")
di = di.withColumn("opening_inventory_qty", F.lag("closing_inventory_qty").over(wd)) \
       .withColumn("rollforward_gap_qty", F.col("closing_inventory_qty") - (F.col("opening_inventory_qty") + F.col("receipts_qty") - F.col("sellout_qty")))
save(di, "dist_inventory")
dq("dist_inventory", "DST-02", "Inventory roll-forward does not balance (opening+receipts-sellout<>closing)", "Medium",
   di.where("rollforward_gap_qty <> 0"), [F.col("month_start").cast("string"), F.col("distributor_id").cast("string"), F.col("distributor_sku")],
   F.col("rollforward_gap_qty"))
so_m = so.groupBy("month_start", "distributor_id", "product_id").agg(F.sum("quantity_sold").alias("so_outlet_qty"))
rec = di.join(so_m, ["month_start", "distributor_id", "product_id"], "left").where(F.coalesce("so_outlet_qty", F.lit(0)) != F.col("sellout_qty"))
dq("dist_inventory", "DST-03", "Distributor-reported sell-out <> sum of outlet sell-out", "Medium", rec,
   [F.col("month_start").cast("string"), F.col("distributor_id").cast("string"), F.col("product_id").cast("string")],
   F.col("sellout_qty") - F.coalesce("so_outlet_qty", F.lit(0)))
save(latest("dist_outlets").select(F.col("OutletID").cast("int").alias("outlet_id"), F.col("DistributorID").cast("int").alias("distributor_id"),
     F.col("DistributorOutletCode").alias("outlet_code"), std_region(F.col("Region")).alias("region"), F.col("OutletType").alias("outlet_type")), "dist_outlets")

# MARKDOWN ********************

# ## Production & MRP

# CELL ********************

save(latest("mrp_demand_forecast").select(month_start("Month").alias("month_start"), F.col("ProductID").cast("int").alias("product_id"),
     F.col("ForecastDemand").cast("int").alias("forecast_qty")), "demand_forecast")
po = latest("mrp_production_orders").select(
    F.col("ProductionOrderID").cast("int").alias("production_order_id"), month_start("Month").alias("month_start"),
    F.col("PlantID").cast("int").alias("plant_id"), F.col("LineID").cast("int").alias("line_id"), F.col("Shift").alias("shift"),
    F.col("ProductID").cast("int").alias("product_id"), F.col("PlannedQuantity").cast("int").alias("planned_qty"),
    F.col("ActualQuantity").cast("int").alias("actual_qty"), F.col("GoodQuantity").cast("int").alias("good_qty"),
    F.col("ScrapQuantity").cast("int").alias("scrap_qty"), F.col("DowntimeMinutes").cast("int").alias("downtime_minutes"))
save(po, "production_orders")
dq("production_orders", "PRD-01", "Actual <> Good + Scrap", "High", po.where("actual_qty <> good_qty + scrap_qty"),
   [F.col("production_order_id").cast("string")], F.col("actual_qty"))
dt = latest("mrp_downtime").select(F.col("ProductionOrderID").cast("int").alias("production_order_id"),
     F.col("PlantID").cast("int").alias("plant_id"), F.col("LineID").cast("int").alias("line_id"), month_start("Month").alias("month_start"),
     F.col("DowntimeReason").alias("downtime_reason"), F.col("DurationMinutes").cast("int").alias("duration_minutes"))
save(dt, "downtime")
dtm = dt.groupBy("production_order_id").agg(F.sum("duration_minutes").alias("m")).join(po, "production_order_id", "full")
dq("downtime", "PRD-02", "Downtime log minutes <> production order downtime", "Medium",
   dtm.where(F.coalesce("m", F.lit(0)) != F.coalesce("downtime_minutes", F.lit(0))), [F.col("production_order_id").cast("string")], F.col("m"))
save(latest("mrp_material_requirements").select(F.col("ProductionOrderID").cast("int").alias("production_order_id"),
     F.col("ProductID").cast("int").alias("product_id"), F.col("RawMaterialID").alias("raw_material_id"),
     F.col("RequiredQuantity").cast("double").alias("required_qty"), F.col("AvailableQuantity").cast("double").alias("available_qty")) \
     .withColumn("is_shortage", F.col("required_qty") > F.col("available_qty")), "material_requirements")

# MARKDOWN ********************

# ## HR & Payroll (RESTRICTED – employee level, never published to gold at this grain)

# CELL ********************

emp = latest("hr_employees").select(F.col("EmployeeID").cast("int").alias("employee_id"), F.col("PlantID").cast("int").alias("plant_id"),
      F.col("LineID").cast("int").alias("line_id"), F.col("Shift").alias("shift"), F.col("JobRole").alias("job_role"),
      F.to_date("HireDate").alias("hire_date"), F.col("EmploymentStatus").alias("employment_status"))
save(emp, "hr_employees")
save(latest("hr_attendance").select(F.col("EmployeeID").cast("int").alias("employee_id"), month_start("Month").alias("month_start"),
     F.col("AttendanceHours").cast("double").alias("attendance_hours"), F.col("AbsenceHours").cast("double").alias("absence_hours")), "hr_attendance")
pay = latest("hr_payroll").select(F.col("EmployeeID").cast("int").alias("employee_id"), month_start("Month").alias("month_start"),
      F.col("BaseSalary").cast("decimal(12,2)").alias("base_salary"), F.col("OvertimeHours").cast("double").alias("overtime_hours"),
      F.col("OvertimeCost").cast("decimal(12,2)").alias("overtime_cost"), F.col("Allowances").cast("decimal(12,2)").alias("allowances"),
      F.col("TotalLaborCost").cast("decimal(12,2)").alias("total_labor_cost"))
save(pay, "hr_payroll")
pb = pay.join(emp, "employee_id").where(F.last_day("month_start") < F.col("hire_date"))
dq("hr_payroll", "HR-01", "Payroll paid before employee hire date", "High", pb,
   [F.col("employee_id").cast("string"), F.col("month_start").cast("string")], F.col("hire_date"))

# MARKDOWN ********************

# ## Publish DQ results

# CELL ********************

from functools import reduce
issues = reduce(lambda a, b: a.unionByName(b), DQ).withColumn("batch_id", F.lit(batch_id)).withColumn("detected_at", F.lit(run_ts))
save(issues, "dq_issues")
hist = issues.groupBy("entity", "rule_id", "rule", "severity").agg(F.count("*").alias("violations")) \
    .withColumn("batch_id", F.lit(batch_id)).withColumn("run_at", F.lit(run_ts))
hist.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable("dq_run_history")
display(hist.orderBy("rule_id"))

# Hard gate: rules that make the numbers wrong (not just untidy) stop the pipeline.
blocking = hist.where("rule_id in ('SAL-03','PRD-01')").agg(F.sum("violations")).first()[0] or 0
if blocking:
    raise RuntimeError(f"Blocking DQ rules violated ({blocking} rows) - gold not refreshed")
notebookutils.notebook.exit(json.dumps({"batch_id": batch_id, "sales_new_rows": n_new, "dq_rules": hist.count()}))
