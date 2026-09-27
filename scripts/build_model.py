"""Regenerate the DairyCo Direct Lake semantic model's TMDL inside the Git-synced workspace folder.

    python build_model.py        # rewrite DairyCo Analytics.SemanticModel/definition/ (repo root)

The model is defined here as data (tables, columns, measures, relationships, roles) so every object carries
a description and naming stays consistent. The output lands in the item folder that the Dev workspace syncs through
Fabric Git integration (the repo root): commit it, open a pull request, and after merge click Update in the Dev workspace.

Only the files this script owns are rewritten (model, relationships, tables, roles). Fabric's own files
(.platform, definition.pbism, cultures, diagram layout) and the stage-specific Direct Lake binding in
expressions.tmdl are left as Fabric wrote them. Run it only after the workspace has been synced to Git.
"""
import json, pathlib, shutil, sys, textwrap

MODEL_NAME = "DairyCo Analytics"
REPO = pathlib.Path(__file__).resolve().parents[1]
ROOT = REPO / f"{MODEL_NAME}.SemanticModel"
SCHEMA = REPO / "config" / "gold_schema.json"
TYPE = {"integer": "int64", "long": "int64", "string": "string", "boolean": "boolean", "date": "dateTime",
        "timestamp": "dateTime", "decimal": "decimal", "double": "double"}
FMT = {"egp": "#,##0", "egp2": "#,##0.00", "int": "#,##0", "pct": "0.0%", "pct2": "0.00%", "dec1": "#,##0.0",
       "dec2": "#,##0.00", "idx": "0.00"}

# ---------------------------------------------------------------------------------------------------------------
# Column spec: (source_column, display_name, type, flags)  flags: h=hidden, s=summarize none, k=key
# ---------------------------------------------------------------------------------------------------------------
C = lambda src, name, typ, flags="", **kw: dict(src=src, name=name, type=typ, flags=flags, **kw)

TABLES = []
def table(name, entity, desc, cols, measures=(), **kw):
    TABLES.append(dict(name=name, entity=entity, desc=desc, cols=cols, measures=list(measures), **kw))
def M(name, expr, fmt, desc, folder):
    return dict(name=name, expr=textwrap.dedent(expr).strip(), fmt=FMT[fmt], desc=desc, folder=folder)

# ---------------------------------------------------------------- dimensions
table("Date", "dim_date", "Calendar 2025-2026 (daily). Egyptian weekend = Friday/Saturday. 'Is Actuals Period' marks dates up to the last loaded invoice date and is used to keep year-on-year comparisons like-for-like.", [
    C("date_key", "Date Key", "integer", "hs"), C("date", "Date", "date", "k", fmt="yyyy-mm-dd"),
    C("year", "Year", "integer", "s"), C("quarter", "Quarter", "integer", "s"), C("month_num", "Month Number", "integer", "hs"),
    C("month_name", "Month", "string", sort="Month Number"), C("year_month", "Year Month", "string"),
    C("month_start", "Month Start", "date", fmt="mmm yyyy"), C("week_start", "Week Start", "date", fmt="yyyy-mm-dd"),
    C("day_name", "Day Name", "string", sort="Day Of Week"), C("day_of_week", "Day Of Week", "integer", "hs"),
    C("is_weekend", "Is Weekend", "boolean"), C("is_actuals_period", "Is Actuals Period", "boolean")],
    date_table=True, hierarchies=[("Calendar", ["Year", "Quarter", "Month", "Date"])])
table("Product", "dim_product", "ERP product master (24 SKUs). Standard Cost is the ERP master value; it is stale for Milk SKUs 1001-1005 from Jan 2026 (see Cost Variance vs Standard).", [
    C("product_key", "Product Key", "integer", "hs"), C("sku", "SKU", "string"), C("product_name", "Product", "string"),
    C("brand", "Brand", "string"), C("category", "Category", "string"), C("pack_size", "Pack Size", "string"),
    C("list_price", "List Price", "decimal", "s", fmt="#,##0.00"), C("standard_cost", "Standard Cost", "decimal", "s", fmt="#,##0.00"),
    C("shelf_life_days", "Shelf Life Days", "integer", "s")],
    hierarchies=[("Product Hierarchy", ["Category", "Brand", "Product"])])
table("Region", "dim_region", "Conformed sales region (6 regions + Unknown). Row-level security is applied on this table; every regional fact relates to it directly.", [
    C("region_key", "Region Key", "integer", "hs"), C("region", "Region", "string", dataCategory="StateOrProvince")])
table("Customer", "dim_customer", "Master customers after de-duplication (8 upper-case duplicate IDs merged into their proper-case master). Region is denormalised (no relationship to Region, to avoid ambiguous paths).", [
    C("customer_key", "Customer Key", "integer", "hs"), C("customer_name", "Customer", "string"), C("channel", "Channel", "string"),
    C("region_key", "Customer Region Key", "integer", "hs"), C("region", "Customer Region", "string"),
    C("sales_territory", "Sales Territory", "string"), C("is_strategic", "Is Strategic Account", "boolean"),
    C("in_crm", "In CRM", "boolean")])
table("Distributor", "dim_distributor", "Third-party distributors (one per region).", [
    C("distributor_key", "Distributor Key", "integer", "hs"), C("distributor_name", "Distributor", "string"),
    C("region_key", "Distributor Region Key", "integer", "hs"), C("region", "Distributor Region", "string")])
table("Warehouse", "dim_warehouse", "DairyCo distribution centres (one per region).", [
    C("warehouse_key", "Warehouse Key", "integer", "hs"), C("warehouse_name", "Warehouse", "string"),
    C("region_key", "Warehouse Region Key", "integer", "hs"), C("region", "Warehouse Region", "string")])
table("Promotion", "dim_promotion", "Trade promotions from ERP plus a 'No promotion' member (key -1) for unpromoted invoice lines.", [
    C("promotion_key", "Promotion Key", "integer", "hs"), C("promotion_code", "Promotion", "string"),
    C("promotion_type", "Promotion Type", "string"), C("product_key", "Promotion Product Key", "integer", "hs"),
    C("region_key", "Promotion Region Key", "integer", "hs"), C("start_date", "Promotion Start", "date", fmt="yyyy-mm-dd"),
    C("end_date", "Promotion End", "date", fmt="yyyy-mm-dd"), C("discount_pct", "Stated Discount %", "decimal", "s", fmt="0.0%"),
    C("support_cost", "Stated Support Cost", "decimal", "s", fmt="#,##0")])
