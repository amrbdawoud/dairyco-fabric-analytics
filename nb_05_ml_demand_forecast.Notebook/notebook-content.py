# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e874ccb7-c908-445a-9469-181d36b50b7b",
# META       "default_lakehouse_name": "lh_gold",
# META       "default_lakehouse_workspace_id": "13f3caf0-07d5-45b6-aba0-319b493a9692"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_05_ml_demand_forecast — AI use case prototype
# **Business problem:** the MRP forecast under-forecasts Milk (~-8%) and over-forecasts Yogurt (~+19%), and the
# production plan copies it 1:1, so forecast error flows straight into stock-outs (Milk) and ageing stock (Yogurt).
# 
# **Approach:** the MRP forecast's error is a stable, SKU-specific bias rather than noise, so the model is a
# *correction layer*: gradient-boosted trees that take the MRP forecast plus the SKU's recent forecast bias, lags,
# rolling means, seasonality and category, and predict actual demand. It is evaluated with a **rolling-origin
# backtest** against three challengers: the incumbent MRP forecast, a naive "same as last month" forecast and a
# simple *rule* (MRP × trailing 3-month actual/forecast ratio) - so we can see whether ML beats a rule at all. Everything is tracked in an MLflow experiment; the best model scores next month
# and the result feeds a stock-cover rebalancing table in gold.
# 
# **Honest limits:** 20 months of history (one full seasonal cycle + 8 months), monthly grain, no price/promo
# calendar in the feature set (promotions show ~0 lift so omitted), no external drivers (weather, Ramadan).
# Output is decision *support* for the demand planner, not an automated order.

# PARAMETERS CELL ********************

batch_id = ""
backtest_months = "6"

# CELL ********************

import json, numpy as np, pandas as pd, mlflow
from sklearn.ensemble import HistGradientBoostingRegressor
from pyspark.sql import functions as F

BT = int(backtest_months)
sales = spark.sql("""
    SELECT d.month_start, s.product_key, SUM(s.quantity) AS actual_qty
    FROM fact_sales s JOIN dim_date d ON s.date_key = d.date_key
    GROUP BY d.month_start, s.product_key""").toPandas()
mrp = spark.sql("""SELECT d.date AS month_start, f.product_key, f.forecast_qty AS mrp_forecast
                   FROM fact_demand_forecast f JOIN dim_date d ON f.date_key = d.date_key""").toPandas()
prod = spark.table("dim_product").select("product_key", "category", "shelf_life_days").toPandas()
df = sales.merge(mrp, on=["month_start", "product_key"], how="left").merge(prod, on="product_key")
df["month_start"] = pd.to_datetime(df["month_start"])
mrp["month_start"] = pd.to_datetime(mrp["month_start"])
df = df.sort_values(["product_key", "month_start"]).reset_index(drop=True)
months = sorted(df["month_start"].unique())
print(f"{df.product_key.nunique()} SKUs × {len(months)} months, backtest on last {BT} months")

# CELL ********************

def features(d):
    d = d.sort_values(["product_key", "month_start"]).reset_index(drop=True)
    g = d.groupby("product_key")["actual_qty"]
    for k in (1, 2, 3, 12):
        d[f"lag_{k}"] = g.shift(k)
    roll3 = lambda s: s.shift(1).rolling(3).mean()          # per-SKU, uses only past months
    d["roll_mean_3"] = g.transform(roll3)
    # How far the incumbent MRP forecast has been off for this SKU recently (known at forecast time)
    d["_ratio"] = d["actual_qty"] / d["mrp_forecast"]
    d["mrp_bias_ratio_3"] = d.groupby("product_key")["_ratio"].transform(roll3)
    for k in (1, 2, 3):
        d[f"mrp_ratio_lag_{k}"] = d.groupby("product_key")["_ratio"].shift(k)
    d = d.drop(columns="_ratio")
    d["growth_3m"] = d["lag_1"] / d.groupby("product_key")["actual_qty"].shift(4) - 1
    d["month_of_year"] = d["month_start"].dt.month
    d["t"] = (d["month_start"].dt.year - 2025) * 12 + d["month_start"].dt.month
    d["cat_code"] = d["category"].astype("category").cat.codes
    return d

