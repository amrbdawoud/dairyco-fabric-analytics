# 5. Explainer briefs and likely reviewer questions

## 5.1 The architecture in plain English (60 seconds)

Five source systems drop files into a **landing zone**. A single **configuration file** lists every file, its format, owner and sensitivity, and one notebook ingests them all into **bronze** exactly as received, stamped with where and when they came from. **Silver** turns the raw data into clean, typed, consistent tables: one list of regions, one master customer, CRM and distributor IDs matched to ERP. Every data problem found is written to a **data-quality log** rather than hidden. **Gold** reshapes silver into a **star schema** (facts such as sales, stock and production, surrounded by shared dimensions such as date, product and region). The **semantic model** reads gold directly (**Direct Lake**) and holds every KPI definition once, with security. The **report**, the **AI forecast** and any future **Copilot / data agent** all use that one model, which is what ends "different functions reporting different versions of the same KPI". A **pipeline** runs the chain daily, and **Git plus Dev/Prod workspaces** control change.

## 5.2 The AI prototype in plain English (60 seconds)

The company's planning system forecasts demand for each product every month, and the factories produce exactly that forecast. It consistently forecasts too little Milk and too much Yogurt, so Milk runs short while Yogurt ages in the warehouse. We trained a machine-learning model on 20 months of sales. It looks at each product's recent months, its trend and the time of year, and learns patterns across all 24 products together. To test it honestly we **pretended to be in the past**: for each of the last six months we trained only on the data available before that month, predicted it, and compared the prediction with what actually sold, alongside the planning system's forecast for the same month. That comparison is the evidence (numbers in section 4.4). The model's forecast then sets a **target stock level** for each product in each warehouse (half its shelf life of cover), and each line is flagged *replenish*, *hold* or *reduce*. A planner stays in charge and can override it. The model only needs to beat the current forecast, not be perfect.

## 5.3 Likely questions and answers

**Why a lakehouse and notebooks rather than a warehouse?**
The sources include JSON API feeds and need MERGE, regex mapping and DQ logging, all of which Spark handles in one engine. If DairyCo's team is SQL-first, gold can move to a Fabric Warehouse without changing the semantic model or report. The trade-off is documented in section 1.2.

**Why three lakehouses instead of schemas?**
Security boundaries. Raw payroll only ever exists in bronze and silver, and business users never get access to those. With one lakehouse, everyone with access would share one permission surface.

**How is it incremental?**
Landing folders are dated. Bronze ingests only files not already logged. Silver's Sales table uses a watermark on ingestion time plus a Delta `MERGE` on InvoiceID. We proved it by loading up to July and then dropping an August file: 3,723 new lines merged, the watermark advanced, and a re-run changed nothing.

**What happens when a load fails?**
Each activity retries twice. A bad file is logged as FAILED and the other files continue. If a *value-breaking* rule fails in silver (net ≠ gross − discount, actual ≠ good + scrap), the pipeline stops before gold, so executives never see wrong numbers. Production would add an Activator/Teams alert on failure.

**Why Direct Lake?**
Gold is already Delta/Parquet in OneLake, so the model reads it in place. There is no import refresh, no second copy of the data, and new data appears as soon as gold is written. Import would be the right choice for non-Fabric sources or heavy calculated columns.

**How does RLS work, and how do you protect payroll?**
There is one *Regional Manager* role. A mapping table links each user's login to their regions, and the role filters the Region dimension, which filters every regional fact. Payroll is protected in three layers: employee-level pay never reaches gold (aggregated to plant/line/shift with at least 5 people per cell); labour cost columns are hidden from regional managers by object-level security; and bronze/silver are engineering-only.

**Why is target attainment shown as an index?**
Targets are about 24× actual revenue, and every target implies exactly 35 EGP per unit. That is a units or definition problem in the target file. The brief says not to create unsupported metrics, so the absolute percentage is flagged and the index (region vs company average) is used until Finance restates the targets.

**Why is stockout rate a proxy?**
Measuring stockouts needs demand that could not be served: order lines with requested vs delivered quantity, or outlet out-of-stock checks. None exist, and the stock status field is always "Available". We show the share of warehouse-SKU-weeks with zero available stock (0.26%) and name the data needed.

**How did the numbers change from the first presentation?**
They were recomputed from the governed gold layer. The story is the same, with more depth and firmer evidence. Leak 5 moved from "promotions cannot be measured" to "promotions *can* be measured and they do not pay back", because the promotion-to-invoice link was rebuilt by product, region and date.

**How would you take this to production?**
See section 3.2: Dev/Test/Prod on dedicated capacity, Git with pull-request review, automated deployment with stage rules, a Variable Library for thresholds, Activator alerts, DQ thresholds with named owners, a certified model in the OneLake catalog, and a KPI council that owns the definitions.

**What would you do next with more time?**
1. A reconciled distributor data contract (roll-forward must balance).
2. Order-line data to build a true fill-rate and stockout KPI.
3. A promotion calendar feature and weekly grain for the forecast.
4. A cost-to-serve model by channel.
5. A data agent with verified answers for the executive team.