table("Production Unit", "dim_production_unit", "Plant x line x shift (18 units) - conformed between production orders and aggregated labour.", [
    C("production_unit_key", "Production Unit Key", "integer", "hs"), C("plant", "Plant", "string"), C("line", "Line", "string"),
    C("shift", "Shift", "string"), C("plant_id", "Plant Id", "integer", "hs"), C("line_id", "Line Id", "integer", "hs"),
    C("production_unit", "Production Unit", "string")],
    hierarchies=[("Plant Hierarchy", ["Plant", "Line", "Shift"])])

# ---------------------------------------------------------------- commercial facts
AP = "'Date'[Is Actuals Period] = TRUE()"
YR = """VAR _yr = IF(HASONEVALUE('Date'[Year]), VALUES('Date'[Year]),
            CALCULATE(MAX('Date'[Year]), 'Date'[Is Actuals Period] = TRUE(), REMOVEFILTERS('Date')))"""
table("Sales", "fact_sales", "ERP invoice lines (grain: invoice line). Region comes from the customer master, customer is the de-duplicated master, promotion is attributed by product + region + invoice date.", [
    C("invoice_id", "Invoice Id", "long", "hs"), C("date_key", "Date Key", "integer", "hs"), C("customer_key", "Customer Key", "integer", "hs"),
    C("product_key", "Product Key", "integer", "hs"), C("distributor_key", "Distributor Key", "integer", "hs"),
    C("region_key", "Region Key", "integer", "hs"), C("promotion_key", "Promotion Key", "integer", "hs"),
    C("quantity", "Quantity", "integer", "h"), C("gross_sales", "Gross Sales", "decimal", "h"), C("discount_amount", "Discount Amount", "decimal", "h"),
    C("net_sales", "Net Sales", "decimal", "h"), C("cogs", "COGS", "decimal", "h"), C("standard_cogs", "Standard COGS", "decimal", "h"),
    C("dq_duplicate_customer", "DQ Duplicate Customer", "boolean"), C("dq_region_relabelled", "DQ Region Relabelled", "boolean")], [
    M("Net Revenue", "SUM('Sales'[Net Sales])", "egp", "Invoiced net sales (gross less on-invoice discount), before returns. Official revenue KPI; EGP.", "Revenue"),
    M("Gross Sales Amount", "SUM('Sales'[Gross Sales])", "egp", "Quantity x list price before discount; EGP.", "Revenue"),
    M("Invoice Discount", "SUM('Sales'[Discount Amount])", "egp", "On-invoice discount; EGP.", "Revenue"),
    M("Invoice Discount %", "DIVIDE([Invoice Discount], [Gross Sales Amount])", "pct", "On-invoice discount as a share of gross sales.", "Revenue"),
    M("Sales Volume", "SUM('Sales'[Quantity])", "int", "Units invoiced (packs, not litres/kg).", "Volume"),
    M("Average Selling Price", "DIVIDE([Net Revenue], [Sales Volume])", "dec2", "Net revenue per unit; moves with mix because list prices never changed.", "Revenue"),
    M("Active Customers", "DISTINCTCOUNT('Sales'[Customer Key])", "int", "Distinct master customers invoiced.", "Volume"),
    M("Cost of Goods Sold", "SUM('Sales'[COGS])", "egp", "Actual COGS booked on invoice lines; EGP.", "Profitability"),
    M("Gross Profit", "[Net Revenue] - [Cost of Goods Sold]", "egp", "Net revenue less actual COGS; EGP.", "Profitability"),
    M("Gross Margin %", "DIVIDE([Gross Profit], [Net Revenue])", "pct", "Gross profit / net revenue.", "Profitability"),
    M("Standard Cost of Goods Sold", "SUM('Sales'[Standard COGS])", "egp", "Quantity x ERP standard cost - what margin reporting based on master data assumes.", "Profitability"),
    M("Cost Variance vs Standard", "[Cost of Goods Sold] - [Standard Cost of Goods Sold]", "egp", "Actual minus standard COGS. Positive = costs running above the ERP standard (Leak 1: stale Milk standard costs from Jan 2026).", "Profitability"),
    M("Gross Margin % at Standard Cost", "DIVIDE([Net Revenue] - [Standard Cost of Goods Sold], [Net Revenue])", "pct", "The margin the business believes it makes if it prices off stale standard costs.", "Profitability"),
    M("Net Revenue PY", f"""
        VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), {AP})
        RETURN CALCULATE([Net Revenue], DATEADD(_dates, -1, YEAR))""", "egp",
      "Net revenue for the same dates one year earlier, limited to dates that have actuals this year (like-for-like).", "Time Intelligence"),
    M("Revenue Growth %", f"""
        {YR}
        VAR _cy = CALCULATE([Net Revenue], {AP}, 'Date'[Year] = _yr)
        VAR _py = CALCULATE([Net Revenue PY], 'Date'[Year] = _yr)
        RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))""", "pct",
      "Like-for-like year-on-year growth for the selected year (defaults to the latest year with actuals). Only 2026 Jan-Aug vs 2025 Jan-Aug is comparable (data starts Jan 2025).", "Time Intelligence"),
    M("Gross Profit PY", f"""
        VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), {AP})
        RETURN CALCULATE([Gross Profit], DATEADD(_dates, -1, YEAR))""", "egp", "Gross profit, same dates last year (like-for-like).", "Time Intelligence"),
    M("Gross Profit Growth %", f"""
        {YR}
        VAR _cy = CALCULATE([Gross Profit], {AP}, 'Date'[Year] = _yr)
        VAR _py = CALCULATE([Gross Profit PY], 'Date'[Year] = _yr)
        RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))""", "pct", "Like-for-like year-on-year gross profit growth.", "Time Intelligence"),
    M("Gross Margin % PY", "DIVIDE([Gross Profit PY], [Net Revenue PY])", "pct", "Gross margin, same dates last year.", "Time Intelligence"),
    M("Gross Margin Change pp", f"""
        {YR}
        VAR _cy = CALCULATE([Gross Margin %], {AP}, 'Date'[Year] = _yr)
        VAR _py = CALCULATE([Gross Margin % PY], 'Date'[Year] = _yr)
        RETURN IF(NOT ISBLANK(_py), _cy - _py)""", "pct", "Change in gross margin vs the same period last year (percentage points); defaults to the latest year with actuals.", "Time Intelligence"),
    M("Sales Volume PY", f"""
        VAR _dates = CALCULATETABLE(VALUES('Date'[Date]), {AP})
        RETURN CALCULATE([Sales Volume], DATEADD(_dates, -1, YEAR))""", "int", "Units, same dates last year (like-for-like).", "Time Intelligence"),
    M("Sales Volume Growth %", f"""
        {YR}
        VAR _cy = CALCULATE([Sales Volume], {AP}, 'Date'[Year] = _yr)
        VAR _py = CALCULATE([Sales Volume PY], 'Date'[Year] = _yr)
        RETURN IF(NOT ISBLANK(_py), DIVIDE(_cy - _py, _py))""", "pct", "Like-for-like year-on-year unit growth.", "Time Intelligence"),
    M("Net Revenue YTD", "TOTALYTD([Net Revenue], 'Date'[Date])", "egp", "Calendar year-to-date net revenue.", "Time Intelligence"),
    M("Promoted Revenue %", "DIVIDE(CALCULATE([Net Revenue], 'Sales'[Promotion Key] <> -1), [Net Revenue])", "pct", "Share of net revenue sold inside a promotion window.", "Promotions"),
    M("Net Revenue after Returns", "[Net Revenue] - [Return Value]", "egp", "Net revenue less the value of goods returned in the period (return-date basis).", "Revenue"),
])
table("Returns", "fact_returns", "Customer return lines (grain: return line). Dated by return date; returns can arrive after the sales period.", [
    C("return_id", "Return Id", "long", "hs"), C("invoice_id", "Invoice Id", "long", "hs"), C("date_key", "Date Key", "integer", "hs"),
    C("invoice_date_key", "Invoice Date Key", "integer", "hs"), C("customer_key", "Customer Key", "integer", "hs"),
    C("product_key", "Product Key", "integer", "hs"), C("region_key", "Region Key", "integer", "hs"),
    C("distributor_key", "Distributor Key", "integer", "hs"), C("returned_quantity", "Returned Quantity", "integer", "h"), C("return_value", "Return Value Amount", "decimal", "h"),
    C("return_reason", "Return Reason", "string")], [
    M("Return Value", "SUM('Returns'[Return Value Amount])", "egp", "Value of returned goods at invoice net price; EGP.", "Returns"),
    M("Returned Units", "SUM('Returns'[Returned Quantity])", "int", "Units returned.", "Returns"),
    M("Return Rate %", "DIVIDE([Return Value], [Net Revenue])", "pct2", "Return value / net revenue, both by their own date (return date vs invoice date).", "Returns"),
])
table("Sales Target", "fact_sales_target", "Monthly revenue and volume targets by region x category. WARNING: targets are ~24x actual revenue (implied price fixed at 35 EGP); use only relative/indexed attainment until Finance restates them.", [
    C("date_key", "Date Key", "integer", "hs"), C("region_key", "Region Key", "integer", "hs"), C("category", "Target Category", "string", "h"),
    C("revenue_target", "Revenue Target Amount", "decimal", "h"), C("volume_target", "Volume Target Units", "double", "h")], [
    M("Revenue Target", "CALCULATE(SUM('Sales Target'[Revenue Target Amount]), TREATAS(VALUES('Product'[Category]), 'Sales Target'[Target Category]))", "egp",
      "Revenue target; category filter flows from Product[Category] via TREATAS. Source targets are on a different scale from actuals.", "Targets"),
    M("Target Attainment %", "DIVIDE([Net Revenue], [Revenue Target])", "pct", "UNRELIABLE AS ABSOLUTE: ~4% because targets are ~24x actuals. Shown for completeness; use Target Attainment Index.", "Targets"),
    M("Target Attainment Index", """
        VAR _att = [Target Attainment %]
        VAR _company = CALCULATE([Target Attainment %], REMOVEFILTERS('Region'), REMOVEFILTERS('Product'), REMOVEFILTERS('Customer'), REMOVEFILTERS('Distributor'))
        RETURN DIVIDE(_att, _company)""", "idx",
      "Attainment relative to the company average in the same period (1.00 = average). Scale-free, so usable while target scale is unresolved.", "Targets"),
])
table("Promotion Performance", "fact_promo_performance", "One row per promotion, dated by promotion start. Baseline = same product+region daily run-rate in the 8 weeks before the promotion (excluding other promotions). Incremental GP = promo-window GP minus baseline GP.", [
    C("promotion_key", "Promotion Key", "integer", "hs"), C("date_key", "Date Key", "integer", "hs"),
    C("product_key", "Product Key", "integer", "hs"), C("region_key", "Region Key", "integer", "hs"),
    C("promotion_type", "Performance Promotion Type", "string", "h"), C("promo_days", "Promo Days", "integer", "s"),
    C("discount_pct", "Discount Stated", "decimal", "h"), C("discount_applied_on_invoice", "Discount Applied On Invoice", "double", "h"),
    C("support_cost", "Support Cost", "decimal", "h"), C("promo_units", "Promo Units", "long", "h"), C("baseline_units", "Baseline Units", "double", "h"),
    C("incremental_units", "Incremental Units", "double", "h"), C("volume_lift_pct", "Volume Lift", "double", "h"),
    C("promo_net_sales", "Promo Net Sales", "decimal", "h"), C("promo_gp", "Promo GP", "decimal", "h"), C("baseline_gp", "Baseline GP", "double", "h"),
    C("incremental_gp", "Incremental GP", "double", "h"), C("net_promo_return", "Net Promo Return", "double", "h"),
    C("promo_roi", "Promo ROI", "double", "h"), C("baseline_measurable", "Baseline Measurable", "boolean")], [
    M("Promotion Support Cost", "SUM('Promotion Performance'[Support Cost])", "egp", "Trade support paid for the promotions in context; EGP.", "Promotions"),
    M("Incremental Gross Profit", "SUM('Promotion Performance'[Incremental GP])", "egp", "Gross profit above the pre-promotion baseline; EGP.", "Promotions"),
    M("Net Promotion Return", "SUM('Promotion Performance'[Net Promo Return])", "egp", "Incremental gross profit less support cost; negative = value destroyed.", "Promotions"),
    M("Promotion ROI %", "DIVIDE([Net Promotion Return], [Promotion Support Cost])", "pct", "Net promotion return / support cost.", "Promotions"),
    M("Promotions Run", "COUNTROWS('Promotion Performance')", "int", "Number of promotions.", "Promotions"),
    M("Measurable Promotions", "CALCULATE(COUNTROWS('Promotion Performance'), 'Promotion Performance'[Baseline Measurable] = TRUE()) + 0", "int",
      "Promotions with at least 28 baseline trading days in the 8 weeks before start.", "Promotions"),
    M("Promotions Paying Back", "CALCULATE(COUNTROWS('Promotion Performance'), 'Promotion Performance'[Net Promo Return] > 0, 'Promotion Performance'[Baseline Measurable] = TRUE()) + 0", "int",
      "Promotions with a measurable baseline whose incremental GP exceeded support cost.", "Promotions"),
    M("Average Volume Lift %", "CALCULATE(AVERAGE('Promotion Performance'[Volume Lift]), 'Promotion Performance'[Baseline Measurable] = TRUE())", "pct",
      "Mean unit uplift vs baseline across measurable promotions.", "Promotions"),
    M("Discount Applied on Invoice %", "AVERAGE('Promotion Performance'[Discount Applied On Invoice])", "pct",
      "Average discount actually on invoices during the promotion window (compare with stated discount).", "Promotions"),
    M("Promotion Incremental Units", "SUM('Promotion Performance'[Incremental Units])", "int", "Units above baseline.", "Promotions"),
])

