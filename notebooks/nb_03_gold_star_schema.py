# %% [markdown]
# # nb_03_gold_star_schema
# **Layer:** Gold (dimensional, analytics-ready) · **Default lakehouse:** `lh_gold` · reads `lh_silver`
#
# Region *names* are denormalised onto customer/distributor/warehouse (no Region->dimension relationships,
# which would create ambiguous filter paths to the facts).
#
# Kimball star schema consumed by the Direct Lake semantic model. Conformed dimensions are shared by every
# fact that carries them (`dim_date`, `dim_product`, `dim_region`, `dim_customer`, `dim_production_unit`).
#
# | Fact | Grain |
# |---|---|
# | fact_sales | invoice line |
# | fact_returns | return line |
# | fact_sales_target | month × region × category |
# | fact_inventory_snapshot | week × warehouse × product (batch) |
# | fact_distributor_month | month × distributor × product |
# | fact_demand_forecast | month × product |
# | fact_production | production order (month × plant × line × shift × product) |
# | fact_labour_month | month × plant × line × shift (**aggregated payroll – no employee rows**) |
# | fact_crm_opportunity / fact_crm_activity | opportunity / activity |
# | fact_promo_performance | promotion (pre-computed attribution) |
#
# Gold tables are small; they are fully rebuilt each run (cheaper and safer than incremental logic at this
# volume). `fact_sales` would switch to partition-overwrite by month at production scale.

# %%
from pyspark.sql import functions as F, Window as W
import datetime, json
S = "lh_silver"
def t(name): return spark.table(f"{S}.{name}")
from pyspark.sql.types import DecimalType
def normalise(df):
    """Power BI Decimal is fixed (19,4): money -> decimal(18,2); high-scale ratios -> double."""
    for f in df.schema.fields:
        if isinstance(f.dataType, DecimalType) and (f.dataType.precision > 18 or f.dataType.scale > 4):
            df = df.withColumn(f.name, F.col(f.name).cast("double" if f.dataType.scale > 2 else "decimal(18,2)"))
    return df
def save(df, name):
    df = normalise(df)
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .option("parquet.vorder.enabled", "true").saveAsTable(name))
    print(f"{name:<28} {spark.table(name).count():>7} rows")
def date_key(c): return F.date_format(c, "yyyyMMdd").cast("int")
NEAR_EXPIRY_REMAINING_PCT = 0.25   # business assumption: <=25% of shelf life left = at risk of expiry

# %% [markdown]
# ## Dimensions

# %%
d = spark.sql("SELECT explode(sequence(to_date('2025-01-01'), to_date('2026-12-31'), interval 1 day)) AS date")
last_actual = t("sales").agg(F.max("invoice_date")).first()[0]
dim_date = d.select(
    date_key("date").alias("date_key"), "date",
    F.year("date").alias("year"), F.quarter("date").alias("quarter"), F.month("date").alias("month_num"),
    F.date_format("date", "MMM").alias("month_name"), F.date_format("date", "yyyy-MM").alias("year_month"),
    F.trunc("date", "month").alias("month_start"), F.date_sub(F.next_day("date", "Sun"), 7).alias("week_start"),
    F.date_format("date", "EEE").alias("day_name"), F.dayofweek("date").alias("day_of_week"),
    F.dayofweek("date").isin(6, 7).alias("is_weekend"),              # Egypt weekend = Friday/Saturday
    (F.col("date") <= F.lit(last_actual)).alias("is_actuals_period"))
save(dim_date, "dim_date")

save(t("products").select(F.col("product_id").alias("product_key"), "sku", "product_name", "brand", "category", "pack_size",
     "list_price", "standard_cost", "shelf_life_days"), "dim_product")

regions = ["Cairo", "Giza", "Alexandria", "Delta", "Canal", "Upper Egypt"]
dim_region = spark.createDataFrame([(i + 1, r) for i, r in enumerate(regions)] + [(0, "Unknown")], "region_key int, region string")
save(dim_region, "dim_region")
rk = spark.table("dim_region")
def with_region(df, col="region"):
    return df.join(rk.withColumnRenamed("region", "_r"), F.col(col) == F.col("_r"), "left").drop("_r") \
             .withColumn("region_key", F.coalesce("region_key", F.lit(0)))

crm_cust = t("crm_accounts").where("customer_id is not null").select(F.col("customer_id").alias("customer_key")).distinct() \
    .withColumn("in_crm", F.lit(True))
dim_customer = with_region(t("customers").where("not is_duplicate")).select(
        F.col("customer_id").alias("customer_key"), "customer_name", "channel", "region_key", "region", "sales_territory", "is_strategic") \
    .join(crm_cust, "customer_key", "left").withColumn("in_crm", F.coalesce("in_crm", F.lit(False)))
save(dim_customer, "dim_customer")

