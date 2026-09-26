# 4. AI and advanced analytics

AI earns its place where a decision is repeated often, the pattern cannot be captured in a stable rule, and a better prediction changes the action taken. Where a rule is enough (for example "alert when distributor cover > 1 month"), plain BI or rules are cheaper, easier to explain and should be used instead.

## 4.1 Use case A (prototyped): SKU demand forecasting → production and stock rebalancing

| | |
|---|---|
| **Business problem** | The MRP forecast is biased by category: Milk is under-forecast by about 8% and Yogurt over-forecast by about 19%. The production plan copies the forecast almost 1:1 (r = 0.99999), so forecast error goes straight into stock-outs (Milk) and ageing stock (Yogurt, Juice, Cheese). This is the mechanism behind "stockouts while holding excess inventory". |
| **Users** | Demand planner (monthly S&OP), plant schedulers, DC managers. |
| **Why AI, not BI/rules** | Demand shifts by SKU (five Milk SKUs doubled while the rest fell 20–27%). A static rule like "last year + x%" cannot track that. A pooled ML model learns trend, seasonality and momentum across all SKUs at once and adapts each month. BI still does the *monitoring* (bias and WAPE measures). |
| **Data** | ERP sales by SKU × month (20 months), the MRP forecast (benchmark), product master (category, shelf life), and weekly warehouse stock for rebalancing. **Sufficient for a prototype, not for production.** It has one full seasonal cycle and no price, promotion calendar, distribution or holiday (Ramadan) drivers. Production would need 3+ years of history, the promo calendar, outlet sell-out and ideally weekly grain. |
| **Approach** | `HistGradientBoostingRegressor` (absolute-error loss) on lags 1/2/3/12, a 3-month rolling mean, 3-month growth, month of year, trend, category and SKU. **Rolling-origin backtest**: for each of the last 6 months, train only on earlier months, predict that month and compare against the MRP forecast and a naive "same as last month" forecast. Everything is logged to the MLflow experiment `dairyco-demand-forecast`, and the final model is registered as `dairyco-demand-forecast-hgb`. |
| **Embedding in the process** | The pipeline scores next month after every load and writes to `lh_gold.ml_demand_forecast`. The planner sees ML vs MRP side by side (Operations page) and overrides with reasons, which become training signal. `ml_stock_rebalancing` gives each warehouse × SKU a *Replenish / Hold / Reduce-redeploy* action against a target cover of 50% of shelf life. |
| **Value & success measures** | Lower forecast WAPE and bias (target: halve the Yogurt over-forecast), lower near-expiry stock value and expired returns, fewer zero-stock SKU-weeks for Milk, and more production runs matched to demand. Measure monthly against the MRP forecast as a champion/challenger. |
| **Risks & governance** | Short history (overfitting risk, mitigated by the out-of-sample backtest); the model does not know about promotions or new listings (planner override required); drift (monthly retrain with the backtest gate: promote only if WAPE beats the current model). The data contains no personal information. The model registry holds versioning and lineage, and there is a human in the loop for every production decision. |

**Prototype results** (6-month out-of-sample backtest, see `docs/findings_numbers.json`) are in section 4.4.

## 4.2 Use case B (designed): early-warning channel-risk score for distributors

| | |
|---|---|
| **Business problem** | Nile Distribution (301) tripled its stock and lost about 30% of sell-out while ERP showed it *growing* +5%. By the time sell-in drops, the revenue is already pulled forward and the stock is ageing in the channel. |
| **Users** | Channel sales manager and the Commercial Director (monthly distributor review). Credit control as a secondary user. |
| **Why AI** | The obvious case can be caught with a rule (sell-through < 85% for 2 months), and that rule is shipped now as the *Sell-through %* and *Distributor Months of Cover* measures. A model adds value in scoring *emerging* risk from several weak signals together: cover trend, sell-through, outlet count, return rate, SKU-mix drift and payment behaviour. It also ranks distributors by expected write-back or return exposure. |
| **Data** | The distributor platform (sell-out, stock, outlets), ERP sell-in and returns. **Partly sufficient.** With only 6 distributors there is too little history to train a supervised model. Start with an unsupervised anomaly score (isolation forest or robust z-scores on cover and sell-through) and graduate to supervised once outcomes (write-offs, credit notes) are recorded. Also needs AR/payment data. |
| **Embedding** | Monthly score per distributor with its top drivers on the Commercial page, plus an Activator alert when the score crosses a threshold. The rep must log an action (stock audit, reduced allocation, promotion to pull through). |
| **Value & measures** | Excess channel stock value, distributor cover back to peer level (about 0.6 months), fewer expired returns from distributors, and forecast quality of sell-in. |
| **Risks** | False positives damage relationships, so the score triggers a *review*, not a sanction. Explainability is mandatory (show drivers). Distributors are external parties, so their data sharing and use must be covered in the distributor agreement. |

## 4.3 Conversational analytics over trusted data

**Proposed design:** a **Fabric Data Agent** (or Copilot in Power BI) grounded on the certified `DairyCo Analytics` semantic model, not on raw tables.

* **Grounding.** The agent generates DAX against the semantic model, so every answer uses the same measures as the dashboards: *Net Revenue*, *Gross Margin %*, *Revenue Growth %* (like-for-like), *Stockout Proxy %*, and so on. All ~100 measures and every table and column carry business descriptions (built into the TMDL), which is what the agent reads to choose fields. Add agent instructions (e.g. "revenue means Net Revenue before returns; growth is like-for-like Jan–Aug") and **verified answers** for the 20 most common executive questions.
* **Security.** Queries execute as the signed-in user, so RLS (regional managers see their regions) and OLS (no labour cost for regional users) apply automatically. The agent cannot see anything the user cannot see in the report. It has no access to bronze or silver, so there is no path to employee-level payroll.
* **Semantic and business definitions.** A KPI glossary lives in the model descriptions and a governed "KPI definitions" page. Deliberately unreliable measures say so in their description (*Target Attainment %*: "UNRELIABLE AS ABSOLUTE"; *Stockout Proxy %*: "PROXY"), so the agent repeats the caveat rather than presenting a made-up number.
* **Reducing unsupported or misleading answers:**
  1. Restrict the agent to the certified model and a curated perspective (no technical or DQ columns).
  2. Always show the generated query and the measure used ("Answer based on *Revenue Growth %*, Jan–Aug 2026 vs 2025").
  3. Instruct it to refuse questions the data cannot answer (e.g. true stockout rate, cost-to-serve) and to name the missing data.
  4. Keep an evaluation set of 50 questions with known answers, re-run after every model change, and ship only if accuracy ≥ 95%.
  5. Log prompts and answers, and let users flag bad answers, which feed the verified-answers list.

## 4.4 Prototype results

See section 4.4 of the appendix (numbers populated from `findings_numbers.json`).