# ---------------------------------------------------------------- supply chain facts
LAST_INV = "VAR _k = CALCULATE(MAX('Inventory Snapshot'[Date Key]))"
table("Inventory Snapshot", "fact_inventory_snapshot", "Weekly (Sunday) warehouse stock by batch. Semi-additive: stock measures take the latest snapshot in context. Near-expiry = 25% or less of shelf life remaining (business assumption).", [
    C("date_key", "Date Key", "integer", "hs"), C("warehouse_key", "Warehouse Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"),
    C("region_key", "Region Key", "integer", "hs"), C("batch_id", "Batch", "string", "h"), C("qty_on_hand", "Qty On Hand", "integer", "h"),
    C("qty_reserved", "Qty Reserved", "integer", "h"), C("qty_available_calc", "Qty Available", "integer", "h"),
    C("qty_available_reported", "Qty Available Reported", "integer", "h"), C("days_to_expiry", "Days To Expiry", "integer", "s"),
    C("remaining_shelf_life_pct", "Remaining Shelf Life", "double", "s", fmt="0%"), C("is_near_expiry", "Is Near Expiry", "boolean"),
    C("stock_value_std", "Stock Value", "decimal", "h"), C("is_zero_available", "Is Zero Available", "boolean")], [
    M("Inventory Units", f"""
        {LAST_INV}
        RETURN CALCULATE(SUM('Inventory Snapshot'[Qty On Hand]), 'Inventory Snapshot'[Date Key] = _k)""", "int",
      "Units on hand at the latest snapshot in context (semi-additive).", "Inventory"),
    M("Inventory Value", f"""
        {LAST_INV}
        RETURN CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Date Key] = _k)""", "egp",
      "Stock on hand at standard cost, latest snapshot in context; EGP.", "Inventory"),
    M("Near-Expiry Stock Value", f"""
        {LAST_INV}
        RETURN CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Date Key] = _k, 'Inventory Snapshot'[Is Near Expiry] = TRUE())""", "egp",
      "Stock with 25% or less of shelf life left at the latest snapshot, at standard cost.", "Inventory"),
    M("Near-Expiry Stock %", "DIVIDE([Near-Expiry Stock Value], [Inventory Value])", "pct", "Share of stock value close to expiry.", "Inventory"),
    M("Average Near-Expiry Stock Value", """
        AVERAGEX(VALUES('Inventory Snapshot'[Date Key]),
            CALCULATE(SUM('Inventory Snapshot'[Stock Value]), 'Inventory Snapshot'[Is Near Expiry] = TRUE()))""", "egp",
      "Average near-expiry stock value per weekly snapshot across the period - the recurring exposure.", "Inventory"),
    M("Days of Cover", f"""
        VAR _units = [Inventory Units]
        VAR _days = CALCULATE(COUNTROWS('Date'), {AP})
        VAR _daily = DIVIDE(CALCULATE([Sales Volume], {AP}), _days)
        RETURN DIVIDE(_units, _daily)""", "dec1",
      "Latest stock / average daily units sold in the period. CAVEAT: warehouse stock and invoice volume look to be on different scales.", "Inventory"),
    M("Stockout Proxy %", """
        DIVIDE(
            CALCULATE(COUNTROWS('Inventory Snapshot'), 'Inventory Snapshot'[Is Zero Available] = TRUE()),
            COUNTROWS('Inventory Snapshot'))""", "pct2",
      "PROXY, not a true stockout rate: share of warehouse x SKU x week snapshots with zero available stock. A real measure needs order lines (requested vs fulfilled) and daily/outlet stock.", "Inventory"),
])
LAST_DM = "VAR _k = CALCULATE(MAX('Distributor Month'[Date Key]))"
table("Distributor Month", "fact_distributor_month", "Month x distributor x SKU: ERP sell-in, distributor-reported receipts, sell-out and closing stock. Distributor SKUs mapped to ERP products (UNKNOWN-#### recovered).", [
    C("date_key", "Date Key", "integer", "hs"), C("distributor_key", "Distributor Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"),
    C("region_key", "Region Key", "integer", "hs"), C("receipts_qty", "Receipts Qty", "integer", "h"), C("sell_in_qty_erp", "Sell In Qty ERP", "long", "h"),
    C("sell_in_value", "Sell In Value", "decimal", "h"), C("sell_in_unit_price", "Sell In Unit Price", "decimal", "h"),
    C("sellout_qty_reported", "Sellout Qty Reported", "integer", "h"), C("sellout_qty_outlets", "Sellout Qty Outlets", "long", "h"),
    C("sellout_value", "Sellout Value", "decimal", "h"), C("active_outlets", "Active Outlets", "long", "h"),
    C("opening_inventory_qty", "Opening Inventory Qty", "integer", "h"), C("closing_inventory_qty", "Closing Inventory Qty", "integer", "h"),
    C("rollforward_gap_qty", "Rollforward Gap Qty", "integer", "h"), C("dq_sku_recovered", "DQ SKU Recovered", "boolean")], [
    M("Sell-in Units", "SUM('Distributor Month'[Receipts Qty])", "int", "Units received by distributors (equals ERP sell-in).", "Distributors"),
    M("Sell-out Units", "SUM('Distributor Month'[Sellout Qty Reported])", "int", "Units distributors report selling to outlets.", "Distributors"),
    M("Sell-out Value", "SUM('Distributor Month'[Sellout Value])", "egp", "Outlet-level sell-out value at distributor prices.", "Distributors"),
    M("Sell-through %", "DIVIDE([Sell-out Units], [Sell-in Units])", "pct", "Sell-out / sell-in. Below ~85% (the peer norm) means stock is building in the channel.", "Distributors"),
    M("Distributor Stock Units", f"""
        {LAST_DM}
        RETURN CALCULATE(SUM('Distributor Month'[Closing Inventory Qty]), 'Distributor Month'[Date Key] = _k)""", "int",
      "Distributor closing stock at the latest month in context (semi-additive).", "Distributors"),
    M("Distributor Months of Cover", f"""
        {LAST_DM}
        VAR _stock = [Distributor Stock Units]
        VAR _sellout = CALCULATE([Sell-out Units], 'Distributor Month'[Date Key] = _k)
        RETURN DIVIDE(_stock, _sellout)""", "dec2", "Closing stock / that month's sell-out. Peers run at ~0.6 months.", "Distributors"),
    M("Distributor Stock Value", f"""
        {LAST_DM}
        RETURN SUMX(FILTER('Distributor Month', 'Distributor Month'[Date Key] = _k),
                    'Distributor Month'[Closing Inventory Qty] * 'Distributor Month'[Sell In Unit Price])""", "egp",
      "Closing distributor stock valued at DairyCo's sell-in price, latest month in context.", "Distributors"),
    M("Excess Channel Stock Value", f"""
        {LAST_DM}
        VAR _benchmarkMonths = 0.6
        RETURN SUMX(FILTER('Distributor Month', 'Distributor Month'[Date Key] = _k),
                    MAX(0, 'Distributor Month'[Closing Inventory Qty] - _benchmarkMonths * 'Distributor Month'[Sellout Qty Reported])
                        * 'Distributor Month'[Sell In Unit Price])""", "egp",
      "Distributor stock above 0.6 months of cover (peer norm), at sell-in price - revenue pulled forward that must still sell through.", "Distributors"),
    M("Sell-in minus Sell-out Units", "[Sell-in Units] - [Sell-out Units]", "int", "Units shipped into the channel but not sold out in the period.", "Distributors"),
])
table("Demand Forecast", "fact_demand_forecast", "MRP monthly demand forecast by SKU (the incumbent forecast; the production plan copies it).", [
    C("date_key", "Date Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"), C("forecast_qty", "Forecast Qty", "integer", "h")], [
    M("Forecast Units", "SUM('Demand Forecast'[Forecast Qty])", "int", "MRP forecast units.", "Planning"),
    M("Forecast Bias %", "DIVIDE([Forecast Units] - [Sales Volume], [Sales Volume])", "pct", "(Forecast - actual) / actual. Positive = over-forecast (ageing stock risk), negative = under-forecast (stockout risk).", "Planning"),
    M("Forecast Error % (WAPE)", """
        VAR _grid = CROSSJOIN(VALUES('Product'[Product Key]), VALUES('Date'[Year Month]))
        VAR _absErr = SUMX(_grid, ABS([Forecast Units] - [Sales Volume]))
        RETURN DIVIDE(_absErr, [Sales Volume])""", "pct", "Weighted absolute percentage error at SKU x month (sum of |forecast - actual| / actual).", "Planning"),
])

