# 2. Exploratory data analysis and data quality

The EDA was run on the raw extracts before any modelling, using DuckDB locally. It was then re-run through the Fabric pipeline, so every data-quality finding below is also a live rule in `nb_02_silver_transform`, with its violation count on the Operations page.

## 2.1 Profile of the sources

| Source | Files | Grain | Range | Notes |
|---|---|---|---|---|
| ERP + WMS | 9 | invoice line (75,354), return line (1,659), weekly batch snapshot (12,503), month × region × category targets | Jan 2025 – Aug 2026 | Net = Gross − Discount on 100% of lines; COGS = Qty × Standard Cost everywhere **except** Milk SKUs 1001–1005 in 2026 (× 1.06). |
| Salesforce CRM | 3 | account (180), opportunity (780), activity (3,234) | Jan 2025 – Aug 2026 | Covers Modern Trade and Key Accounts only (23.7% of ERP revenue). |
| Distributor platform | 3 | month × distributor × SKU × outlet (11,605 JSONL), month × distributor × SKU (2,880 JSONL), 540 outlets | Jan 2025 – Aug 2026 | Receipts = ERP sell-in exactly; outlets cannot be linked to ERP customers. |
| Production + MRP | 4 | order = month × plant × line × shift × SKU (960) | Jan 2025 – Aug 2026 | Actual = Good + Scrap on 100%; downtime log reconciles 100%. |
| HR + Payroll | 3 | employee (342), employee × month (6,840 each) | Jan 2025 – Aug 2026 | Total labour cost = base + OT + allowances on 100%. |

All sources cover the same 20 months, so **year-on-year is only like-for-like for Jan–Aug** (2026 vs 2025).

## 2.2 Data-quality issues (all flagged in `dq_issues`, none silently fixed)

| Rule | Issue | Rows | Treatment | Business impact |
|---|---|---|---|---|
| CUS-01 / SAL-02 | 8 duplicate customers (upper-case copies, IDs 20721–20728) | 8 customers, 819 invoice lines (≈201k EGP) | Mapped to the proper-case master; both IDs kept | Customer count 728 → 720; per-customer KPIs were split. |
| SAL-01 | Non-standard region labels on invoices ("CAIRO", "Alex.", "UpperEgypt") | 185 lines (46.8k EGP) | Region taken from the customer master; raw label retained | Regional revenue and target attainment were understated. |
| SAL-04 | COGS ≠ Qty × Standard Cost | 14,544 lines (Milk 1001–1005, 2026) | Kept actual COGS; `Standard COGS` stored alongside | **Leak 1**: standard costs are stale. |
| CRM-01 / CRM-02 | CRM CustomerID stored as float text ("20290.0"); 10 blank | 170 / 10 accounts | Cast to integer; blanks matched by exact name (10/10) | CRM ↔ ERP join now 100% (was 94%). |
| CRM-03 | Open opportunities past expected close date | 345 | Flagged `is_stale` | 91.9M "open pipeline" is mostly stale. |
| DST-01 | Distributor SKU "UNKNOWN-1013/1018/1023" | 1,308 sell-out rows | ERP product recovered from the numeric suffix; flagged | Without the fix, 3 SKUs vanish from sell-out. |
| DST-02 | Distributor stock roll-forward does not balance | 2,718 of 2,736 | Flagged; reported closing stock used | Channel stock figures are indicative only. |
| DST-03 | Distributor-reported sell-out ≠ sum of outlet sell-out | 2,820 of 2,880 cells | Reported figure used for cover, outlet figure for value | Two versions of the same KPI; needs a data contract. |
| INV-01 | Available ≠ On-hand − Reserved (off by 1) | 12,048 of 12,503 | Recomputed `Qty Available`; reported value kept | Minor, but a sign of a WMS calculation bug. |
| INV-02 | Negative on-hand | 8 | Floored at 0 for valuation; flagged | Integrity issue. |
| INV-03 | Stock ≤ 3 days from expiry still status "Available" | 1,345 | Status ignored; near-expiry derived from dates | The status field cannot be used for stock-risk decisions. |
| RET-01 / RET-02 | Returns dated after the last sale / before the invoice was loaded | 22 / late-arriving | Warning, not blocking | Return rate depends on the dating convention (return date used). |
| HR-01 | Payroll paid before the employee's hire date | 112 employee-months (28 people) | Flagged | Payroll control issue for HR/Finance. |
| CUS-02 | Territory prefix "T-CA" used for Cairo and Canal | 1 prefix | Flagged | Territory codes are not unique. |
| — | Production order 600001 missing | 1 | Noted | Sequence gap. |
| — | Targets ≈ 24× actual revenue; fixed implied price 35 EGP | all 480 rows | Relative index only | Absolute target attainment (~4%) is meaningless. |

## 2.3 Patterns, trends and anomalies

* **Trend and seasonality.** Revenue peaks March–May and bottoms in September. There is no calendar gap: all 608 days have sales, with about 12% fewer lines on Fridays.
* **Step change in January 2026.** Monthly gross margin is 28.3–28.5% in every month of 2025 and 24.7–25.1% in every month of 2026. This is a structural break, not noise.
* **Mix change.** Milk SKUs 1001–1005 grew 123–166% YoY while every other SKU (including Milk 1006) fell 18–27%. List prices never changed; average selling price fell about 3% from mix alone.
* **Distributor 301.** From January 2026 its sell-out falls about 30% while its receipts rise, and its closing stock roughly triples. The other five distributors stay at about 0.6 months of cover.
* **Promotion 9999.** It is the only "Deep Discount" (25%, SKU 1022, Cairo, Apr–May 2026, 120k support cost against 15–45k for others) and the only promotion whose discount appears on invoices. It had zero volume lift.
* **Plant 2 / Shift C.** Scrap is 6.3% at Plant 2 vs 2.7% at Plant 1, and Shift C reaches 7.1% (8.8–9.3% at Plant 2). Overtime and absence follow the same cells (correlation 0.89 across cells) but are flat over time.
* **Forecast.** The production plan equals the forecast minus about one unit. The forecast is biased by category (Milk −8%, Yogurt +19%).
* **Cross-source scale.** Targets (24×), payroll (about 4.5M/month vs about 1M revenue), CRM won value (12×) and warehouse stock (80–130 days of cover for 14-day milk) are not on the same scale as invoice sales. **Assumption:** invoice data is the reliable commercial record, other sources are used for relative comparison, and every affected measure says so in its description.

## 2.4 Material assumptions

1. **Revenue** is ERP net sales (after on-invoice discount, before returns). Returns are reported separately and dated by return date.
2. **Region** is the customer-master region, not the free-text invoice label.
3. **Near-expiry** means 25% or less of shelf life remaining.
4. **Promotion baseline** is the same product and region in the 8 weeks before the promotion, excluding days in other promotions. A promotion is "measurable" when its baseline has at least 28 trading days.
5. **Benchmark scrap** is the Plant 1 shifts A/B rate in the same period (internal best practice).
6. **Normal distributor cover** is 0.6 months (the peer level observed at distributors 302–306).