FEATS = ["mrp_bias_ratio_3", "mrp_ratio_lag_1", "mrp_ratio_lag_2", "mrp_ratio_lag_3", "growth_3m",
         "month_of_year", "cat_code", "product_key"]
fx = features(df)

def fit(train):
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=8,
                                      loss="absolute_error", random_state=42)
    tr = train.dropna(subset=["mrp_ratio_lag_1", "mrp_ratio_lag_2", "mrp_ratio_lag_3"])
    # Target = correction ratio actual / MRP forecast; the forecast is MRP x predicted ratio.
    m.fit(tr[FEATS], tr["actual_qty"] / tr["mrp_forecast"], sample_weight=tr["mrp_forecast"])
    return m

def predict(m, d):
    return np.maximum(m.predict(d[FEATS]) * d["mrp_forecast"], 0).round()

# Rolling-origin backtest: for each of the last BT months train only on earlier months, predict that month.
rows = []
for m_ in months[-BT:]:
    model = fit(fx[fx.month_start < m_])
    te = fx[fx.month_start == m_].copy()
    te["ml_forecast"] = predict(model, te)
    te["naive_forecast"] = te["lag_1"]
    # Rule-based challenger: scale the MRP forecast by the SKU's trailing 3-month actual/forecast ratio
    te["rule_forecast"] = (te["mrp_forecast"] * te["mrp_bias_ratio_3"]).round()
    rows.append(te)
bt = pd.concat(rows)

def metrics(d, col):
    err = d[col] - d["actual_qty"]
    return {"wape": float(err.abs().sum() / d["actual_qty"].sum()), "bias": float(err.sum() / d["actual_qty"].sum()),
            "mape": float((err.abs() / d["actual_qty"]).mean())}
MODELS = ["mrp_forecast", "naive_forecast", "rule_forecast", "ml_forecast"]
res = {c: metrics(bt, c) for c in MODELS}
by_cat = {cat: {c: metrics(g, c) for c in MODELS} for cat, g in bt.groupby("category")}
print(json.dumps(res, indent=1)); print(json.dumps(by_cat, indent=1))

# CELL ********************

mlflow.set_experiment("dairyco-demand-forecast")
with mlflow.start_run(run_name=f"hgb-backtest-{batch_id or 'manual'}") as run:
    mlflow.log_params({"model": "HistGradientBoostingRegressor", "target": "actual/mrp_forecast ratio", "loss": "absolute_error", "max_iter": 300,
                       "learning_rate": 0.05, "max_depth": 4, "features": ",".join(FEATS), "design": "ML correction layer on top of MRP forecast", "backtest_months": BT})
    for c, m in res.items():
        for k, v in m.items():
            mlflow.log_metric(f"{c}_{k}", v)
    for cat, d in by_cat.items():
        for c in MODELS:
            mlflow.log_metric(f"wape_{c}_{cat}", d[c]["wape"])
    final = fit(fx)
    mlflow.sklearn.log_model(final, "model", registered_model_name="dairyco-demand-forecast-hgb",
                             input_example=fx.dropna(subset=FEATS)[FEATS].head(3))
    run_id = run.info.run_id

# CELL ********************

# Score next month (first month after actuals) with the model trained on all history.
nxt = months[-1] + pd.offsets.MonthBegin(1)
future = pd.concat([df, pd.DataFrame({"month_start": nxt, "product_key": prod.product_key, "actual_qty": np.nan})
                    .merge(prod, on="product_key")])
fut = features(future)
fut = fut[fut.month_start == nxt].copy()
mrp_pd = mrp.assign(month_start=pd.to_datetime(mrp.month_start))
fut = fut.drop(columns=["mrp_forecast"]).merge(mrp_pd, on=["month_start", "product_key"], how="left")
# MRP forecast for the next month is not in the extract; carry the latest MRP forecast as the planning input.
last_mrp = mrp_pd[mrp_pd.month_start == mrp_pd.month_start.max()].set_index("product_key")["mrp_forecast"]
fut["mrp_forecast"] = fut["mrp_forecast"].fillna(fut["product_key"].map(last_mrp))
fut["ml_forecast"] = predict(final, fut)
fut["naive_forecast"] = fut["lag_1"]
fut["rule_forecast"] = (fut["mrp_forecast"] * fut["mrp_bias_ratio_3"]).round()