# ---------------------------------------------------------------- manufacturing & workforce facts
table("Production", "fact_production", "Production orders (grain: order = month x plant x line x shift x SKU).", [
    C("production_order_id", "Production Order Id", "integer", "hs"), C("date_key", "Date Key", "integer", "hs"),
    C("production_unit_key", "Production Unit Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"),
    C("planned_qty", "Planned Qty", "integer", "h"), C("actual_qty", "Actual Qty", "integer", "h"), C("good_qty", "Good Qty", "integer", "h"),
    C("scrap_qty", "Scrap Qty", "integer", "h"), C("downtime_minutes", "Downtime Minutes Amount", "integer", "h"),
    C("downtime_reason", "Downtime Reason", "string"), C("material_shortage_flag", "Material Shortage", "boolean"),
    C("scrap_value_std", "Scrap Value Amount", "decimal", "h"), C("good_value_std", "Good Value Amount", "decimal", "h")], [
    M("Planned Units", "SUM('Production'[Planned Qty])", "int", "Planned production units.", "Production"),
    M("Actual Units", "SUM('Production'[Actual Qty])", "int", "Units produced (good + scrap).", "Production"),
    M("Good Units", "SUM('Production'[Good Qty])", "int", "Units passing quality.", "Production"),
    M("Scrap Units", "SUM('Production'[Scrap Qty])", "int", "Units scrapped.", "Production"),
    M("Production Plan Attainment %", "DIVIDE([Actual Units], [Planned Units])", "pct", "Actual / planned units - the figure Operations reports.", "Production"),
    M("Good Output Attainment %", "DIVIDE([Good Units], [Planned Units])", "pct", "Good / planned units - what customers can actually be served from.", "Production"),
    M("Scrap Rate %", "DIVIDE([Scrap Units], [Actual Units])", "pct2", "Scrap / actual units.", "Production"),
    M("Downtime Hours", "DIVIDE(SUM('Production'[Downtime Minutes Amount]), 60)", "dec1", "Unplanned downtime hours.", "Production"),
    M("Downtime Minutes per Order", "DIVIDE(SUM('Production'[Downtime Minutes Amount]), COUNTROWS('Production'))", "dec1", "Average downtime per production order.", "Production"),
    M("Scrap Cost", "SUM('Production'[Scrap Value Amount])", "egp", "Scrapped units at standard cost; EGP.", "Production"),
    M("Benchmark Scrap Rate %", """
        CALCULATE([Scrap Rate %], REMOVEFILTERS('Production Unit'), 'Production Unit'[Plant] = "Plant 1")""", "pct2",
      "Conservative internal benchmark: Plant 1 average scrap rate (all shifts) in the same period. Stretch benchmark = Plant 1 day shifts (~1.8%).", "Production"),
    M("Avoidable Scrap Cost", """
        VAR _benchmark = [Benchmark Scrap Rate %]
        RETURN SUMX('Production',
            MAX(0, 'Production'[Scrap Qty] - 'Production'[Actual Qty] * _benchmark)
                * DIVIDE('Production'[Scrap Value Amount], 'Production'[Scrap Qty]))""", "egp",
      "Scrap above the Plant 1 average rate, at standard cost - cost removable by bringing Plant 2 and night shifts to Plant 1 practice (Leak 2).", "Production"),
])
table("Labour", "fact_labour_month", "Payroll and attendance AGGREGATED to month x plant x line x shift (minimum 5 employees per cell). No employee-level pay is in the model. Cost columns are hidden from the Regional Manager role (OLS).", [
    C("date_key", "Date Key", "integer", "hs"), C("production_unit_key", "Production Unit Key", "integer", "hs"),
    C("headcount", "Headcount", "long", "h"), C("attendance_hours", "Attendance Hours", "double", "h"), C("absence_hours", "Absence Hours", "double", "h"),
    C("overtime_hours", "Overtime Hours", "double", "h"), C("overtime_cost", "Overtime Cost Amount", "decimal", "h"),
    C("base_salary", "Base Salary Amount", "decimal", "h"), C("allowances", "Allowances Amount", "decimal", "h"),
    C("total_labour_cost", "Total Labour Cost Amount", "decimal", "h")], [
    M("Labour Cost", "SUM('Labour'[Total Labour Cost Amount])", "egp", "Base + overtime + allowances; EGP. Restricted (OLS).", "Workforce"),
    M("Overtime Cost", "SUM('Labour'[Overtime Cost Amount])", "egp", "Overtime pay; EGP. Restricted (OLS).", "Workforce"),
    M("Overtime % of Labour Cost", "DIVIDE([Overtime Cost], [Labour Cost])", "pct", "Overtime share of labour cost.", "Workforce"),
    M("Overtime Hours Total", "SUM('Labour'[Overtime Hours])", "int", "Overtime hours worked.", "Workforce"),
    M("Employee Months", "SUM('Labour'[Headcount])", "int", "Sum of monthly headcount (employee-months).", "Workforce"),
    M("Average Headcount", "AVERAGEX(VALUES('Date'[Year Month]), CALCULATE(SUM('Labour'[Headcount])))", "int", "Average monthly headcount.", "Workforce"),
    M("Overtime Hours per Employee", "DIVIDE([Overtime Hours Total], [Employee Months])", "dec1", "Overtime hours per employee per month.", "Workforce"),
    M("Absence Rate %", """
        VAR _abs = SUM('Labour'[Absence Hours])
        RETURN DIVIDE(_abs, SUM('Labour'[Attendance Hours]) + _abs)""", "pct", "Absence hours / scheduled hours.", "Workforce"),
    M("Labour Cost per Good Unit", "DIVIDE([Labour Cost], [Good Units])", "dec2", "Labour cost / good units produced. CAVEAT: payroll appears to be on a larger scale than production volume; use for relative comparison.", "Workforce"),
])