save(with_region(t("distributors")).select(F.col("distributor_id").alias("distributor_key"), "distributor_name", "region_key", "region"), "dim_distributor")
save(with_region(t("warehouses")).select(F.col("warehouse_id").alias("warehouse_key"), "warehouse_name", "region_key", "region"), "dim_warehouse")

promo = with_region(t("promotions"))
dim_promotion = promo.select(F.col("promotion_id").alias("promotion_key"), F.concat(F.lit("PRM-"), F.col("promotion_id")).alias("promotion_code"),
        "promotion_type", F.col("product_id").alias("product_key"), "region_key", "start_date", "end_date", "discount_pct", "support_cost") \
    .unionByName(spark.createDataFrame([(-1, "No promotion", "None")], "promotion_key int, promotion_code string, promotion_type string"),
                 allowMissingColumns=True)
save(dim_promotion, "dim_promotion")

pu = t("production_orders").select("plant_id", "line_id", "shift").distinct() \
    .unionByName(t("hr_employees").select("plant_id", "line_id", "shift").distinct()).distinct()
dim_production_unit = pu.select(
    (F.col("plant_id") * 100 + F.col("line_id") * 10 + F.ascii("shift") - 64).alias("production_unit_key"),
    F.concat(F.lit("Plant "), F.col("plant_id")).alias("plant"), F.concat(F.lit("Line "), F.col("line_id")).alias("line"),
    F.concat(F.lit("Shift "), F.col("shift")).alias("shift"), "plant_id", "line_id",
    F.concat(F.lit("P"), F.col("plant_id"), F.lit("-L"), F.col("line_id"), F.lit("-"), F.col("shift")).alias("production_unit"))
save(dim_production_unit, "dim_production_unit")
def pu_key(): return (F.col("plant_id") * 100 + F.col("line_id") * 10 + F.ascii("shift") - 64)

# %% [markdown]
# ## Commercial facts

# %%
# Promotion attribution: an invoice line belongs to a promotion when product, conformed region and invoice
# date fall inside the promotion window (silver DQ rule PRM-01 guarantees no overlaps).
s = t("sales")
p = t("promotions").select("promotion_id", F.col("product_id").alias("_p"), F.col("region").alias("_pr"), "start_date", "end_date")
s_att = s.join(p, (s.product_id == p._p) & (s.region == p._pr) & s.invoice_date.between(p.start_date, p.end_date), "left") \
    .drop("_p", "_pr", "start_date", "end_date")
std = t("products").select("product_id", "standard_cost")
fact_sales = with_region(s_att.join(std, "product_id")).select(
    "invoice_id", date_key("invoice_date").alias("date_key"), F.col("master_customer_id").alias("customer_key"),
    F.col("product_id").alias("product_key"), F.col("distributor_id").alias("distributor_key"), "region_key",
    F.coalesce("promotion_id", F.lit(-1)).alias("promotion_key"),
    "quantity", "gross_sales", "discount_amount", "net_sales", "cogs",
    (F.col("quantity") * F.col("standard_cost")).cast("decimal(14,2)").alias("standard_cogs"),
    (F.col("customer_id") != F.col("master_customer_id")).alias("dq_duplicate_customer"),
    (F.col("region_raw") != F.col("region")).alias("dq_region_relabelled"))
save(fact_sales, "fact_sales")

inv_dates = s.select("invoice_id", date_key("invoice_date").alias("invoice_date_key"), F.col("distributor_id").alias("distributor_key"))
save(with_region(t("sales_returns")).join(inv_dates, "invoice_id", "left").select(
    "return_id", "invoice_id", date_key("return_date").alias("date_key"), "invoice_date_key",
    F.col("master_customer_id").alias("customer_key"), F.col("product_id").alias("product_key"), "region_key", "distributor_key",
    "returned_quantity", "return_value", "return_reason"), "fact_returns")

save(with_region(t("sales_targets")).select(date_key("month_start").alias("date_key"), "region_key", "category",
     "revenue_target", "volume_target"), "fact_sales_target")

# %%
# Promotion performance. Baseline = average daily units / gross profit of the same product+region in the
# 8 weeks before the promotion, excluding days covered by another promotion of that product+region.
daily = s_att.groupBy("product_id", "region", "invoice_date", "promotion_id").agg(
    F.sum("quantity").alias("u"), F.sum("net_sales").alias("ns"), F.sum(F.col("net_sales") - F.col("cogs")).alias("gp"),
    F.sum("discount_amount").alias("disc"))
pr = t("promotions")
promo_days = pr.select("promotion_id", "product_id", "region", "start_date", "end_date",
                       (F.datediff("end_date", "start_date") + 1).alias("promo_days"))
