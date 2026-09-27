# 6. Semantic model reference: DairyCo Analytics

Direct Lake on `lh_gold`. It is defined in `scripts/build_model.py` and versioned as TMDL in `fabric/DairyCo Analytics.SemanticModel/` through Fabric Git integration. It has 23 tables, 43 relationships (all single-direction, many-to-one, integer keys), 95 measures and 2 roles.

## 6.1 Tables and grain

| Table | Source (gold) | Description / grain |
|---|---|---|
| Date | `dim_date` | Calendar 2025-2026 (daily). Egyptian weekend = Friday/Saturday. 'Is Actuals Period' marks dates up to the last loaded invoice date and is used to keep year-on-year comparisons like-for-like. |
| Product | `dim_product` | ERP product master (24 SKUs). Standard Cost is the ERP master value; it is stale for Milk SKUs 1001-1005 from Jan 2026 (see Cost Variance vs Standard). |
| Region | `dim_region` | Conformed sales region (6 regions + Unknown). Row-level security is applied on this table; every regional fact relates to it directly. |
| Customer | `dim_customer` | Master customers after de-duplication (8 upper-case duplicate IDs merged into their proper-case master). Region is denormalised (no relationship to Region, to avoid ambiguous paths). |
| Distributor | `dim_distributor` | Third-party distributors (one per region). |
| Warehouse | `dim_warehouse` | DairyCo distribution centres (one per region). |
| Promotion | `dim_promotion` | Trade promotions from ERP plus a 'No promotion' member (key -1) for unpromoted invoice lines. |
| Production Unit | `dim_production_unit` | Plant x line x shift (18 units) - conformed between production orders and aggregated labour. |
| Sales | `fact_sales` | ERP invoice lines (grain: invoice line). Region comes from the customer master, customer is the de-duplicated master, promotion is attributed by product + region + invoice date. |
| Returns | `fact_returns` | Customer return lines (grain: return line). Dated by return date; returns can arrive after the sales period. |
| Sales Target | `fact_sales_target` | Monthly revenue and volume targets by region x category. WARNING: targets are ~24x actual revenue (implied price fixed at 35 EGP); use only relative/indexed attainment until Finance restates them. |
| Promotion Performance | `fact_promo_performance` | One row per promotion, dated by promotion start. Baseline = same product+region daily run-rate in the 8 weeks before the promotion (excluding other promotions). Incremental GP = promo-window GP minus baseline GP. |
| Inventory Snapshot | `fact_inventory_snapshot` | Weekly (Sunday) warehouse stock by batch. Semi-additive: stock measures take the latest snapshot in context. Near-expiry = 25% or less of shelf life remaining (business assumption). |
| Distributor Month | `fact_distributor_month` | Month x distributor x SKU: ERP sell-in, distributor-reported receipts, sell-out and closing stock. Distributor SKUs mapped to ERP products (UNKNOWN-#### recovered). |
| Demand Forecast | `fact_demand_forecast` | MRP monthly demand forecast by SKU (the incumbent forecast; the production plan copies it). |
| Production | `fact_production` | Production orders (grain: order = month x plant x line x shift x SKU). |
| Labour | `fact_labour_month` | Payroll and attendance AGGREGATED to month x plant x line x shift (minimum 5 employees per cell). No employee-level pay is in the model. Cost columns are hidden from the Regional Manager role (OLS). |
| CRM Opportunity | `fact_crm_opportunity` | Salesforce opportunities (grain: opportunity), dated by created month. CRM covers Modern Trade and Key Accounts only. |
| CRM Activity | `fact_crm_activity` | Salesforce activities (grain: activity). |
| ML Demand Forecast | `ml_demand_forecast` | Output of nb_05 (MLflow-tracked). record_type 'backtest' = rolling-origin out-of-sample months; 'forecast' = next month. |
| Stock Rebalancing | `ml_stock_rebalancing` | Warehouse x SKU recommendation from nb_05: target stock = ML forecast daily demand x (50% of shelf life); gap = on hand - target. |
| Data Quality | `dq_summary` | Latest result of every silver data-quality rule (flag, don't silently fix). |
| Security User Region | `security_user_region` | RLS mapping: user principal name -> permitted region. Maintained by the BI owner (production: synced from Entra ID groups). |

## 6.2 Relationships

All relationships are many-to-one and single-direction, from fact to dimension, on integer keys.

| Fact | Related dimensions |
|---|---|
| Sales | Date (via Date Key), Customer (via Customer Key), Product (via Product Key), Distributor (via Distributor Key), Region (via Region Key), Promotion (via Promotion Key) |
| Returns | Date (via Date Key), Customer (via Customer Key), Product (via Product Key), Region (via Region Key), Distributor (via Distributor Key) |
| Sales Target | Date (via Date Key), Region (via Region Key) |
| Promotion Performance | Promotion (via Promotion Key), Product (via Product Key), Region (via Region Key), Date (via Date Key) |
| Inventory Snapshot | Date (via Date Key), Warehouse (via Warehouse Key), Product (via Product Key), Region (via Region Key) |
| Distributor Month | Date (via Date Key), Distributor (via Distributor Key), Product (via Product Key), Region (via Region Key) |
| Demand Forecast | Date (via Date Key), Product (via Product Key) |
| Production | Date (via Date Key), Production Unit (via Production Unit Key), Product (via Product Key) |
| Labour | Date (via Date Key), Production Unit (via Production Unit Key) |
| CRM Opportunity | Date (via Date Key), Customer (via Customer Key), Region (via Region Key) |
| CRM Activity | Date (via Date Key), Customer (via Customer Key), Region (via Region Key) |
| ML Demand Forecast | Date (via Date Key), Product (via Product Key) |
| Stock Rebalancing | Warehouse (via Warehouse Key), Product (via Product Key), Region (via Region Key) |

## 6.3 Security roles

**Executive.** Executives and central functions: enterprise-wide view, no row filters.

**Regional Manager.** Regional managers: rows limited to regions mapped to their UPN in Security User Region. Manufacturing and aggregated workforce KPIs are company-wide and visible, but labour cost columns are hidden (OLS).
- RLS on *Region*: `'Region'[Region Key] IN CALCULATETABLE(VALUES('Security User Region'[Region Key]), 'Security User Region'[User UPN] = USERPRINCIPALNAME())`
- RLS on *Customer*: `'Customer'[Customer Region Key] IN CALCULATETABLE(VALUES('Security User Region'[Region Key]), 'Security User Region'[User UPN] = USERPRINCIPALNAME())`
- RLS on *Distributor*: `'Distributor'[Distributor Region Key] IN CALCULATETABLE(VALUES('Security User Region'[Region Key]), 'Security User Region'[User UPN] = USERPRINCIPALNAME())`
- RLS on *Warehouse*: `'Warehouse'[Warehouse Region Key] IN CALCULATETABLE(VALUES('Security User Region'[Region Key]), 'Security User Region'[User UPN] = USERPRINCIPALNAME())`
- RLS on *Security User Region*: `'Security User Region'[User UPN] = USERPRINCIPALNAME()`
- OLS on *Labour*: Overtime Cost Amount, Base Salary Amount, Allowances Amount, Total Labour Cost Amount = none

## 6.4 Measure catalogue

### Sales

| Measure | Definition | DAX |
|---|---|---|
| **Net Revenue** | Invoiced net sales (gross less on-invoice discount), before returns. Official revenue KPI; EGP. | `SUM('Sales'[Net Sales])` |
| **Gross Sales Amount** | Quantity x list price before discount; EGP. | `SUM('Sales'[Gross Sales])` |
| **Invoice Discount** | On-invoice discount; EGP. | `SUM('Sales'[Discount Amount])` |
| **Invoice Discount %** | On-invoice discount as a share of gross sales. | `DIVIDE([Invoice Discount], [Gross Sales Amount])` |
| **Sales Volume** | Units invoiced (packs, not litres/kg). | `SUM('Sales'[Quantity])` |
| **Average Selling Price** | Net revenue per unit; moves with mix because list prices never changed. | `DIVIDE([Net Revenue], [Sales Volume])` |
| **Active Customers** | Distinct master customers invoiced. | `DISTINCTCOUNT('Sales'[Customer Key])` |
| **Cost of Goods Sold** | Actual COGS booked on invoice lines; EGP. | `SUM('Sales'[COGS])` |
| **Gross Profit** | Net revenue less actual COGS; EGP. | `[Net Revenue] - [Cost of Goods Sold]` |
| **Gross Margin %** | Gross profit / net revenue. | `DIVIDE([Gross Profit], [Net Revenue])` |
| **Standard Cost of Goods Sold** | Quantity x ERP standard cost - what margin reporting based on master data assumes. | `SUM('Sales'[Standard COGS])` |
| **Cost Variance vs Standard** | Actual minus standard COGS. Positive = costs running above the ERP standard (Leak 1: stale Milk standard costs from Jan 2026). | `[Cost of Goods Sold] - [Standard Cost of Goods Sold]` |
| **Gross Margin % at Standard Cost** | The margin the business believes it makes if it prices off stale standard costs. | `DIVIDE([Net Revenue] - [Standard Cost of Goods Sold], [Net Revenue])` |
| **Net Revenue PY** | Net revenue for the same dates one year earlier, limited to dates that have actuals this year (like-for-like). | `VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), 'Date'[Is Actuals Period] = TRUE()) RETURN CALCULATE([Net Revenue], DATEADD(_dates, -1, YEAR))` |
| **Revenue Growth %** | Like-for-like year-on-year growth for the selected year (defaults to the latest year with actuals). Only 2026 Jan-Aug vs 2025 Jan-Aug is comparable (data starts Jan 2025). | `VAR _yr = IF(HASONEVALUE('Date'[Year]), VALUES('Date'[Year]), CALCULATE(MAX('Date'[Year]), 'Date'[Is Actuals Period] = TRUE(), REMOVEFILTERS('Date'))) VAR _cy = CALCULATE([Net Revenue], 'Date'[Is Actuals Period] = TRUE(), 'Date'[Year] = _yr) VAR _py = CALCULATE([Net Revenue PY], 'Date'[Year] = _yr) RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))` |
| **Gross Profit PY** | Gross profit, same dates last year (like-for-like). | `VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), 'Date'[Is Actuals Period] = TRUE()) RETURN CALCULATE([Gross Profit], DATEADD(_dates, -1, YEAR))` |
| **Gross Profit Growth %** | Like-for-like year-on-year gross profit growth. | `VAR _yr = IF(HASONEVALUE('Date'[Year]), VALUES('Date'[Year]), CALCULATE(MAX('Date'[Year]), 'Date'[Is Actuals Period] = TRUE(), REMOVEFILTERS('Date'))) VAR _cy = CALCULATE([Gross Profit], 'Date'[Is Actuals Period] = TRUE(), 'Date'[Year] = _yr) VAR _py = CALCULATE([Gross Profit PY], 'Date'[Year] = _yr) RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))` |
| **Gross Margin % PY** | Gross margin, same dates last year. | `DIVIDE([Gross Profit PY], [Net Revenue PY])` |
| **Gross Margin Change pp** | Change in gross margin vs the same period last year (percentage points); defaults to the latest year with actuals. | `VAR _yr = IF(HASONEVALUE('Date'[Year]), VALUES('Date'[Year]), CALCULATE(MAX('Date'[Year]), 'Date'[Is Actuals Period] = TRUE(), REMOVEFILTERS('Date'))) VAR _cy = CALCULATE([Gross Margin %], 'Date'[Is Actuals Period] = TRUE(), 'Date'[Year] = _yr) VAR _py = CALCULATE([Gross Margin % PY], 'Date'[Year] = _yr) RETURN IF(NOT ISBLANK(_py), _cy - _py)` |
| **Sales Volume PY** | Units, same dates last year (like-for-like). | `VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), 'Date'[Is Actuals Period] = TRUE()) RETURN CALCULATE([Sales Volume], DATEADD(_dates, -1, YEAR))` |
| **Sales Volume Growth %** | Like-for-like year-on-year unit growth. | `VAR _yr = IF(HASONEVALUE('Date'[Year]), VALUES('Date'[Year]), CALCULATE(MAX('Date'[Year]), 'Date'[Is Actuals Period] = TRUE(), REMOVEFILTERS('Date'))) VAR _cy = CALCULATE([Sales Volume], 'Date'[Is Actuals Period] = TRUE(), 'Date'[Year] = _yr) VAR _py = CALCULATE([Sales Volume PY], 'Date'[Year] = _yr) RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))` |
| **Net Revenue YTD** | Calendar year-to-date net revenue. | `TOTALYTD([Net Revenue], 'Date'[Date])` |
| **Promoted Revenue %** | Share of net revenue sold inside a promotion window. | `DIVIDE(CALCULATE([Net Revenue], 'Sales'[Promotion Key] <> -1), [Net Revenue])` |
| **Net Revenue after Returns** | Net revenue less the value of goods returned in the period (return-date basis). | `[Net Revenue] - [Return Value]` |

### Returns

| Measure | Definition | DAX |
|---|---|---|
| **Return Value** | Value of returned goods at invoice net price; EGP. | `SUM('Returns'[Return Value Amount])` |
| **Returned Units** | Units returned. | `SUM('Returns'[Returned Quantity])` |
| **Return Rate %** | Return value / net revenue, both by their own date (return date vs invoice date). | `DIVIDE([Return Value], [Net Revenue])` |

### Sales Target

| Measure | Definition | DAX |
|---|---|---|
| **Revenue Target** | Revenue target; category filter flows from Product[Category] via TREATAS. Source targets are on a different scale from actuals. | `CALCULATE(SUM('Sales Target'[Revenue Target Amount]), TREATAS(VALUES('Product'[Category]), 'Sales Target'[Target Category]))` |
| **Target Attainment %** | UNRELIABLE AS ABSOLUTE: ~4% because targets are ~24x actuals. Shown for completeness; use Target Attainment Index. | `DIVIDE([Net Revenue], [Revenue Target])` |
| **Target Attainment Index** | Attainment relative to the company average in the same period (1.00 = average). Scale-free, so usable while target scale is unresolved. | `VAR _att = [Target Attainment %] VAR _company = CALCULATE([Target Attainment %], REMOVEFILTERS('Region'), REMOVEFILTERS('Product'), REMOVEFILTERS('Customer'), REMOVEFILTERS('Distributor')) RETURN DIVIDE(_att, _company)` |

### Promotion Performance

| Measure | Definition | DAX |
|---|---|---|
| **Promotion Support Cost** | Trade support paid for the promotions in context; EGP. | `SUM('Promotion Performance'[Support Cost])` |
| **Incremental Gross Profit** | Gross profit above the pre-promotion baseline; EGP. | `SUM('Promotion Performance'[Incremental GP])` |
| **Net Promotion Return** | Incremental gross profit less support cost; negative = value destroyed. | `SUM('Promotion Performance'[Net Promo Return])` |
| **Promotion ROI %** | Net promotion return / support cost. | `DIVIDE([Net Promotion Return], [Promotion Support Cost])` |
| **Promotions Run** | Number of promotions. | `COUNTROWS('Promotion Performance')` |
| **Measurable Promotions** | Promotions with at least 28 baseline trading days in the 8 weeks before start. | `CALCULATE(COUNTROWS('Promotion Performance'), 'Promotion Performance'[Baseline Measurable] = TRUE()) + 0` |
| **Promotions Paying Back** | Promotions with a measurable baseline whose incremental GP exceeded support cost. | `CALCULATE(COUNTROWS('Promotion Performance'), 'Promotion Performance'[Net Promo Return] > 0, 'Promotion Performance'[Baseline Measurable] = TRUE()) + 0` |
| **Average Volume Lift %** | Mean unit uplift vs baseline across measurable promotions. | `CALCULATE(AVERAGE('Promotion Performance'[Volume Lift]), 'Promotion Performance'[Baseline Measurable] = TRUE())` |
| **Discount Applied on Invoice %** | Average discount actually on invoices during the promotion window (compare with stated discount). | `AVERAGE('Promotion Performance'[Discount Applied On Invoice])` |
| **Promotion Incremental Units** | Units above baseline. | `SUM('Promotion Performance'[Incremental Units])` |

### Inventory Snapshot

| Measure | Definition | DAX |
|---|---|---|
| **Inventory Units** | Units on hand at the latest snapshot in context (semi-additive). | `VAR _k = CALCULATE(MAX('Inventory Snapshot'[Date Key])) RETURN CALCULATE(SUM('Inventory Snapshot'[Qty On Hand]), 'Inventory Snapshot'[Date Key] = _k)` |
| **Inventory Value** | Stock on hand at standard cost, latest snapshot in context; EGP. | `VAR _k = CALCULATE(MAX('Inventory Snapshot'[Date Key])) RETURN CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Date Key] = _k)` |
| **Near-Expiry Stock Value** | Stock with 25% or less of shelf life left at the latest snapshot, at standard cost. | `VAR _k = CALCULATE(MAX('Inventory Snapshot'[Date Key])) RETURN CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Date Key] = _k, 'Inventory Snapshot'[Is Near Expiry] = TRUE())` |
| **Near-Expiry Stock %** | Share of stock value close to expiry. | `DIVIDE([Near-Expiry Stock Value], [Inventory Value])` |
| **Average Near-Expiry Stock Value** | Average near-expiry stock value per weekly snapshot across the period - the recurring exposure. | `AVERAGEX(VALUES('Inventory Snapshot'[Date Key]), CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Is Near Expiry] = TRUE()))` |
| **Days of Cover** | Latest stock / average daily units sold in the period. CAVEAT: warehouse stock and invoice volume look to be on different scales. | `VAR _units = [Inventory Units] VAR _days = CALCULATE(COUNTROWS('Date'), 'Date'[Is Actuals Period] = TRUE()) VAR _daily = DIVIDE(CALCULATE([Sales Volume], 'Date'[Is Actuals Period] = TRUE()), _days) RETURN DIVIDE(_units, _daily)` |
| **Stockout Proxy %** | PROXY, not a true stockout rate: share of warehouse x SKU x week snapshots with zero available stock. A real measure needs order lines (requested vs fulfilled) and daily/outlet stock. | `DIVIDE( CALCULATE(COUNTROWS('Inventory Snapshot'), 'Inventory Snapshot'[Is Zero Available] = TRUE()), COUNTROWS('Inventory Snapshot'))` |

### Distributor Month

| Measure | Definition | DAX |
|---|---|---|
| **Sell-in Units** | Units received by distributors (equals ERP sell-in). | `SUM('Distributor Month'[Receipts Qty])` |
| **Sell-out Units** | Units distributors report selling to outlets. | `SUM('Distributor Month'[Sellout Qty Reported])` |
| **Sell-out Value** | Outlet-level sell-out value at distributor prices. | `SUM('Distributor Month'[Sellout Value])` |
| **Sell-through %** | Sell-out / sell-in. Below ~85% (the peer norm) means stock is building in the channel. | `DIVIDE([Sell-out Units], [Sell-in Units])` |
| **Distributor Stock Units** | Distributor closing stock at the latest month in context (semi-additive). | `VAR _k = CALCULATE(MAX('Distributor Month'[Date Key])) RETURN CALCULATE(SUM('Distributor Month'[Closing Inventory Qty]), 'Distributor Month'[Date Key] = _k)` |
| **Distributor Months of Cover** | Closing stock / that month's sell-out. Peers run at ~0.6 months. | `VAR _k = CALCULATE(MAX('Distributor Month'[Date Key])) VAR _stock = [Distributor Stock Units] VAR _sellout = CALCULATE([Sell-out Units], 'Distributor Month'[Date Key] = _k) RETURN DIVIDE(_stock, _sellout)` |
| **Distributor Stock Value** | Closing distributor stock valued at DairyCo's sell-in price, latest month in context. | `VAR _k = CALCULATE(MAX('Distributor Month'[Date Key])) RETURN SUMX(FILTER('Distributor Month', 'Distributor Month'[Date Key] = _k), 'Distributor Month'[Closing Inventory Qty] * 'Distributor Month'[Sell In Unit Price])` |
| **Excess Channel Stock Value** | Distributor stock above 0.6 months of cover (peer norm), at sell-in price - revenue pulled forward that must still sell through. | `VAR _k = CALCULATE(MAX('Distributor Month'[Date Key])) VAR _benchmarkMonths = 0.6 RETURN SUMX(FILTER('Distributor Month', 'Distributor Month'[Date Key] = _k), MAX(0, 'Distributor Month'[Closing Inventory Qty] - _benchmarkMonths * 'Distributor Month'[Sellout Qty Reported]) * 'Distributor Month'[Sell In Unit Price])` |
| **Sell-in minus Sell-out Units** | Units shipped into the channel but not sold out in the period. | `[Sell-in Units] - [Sell-out Units]` |

### Demand Forecast

| Measure | Definition | DAX |
|---|---|---|
| **Forecast Units** | MRP forecast units. | `SUM('Demand Forecast'[Forecast Qty])` |
| **Forecast Bias %** | (Forecast - actual) / actual. Positive = over-forecast (ageing stock risk), negative = under-forecast (stockout risk). | `DIVIDE([Forecast Units] - [Sales Volume], [Sales Volume])` |
| **Forecast Error % (WAPE)** | Weighted absolute percentage error at SKU x month (sum of |forecast - actual| / actual). | `VAR _grid = CROSSJOIN(VALUES('Product'[Product Key]), VALUES('Date'[Year Month])) VAR _absErr = SUMX(_grid, ABS([Forecast Units] - [Sales Volume])) RETURN DIVIDE(_absErr, [Sales Volume])` |

### Production

| Measure | Definition | DAX |
|---|---|---|
| **Planned Units** | Planned production units. | `SUM('Production'[Planned Qty])` |
| **Actual Units** | Units produced (good + scrap). | `SUM('Production'[Actual Qty])` |
| **Good Units** | Units passing quality. | `SUM('Production'[Good Qty])` |
| **Scrap Units** | Units scrapped. | `SUM('Production'[Scrap Qty])` |
| **Production Plan Attainment %** | Actual / planned units - the figure Operations reports. | `DIVIDE([Actual Units], [Planned Units])` |
| **Good Output Attainment %** | Good / planned units - what customers can actually be served from. | `DIVIDE([Good Units], [Planned Units])` |
| **Scrap Rate %** | Scrap / actual units. | `DIVIDE([Scrap Units], [Actual Units])` |
| **Downtime Hours** | Unplanned downtime hours. | `DIVIDE(SUM('Production'[Downtime Minutes Amount]), 60)` |
| **Downtime Minutes per Order** | Average downtime per production order. | `DIVIDE(SUM('Production'[Downtime Minutes Amount]), COUNTROWS('Production'))` |
| **Scrap Cost** | Scrapped units at standard cost; EGP. | `SUM('Production'[Scrap Value Amount])` |
| **Benchmark Scrap Rate %** | Conservative internal benchmark: Plant 1 average scrap rate (all shifts) in the same period. Stretch benchmark = Plant 1 day shifts (~1.8%). | `CALCULATE([Scrap Rate %], REMOVEFILTERS('Production Unit'), 'Production Unit'[Plant] = "Plant 1")` |
| **Avoidable Scrap Cost** | Scrap above the Plant 1 average rate, at standard cost - cost removable by bringing Plant 2 and night shifts to Plant 1 practice (Leak 2). | `VAR _benchmark = [Benchmark Scrap Rate %] RETURN SUMX('Production', MAX(0, 'Production'[Scrap Qty] - 'Production'[Actual Qty] * _benchmark) * DIVIDE('Production'[Scrap Value Amount], 'Production'[Scrap Qty]))` |

### Labour

| Measure | Definition | DAX |
|---|---|---|
| **Labour Cost** | Base + overtime + allowances; EGP. Restricted (OLS). | `SUM('Labour'[Total Labour Cost Amount])` |
| **Overtime Cost** | Overtime pay; EGP. Restricted (OLS). | `SUM('Labour'[Overtime Cost Amount])` |
| **Overtime % of Labour Cost** | Overtime share of labour cost. | `DIVIDE([Overtime Cost], [Labour Cost])` |
| **Overtime Hours Total** | Overtime hours worked. | `SUM('Labour'[Overtime Hours])` |
| **Employee Months** | Sum of monthly headcount (employee-months). | `SUM('Labour'[Headcount])` |
| **Average Headcount** | Average monthly headcount. | `AVERAGEX(VALUES('Date'[Year Month]), CALCULATE(SUM('Labour'[Headcount])))` |
| **Overtime Hours per Employee** | Overtime hours per employee per month. | `DIVIDE([Overtime Hours Total], [Employee Months])` |
| **Absence Rate %** | Absence hours / scheduled hours. | `VAR _abs = SUM('Labour'[Absence Hours]) RETURN DIVIDE(_abs, SUM('Labour'[Attendance Hours]) + _abs)` |
| **Labour Cost per Good Unit** | Labour cost / good units produced. CAVEAT: payroll appears to be on a larger scale than production volume; use for relative comparison. | `DIVIDE([Labour Cost], [Good Units])` |

### CRM Opportunity

| Measure | Definition | DAX |
|---|---|---|
| **Open Pipeline Value** | Value of open opportunities. | `CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Open] = TRUE())` |
| **Stale Pipeline %** | Open pipeline already past its expected close date. | `DIVIDE(CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Stale] = TRUE()), [Open Pipeline Value])` |
| **Win Rate %** | Won / closed opportunities (count). | `DIVIDE(CALCULATE(COUNTROWS('CRM Opportunity'), 'CRM Opportunity'[Is Won] = TRUE()), CALCULATE(COUNTROWS('CRM Opportunity'), 'CRM Opportunity'[Is Open] = FALSE()))` |
| **Closed Won Value** | Value of won opportunities (CRM scale differs from ERP revenue). | `CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Won] = TRUE())` |

### CRM Activity

| Measure | Definition | DAX |
|---|---|---|
| **Activities** | Sales activities logged. | `COUNTROWS('CRM Activity')` |
| **Activity Hours** | Hours of logged sales activity. | `DIVIDE(SUM('CRM Activity'[Duration Minutes]), 60)` |

### ML Demand Forecast

| Measure | Definition | DAX |
|---|---|---|
| **ML Forecast Units** | Machine-learning forecast units. | `SUM('ML Demand Forecast'[ML Forecast Qty])` |
| **ML Backtest WAPE %** | Out-of-sample weighted absolute % error of the ML model. | `VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest") RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[ML Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))` |
| **MRP Backtest WAPE %** | Weighted absolute % error of the incumbent MRP forecast over the same backtest months. | `VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest") RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[MRP Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))` |
| **Rule Backtest WAPE %** | Error of the rule-based challenger (MRP x trailing 3-month actual/forecast ratio) over the same backtest months. | `VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest") RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[Rule Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))` |
| **Rule Forecast Units** | Bias-corrected MRP forecast units (rule). | `SUM('ML Demand Forecast'[Rule Forecast Qty])` |

### Stock Rebalancing

| Measure | Definition | DAX |
|---|---|---|
| **Excess Stock Value** | Stock above target cover, at standard cost. | `CALCULATE(SUM('Stock Rebalancing'[Stock Gap Value]), 'Stock Rebalancing'[Stock Gap] > 0)` |
| **Stock Shortfall Units** | Units below target cover (stockout risk). | `-CALCULATE(SUM('Stock Rebalancing'[Stock Gap]), 'Stock Rebalancing'[Stock Gap] < 0) + 0` |

### Data Quality

| Measure | Definition | DAX |
|---|---|---|
| **DQ Violations** | Rows violating data-quality rules at the last run. | `SUM('Data Quality'[Violations Count])` |
| **DQ Rules Breached** | Rules with at least one violation. | `CALCULATE(COUNTROWS('Data Quality'), 'Data Quality'[Violations Count] > 0)` |
