# DairyCo Analytics on Microsoft Fabric

An end-to-end Microsoft Fabric implementation for the DairyCo BI Consultant case: medallion lakehouse, data-quality framework, a Direct Lake semantic model with row- and object-level security, a 3-page management report, and an MLflow-tracked demand-forecasting prototype.

> **Headline.** Jan–Aug 2026 vs 2025: net revenue **+7.6%** but gross profit **−5.4%**. Gross margin stepped down from 28.4% to 25.0% in January 2026. The cause is Milk's mix growth plus a Milk cost rise that the ERP standard cost does not reflect. Five profit leaks sit underneath; see `docs/`.

## Repository layout

| Path | Contents |
|---|---|
| `*.Notebook/`, `*.DataPipeline/`, `*.SemanticModel/`, `*.Report/`, `*.Lakehouse/`, `*.MLExperiment/`, `*.MLModel/` (repo root) | The `DairyCo_v2_Dev` workspace as serialised by Fabric Git integration: notebooks (`nb_01_bronze_ingest`, `nb_02_silver_transform`, `nb_03_gold_star_schema`, `nb_05_ml_demand_forecast`), the `pl_dairyco_daily` pipeline, the `DairyCo Analytics` semantic model (TMDL: 95 measures, RLS/OLS roles), the `DairyCo Management` report (PBIR), lakehouse metadata, and the MLflow experiment and registered model. These folders are the source of truth for every workspace item. |
| `config/` | `ingestion_config.json`, the metadata that drives ingestion (22 entities with source, format, bronze table, load type, business key, sensitivity and owner), uploaded to `lh_bronze/Files/config/`. `gold_schema.json`, the gold table schemas used by the model generator. |
| `scripts/` | `build_model.py` (regenerates the semantic model's tables, measures, relationships and roles inside `DairyCo Analytics.SemanticModel/`), `upload_landing.py` (drops source extracts into the bronze landing zone), `fabric.py` (run notebooks and pipelines, fetch Spark logs), `dax.py` (run DAX against the deployed model), `findings.py` + `olq.py` (recompute every figure independently from the gold Delta tables), `export_report.py`, `build_appendix.py`, `build_deck.js` |
| `docs/` | Architecture and decisions, EDA and DQ, security and production readiness, AI, explainer briefs and Q&A, `findings_numbers.json` |

## Development workflow

Only the Dev workspace is connected to Git. Prod is never edited by hand.

1. **Branch out.** In the Dev workspace's Source control panel, *Branch out to new workspace* creates a feature branch and a personal feature workspace.
2. **Change and commit.** Edit items in the feature workspace (or edit the item folders locally) and commit to the feature branch.
3. **Pull request.** Open a PR into `main` for review. Semantic-model changes are reviewed as TMDL diffs.
4. **Update Dev.** After merge, *Update* in the Dev workspace's Source control panel brings it in line with `main`.
5. **Promote.** The Fabric deployment pipeline `DairyCo v2 ALM` promotes Dev → Prod. Notebook and pipeline references rebind to the Prod items; the semantic model's Direct Lake source points at Prod `lh_gold`.

To change the semantic model in bulk, run `python scripts/build_model.py` on the feature branch. It rewrites only the TMDL it owns and keeps Fabric's own files and the Direct Lake binding.

## Data and verification

```bash
az login                                                                        # identity with Contributor on the workspace
python scripts/upload_landing.py <data_dir> <workspace_id> <lh_bronze_id> initial   # then: incremental (August drop)
python scripts/fabric.py pipeline <workspace> pl_dairyco_daily
python scripts/findings.py                                                      # recompute the figures used in the deck
```

The raw candidate-pack data is not included in this repository. Lakehouse data is not in Git; only lakehouse metadata is.

## Workspace

- **Workspaces:** `DairyCo_v2_Dev` (development, connected to this repo; Git folder = repo root) and `DairyCo_v2_Prod` (promoted by deployment pipeline `DairyCo v2 ALM`), on an F2 capacity.
- **Lakehouses:** `lh_bronze`, `lh_silver` and `lh_gold`.
- **Pipeline:** `pl_dairyco_daily`.
- **Semantic model:** `DairyCo Analytics` (Direct Lake).
- **Report:** `DairyCo Management`.
- **ML:** MLflow experiment `dairyco-demand-forecast` and model `dairyco-demand-forecast-hgb`.
