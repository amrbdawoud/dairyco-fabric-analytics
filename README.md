# DairyCo Analytics on Microsoft Fabric

An end-to-end Microsoft Fabric implementation for the DairyCo BI Consultant case: medallion lakehouse, data-quality framework, a Direct Lake semantic model with row- and object-level security, a 3-page management report, and an MLflow-tracked demand-forecasting prototype.

> **Headline.** Jan–Aug 2026 vs 2025: net revenue **+7.6%** but gross profit **−5.4%**. Gross margin stepped down from 28.4% to 25.0% in January 2026. The cause is Milk's mix growth plus a Milk cost rise that the ERP standard cost does not reflect. Five profit leaks sit underneath; see `docs/`.

## Repository layout

| Path | Contents |
|---|---|
| `config/ingestion_config.json` | The metadata that drives ingestion: 22 entities with source, format, bronze table, load type, business key, sensitivity and owner |
| `notebooks/` | Fabric notebook sources (`# %%` cells): `nb_01_bronze_ingest`, `nb_02_silver_transform`, `nb_03_gold_star_schema`, `nb_05_ml_demand_forecast` |
| `pipelines/pl_dairyco_daily.json` | Orchestration pipeline definition (bronze → silver → gold → ML) |
| `semantic-model/DairyCo Analytics.SemanticModel/` | The semantic model as TMDL: tables, relationships, ~100 measures, RLS/OLS roles |
| `report/DairyCo Management.Report/` | 3-page report definition (PBIP; opens in Power BI Desktop together with the model folder) |
| `scripts/` | Deploy tooling: `fabric.py` (deploy/run notebooks and pipelines, fetch logs), `upload_landing.py`, `deploy_pipeline.py`, `build_model.py` (TMDL generator and deploy), `build_report.py`, `findings.py` (recomputes every figure from gold), `olq.py` (read gold Delta tables locally) |
| `docs/` | Architecture and decisions, EDA and DQ, security and production readiness, AI, explainer briefs and Q&A, `findings_numbers.json` |
| `fabric/` | Workspace items as serialised by Fabric Git integration |

## Reproduce

```bash
az login                                   # identity with Contributor on the workspace
python scripts/upload_landing.py <data_dir> <workspace_id> <lh_bronze_id> initial
python scripts/fabric.py deploy <ws> notebooks/nb_01_bronze_ingest.py lh_bronze     # repeat per notebook/lakehouse
python scripts/deploy_pipeline.py <ws>
python scripts/fabric.py pipeline <ws> pl_dairyco_daily
python scripts/build_model.py deploy <ws>
python scripts/build_report.py deploy <ws>
python scripts/findings.py                 # recompute the figures used in the deck
```

The raw candidate-pack data is not included in this repository.

## Workspace

- **Workspaces:** `DairyCo_v2_Dev` (development, Git-connected) and `DairyCo_v2_Prod`, on an F2 capacity.
- **Lakehouses:** `lh_bronze`, `lh_silver` and `lh_gold`.
- **Pipeline:** `pl_dairyco_daily`.
- **Semantic model:** `DairyCo Analytics` (Direct Lake).
- **Report:** `DairyCo Management`.
- **ML:** MLflow experiment `dairyco-demand-forecast` and model `dairyco-demand-forecast-hgb`.