# ---------------------------------------------------------------- CRM
table("CRM Opportunity", "fact_crm_opportunity", "Salesforce opportunities (grain: opportunity), dated by created month. CRM covers Modern Trade and Key Accounts only.", [
    C("opportunity_id", "Opportunity Id", "string", "hs"), C("date_key", "Date Key", "integer", "hs"), C("customer_key", "Customer Key", "integer", "hs"),
    C("region_key", "Region Key", "integer", "hs"), C("opportunity_value", "Opportunity Value", "decimal", "h"), C("stage", "Stage", "string"),
    C("opportunity_type", "Opportunity Type", "string"), C("is_open", "Is Open", "boolean"), C("is_stale", "Is Stale", "boolean"),
    C("is_won", "Is Won", "boolean"), C("expected_close_date_key", "Expected Close Date Key", "integer", "hs")], [
    M("Open Pipeline Value", "CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Open] = TRUE())", "egp", "Value of open opportunities.", "CRM"),
    M("Stale Pipeline %", "DIVIDE(CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Stale] = TRUE()), [Open Pipeline Value])", "pct", "Open pipeline already past its expected close date.", "CRM"),
    M("Win Rate %", "DIVIDE(CALCULATE(COUNTROWS('CRM Opportunity'), 'CRM Opportunity'[Is Won] = TRUE()), CALCULATE(COUNTROWS('CRM Opportunity'), 'CRM Opportunity'[Is Open] = FALSE()))", "pct", "Won / closed opportunities (count).", "CRM"),
    M("Closed Won Value", "CALCULATE(SUM('CRM Opportunity'[Opportunity Value]), 'CRM Opportunity'[Is Won] = TRUE())", "egp", "Value of won opportunities (CRM scale differs from ERP revenue).", "CRM"),
])
table("CRM Activity", "fact_crm_activity", "Salesforce activities (grain: activity).", [
    C("activity_id", "Activity Id", "string", "hs"), C("date_key", "Date Key", "integer", "hs"), C("customer_key", "Customer Key", "integer", "hs"),
    C("region_key", "Region Key", "integer", "hs"), C("activity_type", "Activity Type", "string"), C("duration_minutes", "Duration Minutes", "integer", "h")], [
    M("Activities", "COUNTROWS('CRM Activity')", "int", "Sales activities logged.", "CRM"),
    M("Activity Hours", "DIVIDE(SUM('CRM Activity'[Duration Minutes]), 60)", "dec1", "Hours of logged sales activity.", "CRM"),
])