out = pd.concat([bt.assign(record_type="backtest"), fut.assign(record_type="forecast")])[
    ["month_start", "product_key", "record_type", "actual_qty", "mrp_forecast", "naive_forecast", "rule_forecast", "ml_forecast"]]
out["model_run_id"] = run_id
sdf = spark.createDataFrame(out.astype({c: "float" for c in ["actual_qty", "mrp_forecast", "naive_forecast", "rule_forecast", "ml_forecast"]}))
sdf = sdf.withColumn("date_key", F.date_format("month_start", "yyyyMMdd").cast("int")).drop("month_start")
sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("ml_demand_forecast")

# MARKDOWN ********************

# ## Stock rebalancing recommendation
# Target stock per warehouse × SKU = forecast daily demand for that region × target cover days, where target
# cover = 50% of shelf life (never plan to hold stock into the last half of its life). Regional demand share
# comes from the last 3 months of sell-in. Positive gap = excess to redeploy / stop producing; negative = at risk
# of stock-out.

# CELL ********************

reb = spark.sql(f"""
WITH last_snap AS (SELECT MAX(date_key) k FROM fact_inventory_snapshot),
stock AS (SELECT i.warehouse_key, i.product_key, i.region_key, SUM(GREATEST(i.qty_on_hand,0)) on_hand,
                 SUM(CASE WHEN i.is_near_expiry THEN GREATEST(i.qty_on_hand,0) END) near_expiry
          FROM fact_inventory_snapshot i, last_snap WHERE i.date_key = last_snap.k GROUP BY 1,2,3),
recent AS (SELECT s.product_key, s.region_key, SUM(s.quantity) q FROM fact_sales s JOIN dim_date d ON s.date_key=d.date_key
           WHERE d.month_start >= add_months((SELECT MAX(month_start) FROM dim_date WHERE is_actuals_period), -2)
           GROUP BY 1,2),
share AS (SELECT product_key, region_key, q / SUM(q) OVER (PARTITION BY product_key) region_share FROM recent),
fc AS (SELECT product_key, ml_forecast FROM ml_demand_forecast WHERE record_type = 'forecast')
SELECT st.warehouse_key, st.product_key, st.region_key, st.on_hand, COALESCE(st.near_expiry,0) near_expiry_qty,
       fc.ml_forecast * sh.region_share / 30.0 AS forecast_daily_demand,
       p.shelf_life_days * 0.5 AS target_cover_days,
       st.on_hand / NULLIF(fc.ml_forecast * sh.region_share / 30.0, 0) AS current_cover_days,
       fc.ml_forecast * sh.region_share / 30.0 * p.shelf_life_days * 0.5 AS target_stock,
       st.on_hand - fc.ml_forecast * sh.region_share / 30.0 * p.shelf_life_days * 0.5 AS stock_gap,
       (st.on_hand - fc.ml_forecast * sh.region_share / 30.0 * p.shelf_life_days * 0.5) * p.standard_cost AS stock_gap_value
FROM stock st JOIN share sh ON st.product_key = sh.product_key AND st.region_key = sh.region_key
JOIN fc ON fc.product_key = st.product_key JOIN dim_product p ON p.product_key = st.product_key""")
reb = reb.withColumn("action", F.when(F.col("current_cover_days") > F.col("target_cover_days") * 1.5, "Reduce / redeploy")
                               .when(F.col("current_cover_days") < F.col("target_cover_days") * 0.75, "Replenish")
                               .otherwise("Hold")).withColumn("model_run_id", F.lit(run_id))
reb.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("ml_stock_rebalancing")
display(reb.groupBy("action").agg(F.count("*").alias("n"), F.sum("stock_gap_value").alias("gap_value")))
notebookutils.notebook.exit(json.dumps({"run_id": run_id, **{k: round(v["wape"], 4) for k, v in res.items()}}))
