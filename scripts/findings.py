"""Recompute the headline and the five profit leaks from the GOLD layer (same logic as the DAX measures).
Writes docs/findings_numbers.json so every figure in the deck/appendix is traceable to one script run."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import duckdb
from olq import table

T = ["dim_date", "dim_product", "dim_region", "dim_distributor", "dim_production_unit", "fact_sales", "fact_returns",
     "fact_inventory_snapshot", "fact_distributor_month", "fact_demand_forecast", "fact_production", "fact_labour_month",
     "fact_promo_performance", "fact_sales_target", "dq_summary", "ml_demand_forecast", "ml_stock_rebalancing"]
con = duckdb.connect()
for t in T:
    con.register(t, table("lh_gold", t))
def one(sql): return con.sql(sql).fetchone()
def df(sql): return con.sql(sql).df()
R = {}

# ---------- Headline: YTD Jan-Aug 2026 vs Jan-Aug 2025
yoy = df("""SELECT d.year, SUM(net_sales) rev, SUM(quantity) vol, SUM(net_sales-cogs) gp, SUM(cogs-standard_cogs) cost_var
            FROM fact_sales s JOIN dim_date d USING(date_key) WHERE d.month_num<=8 GROUP BY 1 ORDER BY 1""")
a, b = yoy.iloc[0], yoy.iloc[1]
R["headline"] = dict(rev_2025=float(a.rev), rev_2026=float(b.rev), rev_growth=float(b.rev/a.rev-1), vol_growth=float(b.vol/a.vol-1),
                     gp_2025=float(a.gp), gp_2026=float(b.gp), gp_growth=float(b.gp/a.gp-1), gm_2025=float(a.gp/a.rev), gm_2026=float(b.gp/b.rev))
# margin bridge: mix effect = GM at 2025 category margins with 2026 mix
cat = df("""SELECT d.year, p.category, SUM(net_sales) rev, SUM(net_sales-cogs) gp, SUM(net_sales-standard_cogs) gp_std
            FROM fact_sales s JOIN dim_date d USING(date_key) JOIN dim_product p ON p.product_key=s.product_key
            WHERE d.month_num<=8 GROUP BY 1,2""")
c25 = cat[cat.year == 2025].set_index("category"); c26 = cat[cat.year == 2026].set_index("category")
gm_mix = float(((c26.rev / c26.rev.sum()) * (c25.gp / c25.rev)).sum())
gm_std26 = float(c26.gp_std.sum() / c26.rev.sum())
R["margin_bridge"] = dict(gm_2025=R["headline"]["gm_2025"], after_mix=gm_mix, after_cost=R["headline"]["gm_2026"],
                          mix_pp=gm_mix - R["headline"]["gm_2025"], other_pp=gm_std26 - gm_mix, cost_pp=R["headline"]["gm_2026"] - gm_std26,
                          milk_share_2025=float(c25.rev["Milk"] / c25.rev.sum()), milk_share_2026=float(c26.rev["Milk"] / c26.rev.sum()),
                          cat_growth={k: float(c26.rev[k] / c25.rev[k] - 1) for k in c25.index},
                          cat_gm_2025={k: float(c25.gp[k] / c25.rev[k]) for k in c25.index}, cat_gm_2026={k: float(c26.gp[k] / c26.rev[k]) for k in c26.index})
R["monthly"] = df("""SELECT d.year_month, SUM(net_sales) rev, SUM(net_sales-cogs)/SUM(net_sales) gm, SUM(quantity) vol
                     FROM fact_sales s JOIN dim_date d USING(date_key) GROUP BY 1 ORDER BY 1""").to_dict("records")

# ---------- Leak 1: standard cost variance
l1 = df("""SELECT d.year, p.category, SUM(cogs-standard_cogs) cost_var, SUM(cogs)/SUM(standard_cogs) ratio
           FROM fact_sales s JOIN dim_date d USING(date_key) JOIN dim_product p ON p.product_key=s.product_key
           GROUP BY 1,2 HAVING ABS(SUM(cogs-standard_cogs))>1 ORDER BY 1,2""")
skus = df("""SELECT p.sku, SUM(cogs)/SUM(standard_cogs) ratio FROM fact_sales s JOIN dim_date d USING(date_key)
             JOIN dim_product p ON p.product_key=s.product_key WHERE d.year=2026 GROUP BY 1 HAVING ratio>1.001 ORDER BY 1""")
R["leak1_standard_cost"] = dict(cost_variance_2026=float(l1[l1.year==2026].cost_var.sum()), by_cat=l1.to_dict("records"), skus=skus.to_dict("records"),
                                milk_gm_at_std_2026=float(c26.gp_std["Milk"] / c26.rev["Milk"]), milk_gm_actual_2026=float(c26.gp["Milk"] / c26.rev["Milk"]))

# ---------- Leak 2: plant / shift performance and avoidable scrap (benchmark = Plant 1 shifts A/B)
pr = df("""SELECT u.plant, u.shift, SUM(planned_qty) plan, SUM(actual_qty) act, SUM(good_qty) good, SUM(scrap_qty) scrap,
                  SUM(downtime_minutes)/COUNT(*) dt_per_order, COUNT(*) orders, SUM(scrap_value_std) scrap_cost
           FROM fact_production f JOIN dim_production_unit u USING(production_unit_key) GROUP BY 1,2 ORDER BY 1,2""")
bench = one("""SELECT SUM(scrap_qty)/SUM(actual_qty) FROM fact_production f JOIN dim_production_unit u USING(production_unit_key)
               WHERE u.plant='Plant 1' AND u.shift IN ('Shift A','Shift B')""")[0]
avoid = one(f"""SELECT SUM(GREATEST(0, scrap_qty - actual_qty*{bench}) * scrap_value_std/NULLIF(scrap_qty,0)) FROM fact_production""")[0]
tot = one("SELECT SUM(planned_qty), SUM(actual_qty), SUM(good_qty), SUM(scrap_qty), SUM(scrap_value_std) FROM fact_production")
lab = df("""SELECT u.plant, u.shift, SUM(overtime_hours)/SUM(headcount) ot_per_emp, SUM(absence_hours)/(SUM(attendance_hours)+SUM(absence_hours)) absence,
                   SUM(overtime_cost) ot_cost, SUM(total_labour_cost) labour
            FROM fact_labour_month l JOIN dim_production_unit u USING(production_unit_key) GROUP BY 1,2 ORDER BY 1,2""")
# overtime premium above the benchmark cells
ot_bench = one("""SELECT SUM(overtime_cost)/SUM(total_labour_cost) FROM fact_labour_month l JOIN dim_production_unit u USING(production_unit_key)
                  WHERE u.plant='Plant 1' AND u.shift IN ('Shift A','Shift B')""")[0]
ot_excess = one(f"""SELECT SUM(GREATEST(0, overtime_cost - total_labour_cost*{ot_bench})) FROM fact_labour_month""")[0]
ot_trend = df("""SELECT d.year, SUM(overtime_cost) ot FROM fact_labour_month l JOIN dim_date d USING(date_key) WHERE d.month_num<=8 GROUP BY 1 ORDER BY 1""")
cells = df("""SELECT l.date_key, l.production_unit_key, SUM(l.overtime_hours)/SUM(l.headcount) ot, MAX(p.scrap) scrap FROM fact_labour_month l
              JOIN (SELECT date_key, production_unit_key, SUM(scrap_qty)/SUM(actual_qty) scrap FROM fact_production GROUP BY 1,2) p USING(date_key, production_unit_key)
              GROUP BY 1,2""")
bench_p1 = one("""SELECT SUM(scrap_qty)/SUM(actual_qty) FROM fact_production f JOIN dim_production_unit u USING(production_unit_key) WHERE u.plant='Plant 1'""")[0]
avoid_p1 = one(f"""SELECT SUM(GREATEST(0, scrap_qty - actual_qty*{bench_p1}) * scrap_value_std/NULLIF(scrap_qty,0)) FROM fact_production""")[0]
avoid_by_year = df(f"""SELECT d.year, SUM(GREATEST(0, scrap_qty - actual_qty*{bench}) * scrap_value_std/NULLIF(scrap_qty,0)) stretch,
                          SUM(GREATEST(0, scrap_qty - actual_qty*{bench_p1}) * scrap_value_std/NULLIF(scrap_qty,0)) conservative
                   FROM fact_production f JOIN dim_date d USING(date_key) GROUP BY 1 ORDER BY 1""")
R["leak2_plant"] = dict(benchmark_plant1_avg=bench_p1, avoidable_scrap_cost_conservative=float(avoid_p1), avoidable_by_year=avoid_by_year.to_dict("records"), plan_attainment=tot[1] / tot[0], good_attainment=tot[2] / tot[0], scrap_rate=tot[3] / tot[1], scrap_cost_total=float(tot[4]),
                        benchmark_scrap=bench, avoidable_scrap_cost=float(avoid), by_plant_shift=pr.to_dict("records"),
                        labour=lab.to_dict("records"), ot_benchmark_share=ot_bench, excess_overtime_cost=float(ot_excess),
                        ot_ytd_by_year=ot_trend.to_dict("records"), corr_ot_scrap_cells=float(cells.ot.corr(cells.scrap)))

# ---------- Leak 3: distributor channel stock
dm = df("""SELECT d.year, dm.distributor_key, SUM(receipts_qty) sell_in, SUM(sellout_qty_reported) sell_out
           FROM fact_distributor_month dm JOIN dim_date d USING(date_key) WHERE d.month_num<=8 GROUP BY 1,2 ORDER BY 2,1""")
last_k = one("SELECT MAX(date_key) FROM fact_distributor_month")[0]
stock = df(f"""SELECT dm.distributor_key, di.distributor_name, SUM(closing_inventory_qty) stock, SUM(sellout_qty_reported) so_month,
                  SUM(closing_inventory_qty*sell_in_unit_price) stock_value,
                  SUM(GREATEST(0, closing_inventory_qty - 0.6*sellout_qty_reported)*sell_in_unit_price) excess_value
               FROM fact_distributor_month dm JOIN dim_distributor di USING(distributor_key) WHERE date_key={last_k} GROUP BY 1,2 ORDER BY 1""")
d301 = df("""SELECT d.year_month, SUM(receipts_qty) sell_in, SUM(sellout_qty_reported) sell_out, SUM(closing_inventory_qty) stock
             FROM fact_distributor_month dm JOIN dim_date d USING(date_key) WHERE distributor_key=301 GROUP BY 1 ORDER BY 1""")
R["leak3_channel"] = dict(ytd=dm.to_dict("records"), last_month_stock=stock.to_dict("records"), nile_monthly=d301.to_dict("records"),
                          nile_excess_value=float(stock[stock.distributor_key == 301].excess_value.iloc[0]))

# ---------- Leak 4: inventory vs demand, near-expiry (<=25% shelf life left)
inv = df("""SELECT category, AVG(nx) avg_near_expiry_value, AVG(stock) avg_stock_value FROM (
              SELECT i.date_key, p.category, SUM(CASE WHEN is_near_expiry THEN stock_value_std ELSE 0 END) nx, SUM(stock_value_std) stock
              FROM fact_inventory_snapshot i JOIN dim_product p USING(product_key) GROUP BY 1,2) x GROUP BY 1 ORDER BY 1""")
nx_share = one("""SELECT AVG(nx/stock) FROM (SELECT date_key, SUM(CASE WHEN is_near_expiry THEN stock_value_std ELSE 0 END) nx, SUM(stock_value_std) stock
                  FROM fact_inventory_snapshot GROUP BY 1)""")[0]
last_i = one("SELECT MAX(date_key) FROM fact_inventory_snapshot")[0]
nx_last = one(f"SELECT SUM(CASE WHEN is_near_expiry THEN stock_value_std END), SUM(stock_value_std) FROM fact_inventory_snapshot WHERE date_key={last_i}")
cover = df("""WITH st AS (SELECT d.year, i.product_key, AVG(q) units FROM (SELECT date_key, product_key, SUM(qty_on_hand) q FROM fact_inventory_snapshot GROUP BY 1,2) i
                          JOIN dim_date d USING(date_key) GROUP BY 1,2),
              dem AS (SELECT d.year, s.product_key, SUM(quantity)/COUNT(DISTINCT d.date) daily FROM fact_sales s JOIN dim_date d USING(date_key) GROUP BY 1,2)
              SELECT st.year, p.category, SUM(units)/SUM(daily) cover_days, MIN(p.shelf_life_days) shelf_life
              FROM st JOIN dem USING(year, product_key) JOIN dim_product p USING(product_key) GROUP BY 1,2 ORDER BY 2,1""")
fc = df("""SELECT d.year, p.category, SUM(f.forecast_qty) fc, SUM(a.q) act FROM fact_demand_forecast f JOIN dim_date d USING(date_key)
           JOIN dim_product p USING(product_key)
           JOIN (SELECT dd.month_start, s.product_key, SUM(quantity) q FROM fact_sales s JOIN dim_date dd USING(date_key) GROUP BY 1,2) a
             ON a.month_start=d.date AND a.product_key=f.product_key GROUP BY 1,2 ORDER BY 2,1""")
fc["bias"] = fc.fc / fc.act - 1
stockout = one("SELECT AVG(CASE WHEN is_zero_available THEN 1.0 ELSE 0 END) FROM fact_inventory_snapshot")[0]
R["leak4_inventory"] = dict(avg_near_expiry_share=nx_share, avg_near_expiry_by_cat=inv.to_dict("records"), avg_near_expiry_total=float(inv.avg_near_expiry_value.sum()),
                            near_expiry_last_snapshot=float(nx_last[0]), stock_value_last_snapshot=float(nx_last[1]),
                            cover_days=cover.to_dict("records"), forecast_bias=fc.to_dict("records"), stockout_proxy=stockout)

# ---------- Leak 5: promotions
pp = df("SELECT * FROM fact_promo_performance")
m = pp[pp.baseline_measurable]
R["leak5_promo"] = dict(n=len(pp), measurable=len(m), support_total=float(pp.support_cost.sum()), incremental_gp=float(pp.incremental_gp.sum()),
                        net_return=float(pp.net_promo_return.sum()), paying_back=int((m.net_promo_return > 0).sum()),
                        avg_lift=float(m.volume_lift_pct.mean()), median_lift=float(m.volume_lift_pct.median()),
                        stated_discount_avg=float(pp.discount_pct.astype(float).mean()),
                        applied_discount_avg=float(pp[pp.promotion_key != 9999].discount_applied_on_invoice.mean()),
                        p9999=pp[pp.promotion_key == 9999].to_dict("records"))
promo_share = df("""SELECT d.year, SUM(CASE WHEN promotion_key<>-1 THEN net_sales END)/SUM(net_sales) promo_share FROM fact_sales s JOIN dim_date d USING(date_key) GROUP BY 1""")
R["leak5_promo"]["promoted_revenue_share"] = promo_share.to_dict("records")
R["leak5_promo"]["support_vs_gp_pct"] = float(pp.support_cost.sum()) / float(one("SELECT SUM(net_sales-cogs) FROM fact_sales")[0])

# ---------- Other
R["returns"] = df("""SELECT d.year, SUM(return_value) rv FROM fact_returns r JOIN dim_date d USING(date_key) GROUP BY 1""").to_dict("records")
R["return_rate_total"] = one("SELECT (SELECT SUM(return_value) FROM fact_returns)/(SELECT SUM(net_sales) FROM fact_sales)")[0]
R["target_attainment"] = one("SELECT (SELECT SUM(net_sales) FROM fact_sales)/(SELECT SUM(revenue_target) FROM fact_sales_target)")[0]
R["dq"] = df("SELECT rule_id, rule, severity, violations FROM dq_summary ORDER BY rule_id").to_dict("records")
ml = df("SELECT * FROM ml_demand_forecast WHERE record_type='backtest'")
w = lambda c: float((ml[c] - ml.actual_qty).abs().sum() / ml.actual_qty.sum())
b_ = lambda c: float((ml[c] - ml.actual_qty).sum() / ml.actual_qty.sum())
R["ml"] = dict(wape_ml=w("ml_forecast"), wape_mrp=w("mrp_forecast"), wape_naive=w("naive_forecast"), wape_rule=w("rule_forecast"),
               bias_ml=b_("ml_forecast"), bias_mrp=b_("mrp_forecast"), months=int(ml.date_key.nunique()),
               rebalancing=df("SELECT action, COUNT(*) n, SUM(stock_gap_value) gap_value FROM ml_stock_rebalancing GROUP BY 1").to_dict("records"))
mlc = ml.merge(con.sql("SELECT product_key, category FROM dim_product").df(), on="product_key")
R["ml"]["by_category"] = {c: {"ml": float((g.ml_forecast - g.actual_qty).abs().sum() / g.actual_qty.sum()),
                              "mrp": float((g.mrp_forecast - g.actual_qty).abs().sum() / g.actual_qty.sum()),
                              "rule": float((g.rule_forecast - g.actual_qty).abs().sum() / g.actual_qty.sum())} for c, g in mlc.groupby("category")}

out = pathlib.Path(__file__).resolve().parents[1] / "docs" / "findings_numbers.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(R, indent=1, default=str))
print(json.dumps({k: v for k, v in R.items() if k not in ("monthly",)}, indent=1, default=str)[:12000])