# ---------------------------------------------------------------- AI outputs
table("ML Demand Forecast", "ml_demand_forecast", "Output of nb_05 (MLflow-tracked). record_type 'backtest' = rolling-origin out-of-sample months; 'forecast' = next month.", [
    C("date_key", "Date Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"), C("record_type", "Record Type", "string"),
    C("actual_qty", "Backtest Actual Qty", "double", "h"), C("mrp_forecast", "MRP Forecast Qty", "double", "h"),
    C("naive_forecast", "Naive Forecast Qty", "double", "h"), C("rule_forecast", "Rule Forecast Qty", "double", "h"),
    C("ml_forecast", "ML Forecast Qty", "double", "h"),
    C("model_run_id", "Model Run Id", "string", "h")], [
    M("ML Forecast Units", "SUM('ML Demand Forecast'[ML Forecast Qty])", "int", "Machine-learning forecast units.", "AI Forecast"),
    M("ML Backtest WAPE %", """
        VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest")
        RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[ML Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))""", "pct",
      "Out-of-sample weighted absolute % error of the ML model.", "AI Forecast"),
    M("MRP Backtest WAPE %", """
        VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest")
        RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[MRP Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))""", "pct",
      "Weighted absolute % error of the incumbent MRP forecast over the same backtest months.", "AI Forecast"),
    M("Rule Backtest WAPE %", """
        VAR _bt = FILTER('ML Demand Forecast', 'ML Demand Forecast'[Record Type] = "backtest")
        RETURN DIVIDE(SUMX(_bt, ABS('ML Demand Forecast'[Rule Forecast Qty] - 'ML Demand Forecast'[Backtest Actual Qty])), SUMX(_bt, 'ML Demand Forecast'[Backtest Actual Qty]))""", "pct",
      "Error of the rule-based challenger (MRP x trailing 3-month actual/forecast ratio) over the same backtest months.", "AI Forecast"),
    M("Rule Forecast Units", "SUM('ML Demand Forecast'[Rule Forecast Qty])", "int", "Bias-corrected MRP forecast units (rule).", "AI Forecast"),
])
table("Stock Rebalancing", "ml_stock_rebalancing", "Warehouse x SKU recommendation from nb_05: target stock = ML forecast daily demand x (50% of shelf life); gap = on hand - target.", [
    C("warehouse_key", "Warehouse Key", "integer", "hs"), C("product_key", "Product Key", "integer", "hs"), C("region_key", "Region Key", "integer", "hs"),
    C("on_hand", "On Hand", "long", "h"), C("near_expiry_qty", "Near Expiry Qty", "long", "h"), C("forecast_daily_demand", "Forecast Daily Demand", "double", "h"),
    C("target_cover_days", "Target Cover Days", "double", "s", fmt="#,##0.0"), C("current_cover_days", "Current Cover Days", "double", "s", fmt="#,##0.0"),
    C("target_stock", "Target Stock", "double", "h"), C("stock_gap", "Stock Gap", "double", "h"), C("stock_gap_value", "Stock Gap Value", "double", "h"),
    C("action", "Recommended Action", "string"), C("model_run_id", "Rebalancing Run Id", "string", "h")], [
    M("Excess Stock Value", "CALCULATE(SUM('Stock Rebalancing'[Stock Gap Value]), 'Stock Rebalancing'[Stock Gap] > 0)", "egp", "Stock above target cover, at standard cost.", "AI Forecast"),
    M("Stock Shortfall Units", "-CALCULATE(SUM('Stock Rebalancing'[Stock Gap]), 'Stock Rebalancing'[Stock Gap] < 0) + 0", "int", "Units below target cover (stockout risk).", "AI Forecast"),
])

