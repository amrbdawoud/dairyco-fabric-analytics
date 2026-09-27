# 3. Security and production readiness

## 3.1 Protecting payroll and commercially sensitive data

| Control | Implemented in the prototype | Production hardening |
|---|---|---|
| **Data minimisation** | Employee-level payroll stays in `lh_silver`; gold only holds plant × line × shift × month aggregates, with an assertion that no cell has fewer than 5 employees (prevents re-identifying one person's pay). | Keep. Add a separate HR workspace for silver HR tables. |
| **Layer isolation** | Three lakehouses. Bronze/silver are engineering-only; business users never get lakehouse or SQL endpoint access, only Build/Read on the semantic model. | Separate *Data Engineering* and *BI* workspaces; OneLake data access roles on bronze/silver folders; sensitivity labels (Confidential – HR) on HR tables and the model. |
| **Row-level security** | Dynamic RLS role *Regional Manager*: `Region[Region Key] IN <regions mapped to USERPRINCIPALNAME()>`, plus matching filters on Customer, Distributor and Warehouse. *Executive* role has no filter. | Mapping table fed from Entra ID security groups (one group per region); role membership assigned to groups, never individuals; test with "View as role" in every release. |
| **Object-level security** | Labour cost columns (`Total Labour Cost`, `Overtime Cost`, `Base Salary`, `Allowances`) are `none` for Regional Managers — they see hours, absence and scrap, not pay. | Extend OLS to margin/COGS for any external (distributor-facing) audience. |
| **Commercial data** | Cost, margin and promotion ROI live only in the governed model; the report is shared, the lakehouse is not. | Disable "export underlying data" for non-executives; Purview DLP policies on the model; audit logs to Log Analytics. |
| **Direct Lake identity** | Uses the viewer's identity (SSO) against `lh_gold`. | Switch to a fixed-identity cloud connection (service principal) so viewers need no lakehouse permission at all; RLS still applies in the model. |
| **AI** | ML trains on aggregated sales only; no personal data. Conversational analytics runs through the semantic model, so RLS/OLS apply to every AI answer. | Data agent limited to the certified model; prompts/answers logged; Copilot tenant settings scoped to a security group. |

## 3.2 From prototype to production

| Area | What exists now | What is needed before enterprise rollout |
|---|---|---|
| **Environments** | `DairyCo_v2_Dev` and `DairyCo_v2_Prod` workspaces on one F2 capacity. | Dev / Test / Prod workspaces; Prod on its own capacity (F64 recommended: Copilot, no Pro licences for viewers, headroom). |
| **Source control** | Dev workspace connected to GitHub by Fabric Git integration (`fabric/` folder: notebooks, pipeline, TMDL model, PBIR report, lakehouse metadata, ML experiment and model). Ingestion config, generators and verification scripts sit alongside. | Branch policy on `main` (PR + review required), feature workspaces per developer via *Branch out*, Best Practice Analyzer on the model in PR checks. |
| **Deployment** | Merge to `main` → Update Dev → deployment pipeline `DairyCo v2 ALM` promotes Dev → Prod (notebook and pipeline references rebind to Prod items; the model reads Prod `lh_gold`). | Add a Test stage and deployment rules for the model's Direct Lake source. For a larger engineering team: GitHub Actions + `fabric-cicd` deploying `fabric/` on merge, with approvals before Prod. |
| **Parameterisation** | Notebooks reference lakehouses by *name* (workspace-relative), pipeline parameters (`load_date_filter`, `full_reload`), `batch_id` injected from the pipeline run. | Fabric Variable Library per stage (source paths, thresholds such as near-expiry 25%, benchmark scrap rate, target cover). |
| **Incremental & replay** | Watermark + MERGE for Sales; landing folders by load date; `full_reload` switch rebuilds from bronze. | Extend incremental to returns/inventory/sell-out; partition `fact_sales` by month; retention (VACUUM, 30-day time travel). |
| **Monitoring & failure handling** | Activity retries (2 × 120 s) and timeouts; bronze logs every file (SUCCEEDED/FAILED) and continues past a bad file; silver hard-stops on value-breaking DQ rules so gold is never refreshed with wrong numbers. | Pipeline failure alert via Fabric Activator / Teams; Capacity Metrics app monitoring; run log table surfaced in an ops report; on-call runbook. |
| **Data-quality monitoring** | 17 rules, `dq_issues` (current) and `dq_run_history` (trend), surfaced on the Operations page. | Thresholds and owners per rule (e.g. alert when duplicate customers > 0), DQ trend in the ops report, data-contract checks on source schema drift. |
| **Performance** | V-Order on gold, integer keys, star schema, hidden technical columns, `discourageImplicitMeasures`. | Monitor Direct Lake fallback/guardrails, Best Practice Analyzer in CI, DAX performance review of heavy measures (WAPE, avoidable scrap). |
| **Lineage & catalogue** | Fabric lineage view shows landing → bronze → silver → gold → model → report; every model object has a description. | Endorse (certify) the model; register in Purview / OneLake catalog; business glossary for KPI definitions. |
| **Operating ownership** | Owner per source recorded in the ingestion config (Finance/Commercial IT, Sales Ops, Channel Sales, Supply Chain, HR). | RACI: data owners fix source DQ issues; BI team owns model and measures; a KPI council signs off definitions (ends "different versions of the same KPI"). |

## 3.3 Data limitations that need a business decision (not a technical fix)

1. **Targets** are about 24× actual revenue, with a fixed implied price of 35 EGP. Finance needs to restate them. Until then attainment is shown only as a relative index.
2. **Stockout rate** cannot be measured. There are no orders, backorders or lost sales, and the stock status is always "Available". The report shows a proxy (share of zero-stock SKU-warehouse-weeks, 0.26%). The real KPI needs order lines with requested vs fulfilled quantity and daily or outlet-level stock.
3. **Cross-source scale.** Warehouse stock, payroll and CRM values are on different scales from invoice sales. This makes absolute ratios such as labour cost per unit, days of cover and CRM value vs revenue unreliable. Relative comparisons and trends still hold. Source owners need to confirm the units.
4. **Distributor feeds.** The stock roll-forward does not balance in 99% of rows, and reported sell-out matches outlet sell-out in only 2% of cells. The distributor data contract should require a roll-forward that reconciles.
5. **Growth periods.** With 20 months of history, only Jan–Aug year-on-year comparisons are like-for-like.