during = promo_days.join(daily.drop("promotion_id").alias("x"), ["product_id", "region"]) \
    .where(F.col("x.invoice_date").between(F.col("start_date"), F.col("end_date"))) \
    .groupBy("promotion_id").agg(F.sum("u").alias("promo_units"), F.sum("ns").alias("promo_net_sales"),
                                 F.sum("gp").alias("promo_gp"), F.sum("disc").alias("promo_invoice_discount"))
base = promo_days.join(daily.where("promotion_id is null").drop("promotion_id").alias("x"), ["product_id", "region"]) \
    .where(F.col("x.invoice_date").between(F.date_sub("start_date", 56), F.date_sub("start_date", 1))) \
    .groupBy("promotion_id").agg(F.sum("u").alias("base_units"), F.sum("gp").alias("base_gp"),
                                 F.countDistinct("x.invoice_date").alias("_d"))
perf = promo_days.join(during, "promotion_id", "left").join(base, "promotion_id", "left") \
    .join(pr.select("promotion_id", "promotion_type", "discount_pct", "support_cost"), "promotion_id") \
    .fillna(0, ["promo_units", "promo_net_sales", "promo_gp", "promo_invoice_discount", "base_units", "base_gp"]) \
    .withColumn("baseline_units", F.col("base_units") / 56 * F.col("promo_days")) \
    .withColumn("baseline_gp", F.col("base_gp") / 56 * F.col("promo_days")) \
    .withColumn("incremental_units", F.col("promo_units") - F.col("baseline_units")) \
    .withColumn("volume_lift_pct", F.when(F.col("baseline_units") > 0, F.col("incremental_units") / F.col("baseline_units"))) \
    .withColumn("incremental_gp", F.col("promo_gp") - F.col("baseline_gp")) \
    .withColumn("net_promo_return", F.col("incremental_gp") - F.col("support_cost")) \
    .withColumn("promo_roi", F.when(F.col("support_cost") > 0, F.col("net_promo_return") / F.col("support_cost"))) \
    .withColumn("discount_applied_on_invoice", F.col("promo_invoice_discount") / (F.col("promo_net_sales") + F.col("promo_invoice_discount"))) \
    .withColumn("baseline_measurable", F.col("_d") >= 28)
save(with_region(perf).select(F.col("promotion_id").alias("promotion_key"), date_key("start_date").alias("date_key"),
     F.col("product_id").alias("product_key"), "region_key",
     "promotion_type", "promo_days", "discount_pct", "discount_applied_on_invoice", "support_cost", "promo_units", "baseline_units",
     "incremental_units", "volume_lift_pct", "promo_net_sales", "promo_gp", "baseline_gp", "incremental_gp",
     "net_promo_return", "promo_roi", "baseline_measurable"), "fact_promo_performance")

# %% [markdown]
# ## Supply-chain facts

# %%
inv = with_region(t("inventory_snapshots").join(t("warehouses").select("warehouse_id", "region"), "warehouse_id")) \
    .join(t("products").select("product_id", "shelf_life_days", "standard_cost"), "product_id")
save(inv.select(date_key("snapshot_date").alias("date_key"), F.col("warehouse_id").alias("warehouse_key"),
     F.col("product_id").alias("product_key"), "region_key", "batch_id", "qty_on_hand", "qty_reserved", "qty_available_calc",
     "qty_available_reported", "days_to_expiry",
     (F.col("days_to_expiry") / F.col("shelf_life_days")).alias("remaining_shelf_life_pct"),
     (F.col("days_to_expiry") / F.col("shelf_life_days") <= NEAR_EXPIRY_REMAINING_PCT).alias("is_near_expiry"),
     (F.greatest(F.col("qty_on_hand"), F.lit(0)) * F.col("standard_cost")).cast("decimal(14,2)").alias("stock_value_std"),
     (F.col("qty_available_calc") <= 0).alias("is_zero_available")), "fact_inventory_snapshot")

# Distributor sell-in (ERP) vs distributor-reported sell-out and stock, one row per month × distributor × SKU
sellin = s.groupBy(F.trunc("invoice_date", "month").alias("month_start"), "distributor_id", "product_id") \
    .agg(F.sum("quantity").alias("sell_in_qty_erp"), F.sum("net_sales").alias("sell_in_value"))
so_out = t("dist_sellout").groupBy("month_start", "distributor_id", "product_id") \
    .agg(F.sum("quantity_sold").alias("sellout_qty_outlets"), F.sum("sellout_value").alias("sellout_value"),
         F.countDistinct("outlet_code").alias("active_outlets"))
di = t("dist_inventory").join(sellin, ["month_start", "distributor_id", "product_id"], "full") \
    .join(so_out, ["month_start", "distributor_id", "product_id"], "left")