# ---------------------------------------------------------------- utility
table("Data Quality", "dq_summary", "Latest result of every silver data-quality rule (flag, don't silently fix).", [
    C("entity", "Entity", "string"), C("rule_id", "Rule Id", "string"), C("rule", "Rule", "string"), C("severity", "Severity", "string"),
    C("violations", "Violations Count", "long", "h"), C("batch_id", "DQ Batch", "string", "h"), C("run_at", "Checked At", "timestamp", fmt="yyyy-mm-dd hh:nn")], [
    M("DQ Violations", "SUM('Data Quality'[Violations Count])", "int", "Rows violating data-quality rules at the last run.", "Data Quality"),
    M("DQ Rules Breached", "CALCULATE(COUNTROWS('Data Quality'), 'Data Quality'[Violations Count] > 0)", "int", "Rules with at least one violation.", "Data Quality"),
])
table("Security User Region", "security_user_region", "RLS mapping: user principal name -> permitted region. Maintained by the BI owner (production: synced from Entra ID groups).", [
    C("user_upn", "User UPN", "string", "h"), C("region_key", "Region Key", "integer", "hs")], hidden=True)

# ---------------------------------------------------------------------------------------------------------------
REL = [("Sales", "Date Key", "Date", "Date Key"), ("Sales", "Customer Key", "Customer", "Customer Key"),
       ("Sales", "Product Key", "Product", "Product Key"), ("Sales", "Distributor Key", "Distributor", "Distributor Key"),
       ("Sales", "Region Key", "Region", "Region Key"), ("Sales", "Promotion Key", "Promotion", "Promotion Key"),
       ("Returns", "Date Key", "Date", "Date Key"), ("Returns", "Customer Key", "Customer", "Customer Key"),
       ("Returns", "Product Key", "Product", "Product Key"), ("Returns", "Region Key", "Region", "Region Key"),
       ("Returns", "Distributor Key", "Distributor", "Distributor Key"),
       ("Sales Target", "Date Key", "Date", "Date Key"), ("Sales Target", "Region Key", "Region", "Region Key"),
       ("Promotion Performance", "Promotion Key", "Promotion", "Promotion Key"), ("Promotion Performance", "Product Key", "Product", "Product Key"),
       ("Promotion Performance", "Region Key", "Region", "Region Key"), ("Promotion Performance", "Date Key", "Date", "Date Key"),
       ("Inventory Snapshot", "Date Key", "Date", "Date Key"), ("Inventory Snapshot", "Warehouse Key", "Warehouse", "Warehouse Key"),
       ("Inventory Snapshot", "Product Key", "Product", "Product Key"), ("Inventory Snapshot", "Region Key", "Region", "Region Key"),
       ("Distributor Month", "Date Key", "Date", "Date Key"), ("Distributor Month", "Distributor Key", "Distributor", "Distributor Key"),
       ("Distributor Month", "Product Key", "Product", "Product Key"), ("Distributor Month", "Region Key", "Region", "Region Key"),
       ("Demand Forecast", "Date Key", "Date", "Date Key"), ("Demand Forecast", "Product Key", "Product", "Product Key"),
       ("Production", "Date Key", "Date", "Date Key"), ("Production", "Production Unit Key", "Production Unit", "Production Unit Key"),
       ("Production", "Product Key", "Product", "Product Key"),
       ("Labour", "Date Key", "Date", "Date Key"), ("Labour", "Production Unit Key", "Production Unit", "Production Unit Key"),
       ("CRM Opportunity", "Date Key", "Date", "Date Key"), ("CRM Opportunity", "Customer Key", "Customer", "Customer Key"),
       ("CRM Opportunity", "Region Key", "Region", "Region Key"),
       ("CRM Activity", "Date Key", "Date", "Date Key"), ("CRM Activity", "Customer Key", "Customer", "Customer Key"),
       ("CRM Activity", "Region Key", "Region", "Region Key"),
       ("ML Demand Forecast", "Date Key", "Date", "Date Key"), ("ML Demand Forecast", "Product Key", "Product", "Product Key"),
       ("Stock Rebalancing", "Warehouse Key", "Warehouse", "Warehouse Key"), ("Stock Rebalancing", "Product Key", "Product", "Product Key"),
       ("Stock Rebalancing", "Region Key", "Region", "Region Key")]

ALLOWED = "CALCULATETABLE(VALUES('Security User Region'[Region Key]), 'Security User Region'[User UPN] = USERPRINCIPALNAME())"
ROLES = {
    "Executive": dict(desc="Executives and central functions: enterprise-wide view, no row filters.", perms={}),
    "Regional Manager": dict(desc="Regional managers: rows limited to regions mapped to their UPN in Security User Region. Manufacturing and aggregated workforce KPIs are company-wide and visible, but labour cost columns are hidden (OLS).",
        perms={"Region": f"'Region'[Region Key] IN {ALLOWED}", "Customer": f"'Customer'[Customer Region Key] IN {ALLOWED}",
               "Distributor": f"'Distributor'[Distributor Region Key] IN {ALLOWED}", "Warehouse": f"'Warehouse'[Warehouse Region Key] IN {ALLOWED}",
               "Security User Region": "'Security User Region'[User UPN] = USERPRINCIPALNAME()"},
        ols={"Labour": ["Overtime Cost Amount", "Base Salary Amount", "Allowances Amount", "Total Labour Cost Amount"]}),
}

# ---------------------------------------------------------------------------------------------------------------
def q(n):
    return f"'{n}'" if any(c in n for c in " .=:'-%()") or not n.isidentifier() else n

def desc_lines(text, indent):
    return "".join(f"{indent}/// {l}\n" for l in textwrap.wrap(text, 110))

def render_table(t, schema):
    types = dict(schema[t["entity"]])
    out = desc_lines(t["desc"], "") + f"table {q(t['name'])}\n"
    if t.get("date_table"):
        out += "\tdataCategory: Time\n"
    if t.get("hidden"):
        out += "\tisHidden\n"
    out += "\n"
    for m in t["measures"]:
        out += desc_lines(m["desc"], "\t")
        if "\n" in m["expr"]:
            body = textwrap.indent(m["expr"], "\t\t\t")
            out += f"\tmeasure {q(m['name'])} =\n{body}\n"
        else:
            out += f"\tmeasure {q(m['name'])} = {m['expr']}\n"
        out += f"\t\tformatString: {m['fmt']}\n\t\tdisplayFolder: {m['folder']}\n\n"
    for c in t["cols"]:
        st = types[c["src"]].split('"')[1].split("(")[0]
        out += f"\tcolumn {q(c['name'])}\n\t\tdataType: {TYPE[st]}\n"
        if "k" in c["flags"]:
            out += "\t\tisKey\n"
        if "h" in c["flags"]:
            out += "\t\tisHidden\n"
        if c.get("fmt"):
            out += f"\t\tformatString: {c['fmt']}\n"
        if "s" in c["flags"] or TYPE[st] in ("string", "boolean", "dateTime") or "h" in c["flags"]:
            out += "\t\tsummarizeBy: none\n"
        if c.get("dataCategory"):
            out += f"\t\tdataCategory: {c['dataCategory']}\n"
        out += f"\t\tsourceColumn: {c['src']}\n"
        if c.get("sort"):
            out += f"\t\tsortByColumn: {q(c['sort'])}\n"
        out += "\n"
    for hname, levels in t.get("hierarchies", []):
        out += f"\thierarchy {q(hname)}\n\n"
        for lv in levels:
            out += f"\t\tlevel {q(lv)}\n\t\t\tcolumn: {q(lv)}\n\n"
    out += f"\tpartition {q(t['name'])} = entity\n\t\tmode: directLake\n\t\tsource\n\t\t\tentityName: {t['entity']}\n\t\t\texpressionSource: 'DirectLake - Gold'\n\n"
    return out

def build():
    if not (ROOT / ".platform").exists():
        sys.exit(f"{ROOT} is not a Fabric-synced item folder (no .platform). Connect the Dev workspace to Git "
                 "and commit it first.")
    schema = json.loads(SCHEMA.read_text())
    d = ROOT / "definition"
    for owned in ("tables", "roles"):          # fully generated: remove so dropped tables/roles disappear
        shutil.rmtree(d / owned, ignore_errors=True)
        (d / owned).mkdir(parents=True)
    files = {}
    model = ("model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n"
             "\tsourceQueryCulture: en-US\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n")
    model += "".join(f"ref table {q(t['name'])}\n" for t in TABLES) + "\n"
    model += "".join(f"ref role {q(r)}\n" for r in ROLES) + "\n"
    files["model.tmdl"] = model
    rel = ""
    for f_t, f_c, t_t, t_c in REL:
        rel += f"relationship '{f_t} to {t_t} ({f_c})'\n\tfromColumn: {q(f_t)}.{q(f_c)}\n\ttoColumn: {q(t_t)}.{q(t_c)}\n\n"
    files["relationships.tmdl"] = rel
    for t in TABLES:
        files[f"tables/{t['name']}.tmdl"] = render_table(t, schema)
    for r, spec in ROLES.items():
        s = desc_lines(spec["desc"], "") + f"role {q(r)}\n\tmodelPermission: read\n\n"
        for tb, expr in spec["perms"].items():
            s += f"\ttablePermission {q(tb)} = {expr}\n\n"
        for tb, cols in spec.get("ols", {}).items():
            s += f"\ttablePermission {q(tb)}\n\n" + "".join(f"\t\tcolumnPermission {q(c)} = none\n\n" for c in cols)
        files[f"roles/{r}.tmdl"] = s
    for rel_path, content in files.items():
        (d / rel_path).write_text(content)
    n_m = sum(len(t["measures"]) for t in TABLES)
    print(f"wrote {len(files)} files: {len(TABLES)} tables, {len(REL)} relationships, {n_m} measures, {len(ROLES)} roles -> {d}")

if __name__ == "__main__":
    build()