save(with_region(di.join(t("distributors").select("distributor_id", "region"), "distributor_id", "left")).select(
     date_key("month_start").alias("date_key"), F.col("distributor_id").alias("distributor_key"), F.col("product_id").alias("product_key"),
     "region_key", "receipts_qty", "sell_in_qty_erp", "sell_in_value",
     (F.col("sell_in_value") / F.col("sell_in_qty_erp")).cast("decimal(12,4)").alias("sell_in_unit_price"), F.col("sellout_qty").alias("sellout_qty_reported"),
     "sellout_qty_outlets", "sellout_value", "active_outlets", "opening_inventory_qty", "closing_inventory_qty", "rollforward_gap_qty",
     (F.col("sku_mapping_status") != "mapped").alias("dq_sku_recovered")), "fact_distributor_month")

save(t("demand_forecast").select(date_key("month_start").alias("date_key"), F.col("product_id").alias("product_key"), "forecast_qty"),
     "fact_demand_forecast")

# %% [markdown]
# ## Manufacturing & workforce facts

# %%
dt = t("downtime").groupBy("production_order_id").agg(F.first("downtime_reason").alias("downtime_reason"))
mrp = t("material_requirements").groupBy("production_order_id").agg(F.max(F.col("is_shortage").cast("int")).cast("boolean").alias("material_shortage_flag"))
po = t("production_orders").join(dt, "production_order_id", "left").join(mrp, "production_order_id", "left") \
    .join(t("products").select("product_id", "standard_cost"), "product_id")
save(po.select("production_order_id", date_key("month_start").alias("date_key"), pu_key().alias("production_unit_key"),
     F.col("product_id").alias("product_key"), "planned_qty", "actual_qty", "good_qty", "scrap_qty", "downtime_minutes",
     "downtime_reason", "material_shortage_flag",
     (F.col("scrap_qty") * F.col("standard_cost")).cast("decimal(14,2)").alias("scrap_value_std"),
     (F.col("good_qty") * F.col("standard_cost")).cast("decimal(14,2)").alias("good_value_std")), "fact_production")

# Payroll is aggregated to plant × line × shift × month before it leaves silver (min. cell size checked below).
lab = t("hr_payroll").join(t("hr_attendance"), ["employee_id", "month_start"], "left").join(t("hr_employees"), "employee_id") \
    .groupBy("month_start", "plant_id", "line_id", "shift").agg(
        F.countDistinct("employee_id").alias("headcount"), F.sum("attendance_hours").alias("attendance_hours"),
        F.sum("absence_hours").alias("absence_hours"), F.sum("overtime_hours").alias("overtime_hours"),
        F.sum("overtime_cost").alias("overtime_cost"), F.sum("base_salary").alias("base_salary"),
        F.sum("allowances").alias("allowances"), F.sum("total_labor_cost").alias("total_labour_cost"))
MIN_CELL = 5
small = lab.where(F.col("headcount") < MIN_CELL).count()
assert small == 0, f"{small} labour cells below minimum aggregation size {MIN_CELL} - would expose individual pay"
save(lab.select(date_key("month_start").alias("date_key"), pu_key().alias("production_unit_key"), "headcount", "attendance_hours",
     "absence_hours", "overtime_hours", "overtime_cost", "base_salary", "allowances", "total_labour_cost"), "fact_labour_month")

# %% [markdown]
# ## CRM facts

# %%
acc = with_region(t("crm_accounts")).select("sf_account_id", F.col("customer_id").alias("customer_key"), "region_key")
save(t("crm_opportunities").join(acc, "sf_account_id", "left").select(
     "opportunity_id", date_key("created_month").alias("date_key"), "customer_key", "region_key", "opportunity_value", "stage",
     "opportunity_type", "is_open", "is_stale", (F.col("stage") == "Closed Won").alias("is_won"),
     date_key("expected_close_date").alias("expected_close_date_key")), "fact_crm_opportunity")
save(t("crm_activities").join(acc, "sf_account_id", "left").select(
     "activity_id", date_key("activity_date").alias("date_key"), "customer_key", "region_key", "activity_type", "duration_minutes"),
     "fact_crm_activity")

# %% [markdown]
# ## Data-quality summary & security mapping

# %%
save(t("dq_run_history").withColumn("_rn", F.row_number().over(W.partitionBy("rule_id").orderBy(F.col("run_at").desc())))
     .where("_rn = 1").drop("_rn"), "dq_summary")

# Row-level security mapping (maintained by the BI owner; in production sourced from an Entra ID group sync).
if not spark.catalog.tableExists("security_user_region"):
    sec = spark.createDataFrame([
        ("cairo.manager@dairyco.example", "Cairo"), ("alex.manager@dairyco.example", "Alexandria"),
        ("delta.manager@dairyco.example", "Delta"), ("delta.manager@dairyco.example", "Canal")], "user_upn string, region string")
    save(with_region(sec).select("user_upn", "region_key"), "security_user_region")
notebookutils.notebook.exit(json.dumps({"last_actual_date": str(last_actual)}))
