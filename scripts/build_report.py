"""Generate the 3-page DairyCo management report (Power BI report.json format) bound to the semantic model.

    python build_report.py                      # write report/DairyCo Management.Report (PBIP, byPath)
    python build_report.py deploy <workspace>   # also create/update the report in the workspace (byConnection)
"""
import base64, hashlib, json, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))

REPORT = "DairyCo Management"
MODEL = "DairyCo Analytics"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / f"{REPORT}.Report"
THEME_SRC = ROOT / "report" / "theme" / "Fluent2-CY26SU09.json"
W, H = 1920, 1080
NAVY, RED, GREEN, GREY = "#1F3864", "#C0392B", "#1E8449", "#595959"

_z = [0]
def _id(*parts):
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:20]

def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}

def visual(page, vtype, x, y, w, h, roles=None, title=None, objects=None, sort=None, vc=None, filters=None):
    """roles: {role: [(table, field, 'm'|'c'), ...]}"""
    roles = roles or {}
    _z[0] += 1
    ents, frm, sel, proj = {}, [], [], {}
    def src(tbl):
        if tbl not in ents:
            ents[tbl] = f"t{len(ents)}"
            frm.append({"Name": ents[tbl], "Entity": tbl, "Type": 0})
        return ents[tbl]
    for role, fields in roles.items():
        proj[role] = []
        for i, (tbl, fld, kind) in enumerate(fields):
            ref = f"{tbl}.{fld}"
            expr = {"Expression": {"SourceRef": {"Source": src(tbl)}}, "Property": fld}
            sel.append({("Measure" if kind == "m" else "Column"): expr, "Name": ref, "NativeReferenceName": fld})
            p = {"queryRef": ref}
            if kind == "c" and role in ("Category", "Rows", "Values") and i == 0 and vtype != "tableEx":
                p["active"] = True
            proj[role].append(p)
    sv = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        pq = {"Version": 2, "From": frm, "Select": sel}
        if sort:
            tbl, fld, kind, direction = sort
            pq["OrderBy"] = [{"Direction": 2 if direction == "desc" else 1,
                              "Expression": {("Measure" if kind == "m" else "Column"): {"Expression": {"SourceRef": {"Source": src(tbl)}}, "Property": fld}}}]
            sv["hasDefaultSort"] = True
        sv["projections"] = proj
        sv["prototypeQuery"] = pq
    if objects:
        sv["objects"] = objects
    vco = dict(vc or {})
    if title:
        vco["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontColor": {"solid": {"color": lit(NAVY)}}}}]
    if vco:
        sv["vcObjects"] = vco
    name = _id(page, vtype, x, y)
    cfg = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": _z[0], "width": w, "height": h, "tabOrder": _z[0]}}],
           "singleVisual": sv}
    return {"config": json.dumps(cfg), "filters": json.dumps(filters or []), "height": h, "width": w, "x": x, "y": y, "z": _z[0]}

def year_filter(year=2026):
    return [{"name": _id("yf", year), "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Date"}}, "Property": "Year"}},
             "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "Date", "Type": 0}],
                        "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Year"}}],
                                                        "Values": [[{"Literal": {"Value": f"{year}L"}}]]}}}]},
             "type": "Categorical", "howCreated": 1}]
Y26 = year_filter(2026)

def textbox(page, x, y, w, h, runs):
    """runs: list of paragraphs; each paragraph = list of (text, size_pt, bold, color)."""
    paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "fontWeight": "bold" if b else "normal", "color": c}}
                           for t, s, b, c in p]} for p in runs]
    return visual(page, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]})

def slicer(page, x, y, w, h, tbl, fld, title=None):
    return visual(page, "slicer", x, y, w, h, {"Values": [(tbl, fld, "c")]}, title=title,
                  objects={"data": [{"properties": {"mode": lit("Dropdown")}}]})

def cards(page, x, y, w, h, measures, title=None):
    return visual(page, "multiRowCard", x, y, w, h, {"Values": [(t, m, "m") for t, m in measures]}, title=title)

def kpi(page, x, y, w, h, tbl, m, title, filters=None, size=26, color=NAVY, units=None, precision=None):
    lab = {"fontSize": lit(size), "color": {"solid": {"color": lit(color)}}}
    if units:
        lab["labelDisplayUnits"] = lit(units)
    if precision is not None:
        lab["labelPrecision"] = {"expr": {"Literal": {"Value": f"{precision}L"}}}
    return visual(page, "card", x, y, w, h, {"Values": [(tbl, m, "m")]}, title=title, filters=filters,
                  objects={"labels": [{"properties": lab}],
                           "categoryLabels": [{"properties": {"show": lit(False)}}]})

def header(page, title, subtitle):
    return textbox(page, 20, 10, 1460, 90, [[(title, 20, True, NAVY)], [(subtitle, 11, False, GREY)]])

def page(name, display, visuals, ordinal):
    return {"config": "{}", "displayName": display, "displayOption": 1, "filters": "[]", "height": H, "name": name,
            "ordinal": ordinal, "visualContainers": visuals, "width": W}

# =============================================================== Page 1: Executive Performance
P1 = "exec"
kx = [(20 + i * 236, 110) for i in range(8)]
p1 = [header(P1, "Revenue +7.6%, gross profit −5.4%: the margin broke in January 2026",
             "Jan–Aug 2026 vs Jan–Aug 2025 (like-for-like). Every figure is a governed measure in the DairyCo Analytics semantic model."),
      slicer(P1, 1500, 20, 190, 60, "Region", "Region", "Region"), slicer(P1, 1710, 20, 190, 60, "Customer", "Channel", "Channel")]
for (x, y), (t, m, lab) in zip(kx, [("Sales", "Net Revenue", "Net revenue 2026 YTD (EGP)"), ("Sales", "Revenue Growth %", "Revenue growth vs 2025"),
                                    ("Sales", "Gross Profit", "Gross profit 2026 YTD (EGP)"), ("Sales", "Gross Profit Growth %", "Gross profit growth vs 2025"),
                                    ("Sales", "Gross Margin %", "Gross margin 2026 YTD"), ("Sales", "Gross Margin Change pp", "Margin change vs 2025 (pp)"),
                                    ("Sales", "Sales Volume Growth %", "Volume growth vs 2025"), ("Returns", "Return Rate %", "Return rate 2026 YTD")]):
    money = m in ("Net Revenue", "Gross Profit")
    p1.append(kpi(P1, x, y, 226, 120, t, m, lab, filters=Y26, units=1000000 if money else None, precision=2 if money else None))
p1 += [
    visual(P1, "lineStackedColumnComboChart", 20, 250, 1180, 400,
           {"Category": [("Date", "Year Month", "c")], "Y": [("Sales", "Net Revenue", "m")], "Y2": [("Sales", "Gross Margin %", "m")]},
           title="Net revenue (columns) vs gross margin % (line): margin steps down from 28.4% to 25.0% in Jan 2026",
           objects={"valueAxis": [{"properties": {"secStart": lit(0.2), "secEnd": lit(0.3)}}]}),
    textbox(P1, 1220, 250, 680, 40, [[("The five profit leaks (EGP, Jan 2025 – Aug 2026)", 13, True, NAVY)]]),
    kpi(P1, 1220, 290, 336, 115, "Sales", "Cost Variance vs Standard", "1 · Cost above stale standard (Milk, 2026)", size=20, color=RED, units=1000, precision=0),
    kpi(P1, 1564, 290, 336, 115, "Production", "Avoidable Scrap Cost", "2 · Avoidable scrap vs Plant 1 rate", size=20, color=RED, units=1000, precision=0),
    kpi(P1, 1220, 413, 336, 115, "Distributor Month", "Excess Channel Stock Value", "3 · Excess distributor stock (latest month)", size=20, color=RED, units=1000, precision=0),
    kpi(P1, 1564, 413, 336, 115, "Inventory Snapshot", "Average Near-Expiry Stock Value", "4 · Near-expiry stock (avg per week)", size=20, color=RED, units=1000, precision=0),
    kpi(P1, 1220, 536, 680, 114, "Promotion Performance", "Net Promotion Return", "5 · Net return on promotion spend (incremental GP − support cost)", size=20, color=RED, units=1000000, precision=2),
    visual(P1, "hundredPercentStackedColumnChart", 20, 670, 600, 390,
           {"Category": [("Date", "Year", "c")], "Y": [("Sales", "Net Revenue", "m")], "Series": [("Product", "Category", "c")]},
           title="Mix shift: Milk (lowest margin) doubles its share of revenue"),
    visual(P1, "clusteredBarChart", 640, 670, 600, 390,
           {"Category": [("Product", "Category", "c")], "Y": [("Sales", "Gross Margin %", "m"), ("Sales", "Gross Margin % at Standard Cost", "m")]},
           title="Gross margin actual vs at (stale) standard cost", sort=("Sales", "Gross Margin %", "m", "desc")),
    visual(P1, "tableEx", 1260, 670, 640, 390,
           {"Values": [("Region", "Region", "c"), ("Sales", "Net Revenue", "m"), ("Sales", "Revenue Growth %", "m"),
                       ("Sales", "Gross Margin %", "m"), ("Sales Target", "Target Attainment Index", "m")]},
           title="Regions 2026 YTD (Target Attainment Index: 1.00 = company average; targets under restatement)",
           sort=("Sales", "Net Revenue", "m", "desc"), filters=Y26),
]

# =============================================================== Page 2: Commercial
P2 = "comm"
p2 = [header(P2, "Commercial: growth sits in five Milk SKUs, Nile is stuffing its channel, promotions don't pay back",
             "Sell-in (ERP) vs sell-out (distributor platform) · promotion attribution by product + region + date · CRM coverage: Modern Trade & Key Accounts only"),
      slicer(P2, 1500, 20, 190, 60, "Region", "Region", "Region"), slicer(P2, 1710, 20, 190, 60, "Customer", "Channel", "Channel")]
for (x, y), (t, m, lab) in zip(kx, [("Sales", "Net Revenue", "Net revenue (EGP)"), ("Sales", "Revenue Growth %", "Revenue growth YoY"),
                                    ("Sales", "Average Selling Price", "Avg selling price"), ("Sales", "Invoice Discount %", "Invoice discount"),
                                    ("Sales", "Promoted Revenue %", "Revenue on promotion"), ("Distributor Month", "Sell-through %", "Distributor sell-through"),
                                    ("CRM Opportunity", "Open Pipeline Value", "Open CRM pipeline"), ("CRM Opportunity", "Stale Pipeline %", "Pipeline past close date")]):
    p2.append(kpi(P2, x, y, 226, 120, t, m, lab + (" (2026)" if t in ("Sales", "Distributor Month") else ""), filters=Y26 if t in ("Sales", "Distributor Month") else None,
                  units=1000000 if m in ("Net Revenue", "Open Pipeline Value") else None, precision=2 if m in ("Net Revenue", "Open Pipeline Value") else None))
p2 += [
    visual(P2, "clusteredBarChart", 20, 250, 560, 810,
           {"Category": [("Product", "Product", "c")], "Y": [("Sales", "Revenue Growth %", "m")]},
           title="Revenue growth by SKU, 2026 vs 2025: Milk 1001–1005 +120–170%, the rest −18% to −27%",
           sort=("Sales", "Revenue Growth %", "m", "desc"), filters=Y26),
    visual(P2, "tableEx", 600, 250, 1300, 300,
           {"Values": [("Distributor", "Distributor", "c"), ("Sales", "Net Revenue", "m"), ("Sales", "Revenue Growth %", "m"),
                       ("Distributor Month", "Sell-in Units", "m"), ("Distributor Month", "Sell-out Units", "m"),
                       ("Distributor Month", "Sell-through %", "m"), ("Distributor Month", "Distributor Months of Cover", "m"),
                       ("Distributor Month", "Excess Channel Stock Value", "m"), ("Returns", "Return Rate %", "m")]},
           title="Distributor scorecard 2026 YTD — judge distributors on sell-out and stock cover, not sell-in",
           sort=("Distributor Month", "Distributor Months of Cover", "m", "desc"), filters=Y26),
    visual(P2, "lineChart", 600, 570, 640, 490,
           {"Category": [("Date", "Year Month", "c")], "Y": [("Distributor Month", "Sell-in Units", "m"), ("Distributor Month", "Sell-out Units", "m"),
                                                          ("Distributor Month", "Distributor Stock Units", "m")]},
           title="Sell-in vs sell-out vs distributor stock (select a distributor above)"),
    visual(P2, "tableEx", 1260, 570, 640, 490,
           {"Values": [("Promotion", "Promotion", "c"), ("Promotion Performance", "Promotion Support Cost", "m"),
                       ("Promotion Performance", "Average Volume Lift %", "m"), ("Promotion Performance", "Net Promotion Return", "m")]},
           title="Promotion ROI — 0 of 37 measurable promotions cover their support cost",
           sort=("Promotion Performance", "Net Promotion Return", "m", "asc")),
]

# =============================================================== Page 3: Operations
P3 = "ops"
p3 = [header(P3, "Operations: plan attainment hides Plant 2 / Shift C scrap and a copy-paste forecast",
             "Production plan attainment on actual vs good output · forecast bias by category · weekly warehouse snapshots · labour aggregated to plant/line/shift (no individual pay)"),
      slicer(P3, 1500, 20, 190, 60, "Date", "Year", "Year"), slicer(P3, 1710, 20, 190, 60, "Production Unit", "Plant", "Plant")]
for (x, y), (t, m, lab) in zip(kx, [("Production", "Production Plan Attainment %", "Plan attainment (actual)"), ("Production", "Good Output Attainment %", "Plan attainment (good)"),
                                    ("Production", "Scrap Rate %", "Scrap rate"), ("Labour", "Overtime Hours per Employee", "OT hrs / employee / month"),
                                    ("Demand Forecast", "Forecast Error % (WAPE)", "MRP forecast error (WAPE)"), ("Demand Forecast", "Forecast Bias %", "MRP forecast bias"),
                                    ("Inventory Snapshot", "Near-Expiry Stock %", "Stock near expiry"), ("Inventory Snapshot", "Stockout Proxy %", "Stockout proxy*")]):
    p3.append(kpi(P3, x, y, 226, 120, t, m, lab))
p3 += [
    visual(P3, "tableEx", 20, 250, 1060, 380,
           {"Values": [("Production Unit", "Plant", "c"), ("Production Unit", "Shift", "c"), ("Production", "Production Plan Attainment %", "m"),
                       ("Production", "Scrap Rate %", "m"), ("Labour", "Overtime Hours per Employee", "m"),
                       ("Labour", "Absence Rate %", "m"), ("Production", "Avoidable Scrap Cost", "m")]},
           title="Plant × shift: scrap, downtime, overtime and absence move together (avoidable scrap vs Plant 1 average)",
           sort=("Production", "Scrap Rate %", "m", "desc")),
    visual(P3, "clusteredBarChart", 1100, 250, 390, 380,
           {"Category": [("Product", "Category", "c")], "Y": [("Demand Forecast", "Forecast Bias %", "m")]},
           title="MRP forecast bias by category (+ = over-forecast)", sort=("Demand Forecast", "Forecast Bias %", "m", "desc")),
    visual(P3, "clusteredBarChart", 1510, 250, 390, 380,
           {"Category": [("Product", "Category", "c")], "Y": [("Inventory Snapshot", "Days of Cover", "m")]},
           title="Warehouse days of cover by category", sort=("Inventory Snapshot", "Days of Cover", "m", "desc")),
    visual(P3, "clusteredBarChart", 20, 650, 600, 410,
           {"Category": [("Production", "Downtime Reason", "c")], "Y": [("Production", "Downtime Hours", "m")], "Series": [("Production Unit", "Plant", "c")]},
           title="Downtime hours by reason and plant", sort=("Production", "Downtime Hours", "m", "desc")),
    textbox(P3, 640, 650, 420, 50, [[("AI prototype — forecast error, 6-month out-of-sample backtest", 12, True, NAVY)]]),
    kpi(P3, 640, 700, 205, 115, "ML Demand Forecast", "MRP Backtest WAPE %", "MRP forecast (today)", size=22, color=RED),
    kpi(P3, 855, 700, 205, 115, "ML Demand Forecast", "Rule Backtest WAPE %", "Bias-corrected rule", size=22),
    kpi(P3, 640, 825, 205, 115, "ML Demand Forecast", "ML Backtest WAPE %", "ML correction model", size=22, color=GREEN),
    kpi(P3, 855, 825, 205, 115, "Stock Rebalancing", "Excess Stock Value", "Stock above target cover", size=22, units=1000000, precision=2),
    textbox(P3, 640, 945, 420, 110, [[("Target cover = 50% of shelf life. Stock and invoice volumes appear to be on different scales; use for allocation (which DC/SKU), not absolute value.", 10, False, GREY)]]),
    visual(P3, "tableEx", 1080, 650, 820, 410,
           {"Values": [("Data Quality", "Rule Id", "c"), ("Data Quality", "Rule", "c"), ("Data Quality", "Severity", "c"), ("Data Quality", "DQ Violations", "m")]},
           title="Data trust: latest data-quality checks (flagged, not silently fixed). *Stockout = proxy (no order/backorder data)",
           sort=("Data Quality", "DQ Violations", "m", "desc")),
]

SECTIONS = [page("ReportSection" + _id("p1"), "Executive Performance", p1, 0),
            page("ReportSection" + _id("p2"), "Commercial", p2, 1),
            page("ReportSection" + _id("p3"), "Operations", p3, 2)]

def report_json():
    cfg = {"version": "5.77", "themeCollection": {"baseTheme": {"name": "Fluent2-CY26SU09", "type": 2,
           "version": {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}}}, "activeSectionIndex": 0,
           "defaultDrillFilterOtherVisuals": True, "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
           "useStylableVisualContainerHeader": True, "queryLimitOption": 6, "useEnhancedTooltips": True, "exportDataMode": 1,
           "useDefaultAggregateDisplayName": True}}
    return {"config": json.dumps(cfg), "layoutOptimization": 0,
            "resourcePackages": [{"resourcePackage": {"disabled": False, "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": 202}],
                                                      "name": "SharedResources", "type": 2}}],
            "sections": SECTIONS}

def pbir(dataset_ref):
    return json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                       "version": "4.0", "datasetReference": dataset_ref}, indent=2)

def parts(dataset_ref):
    return {"definition.pbir": pbir(dataset_ref), "report.json": json.dumps(report_json(), indent=1),
            "StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU09.json": THEME_SRC.read_text()}

def write_local():
    if OUT.exists():
        shutil.rmtree(OUT)
    for p, c in parts({"byPath": {"path": f"../../semantic-model/{MODEL}.SemanticModel"}}).items():
        (OUT / p).parent.mkdir(parents=True, exist_ok=True); (OUT / p).write_text(c)
    print("wrote", OUT, sum(len(s["visualContainers"]) for s in SECTIONS), "visuals")

def deploy(ws_name):
    from fabric import workspace_id, item_id, call, lro
    ws = workspace_id(ws_name)
    sm = item_id(ws, MODEL, "SemanticModel")
    ref = {"byConnection": {"connectionString": f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{ws_name};initial catalog={MODEL};"
                                                f"integrated security=ClaimsToken;semanticmodelid={sm}"}}
    pl = [{"path": p, "payload": base64.b64encode(c.encode()).decode(), "payloadType": "InlineBase64"} for p, c in parts(ref).items()]
    rid = item_id(ws, REPORT, "Report")
    if rid:
        lro(call("POST", f"/workspaces/{ws}/reports/{rid}/updateDefinition", {"definition": {"parts": pl}})); print("updated", rid)
    else:
        lro(call("POST", f"/workspaces/{ws}/reports", {"displayName": REPORT, "definition": {"parts": pl}}))
        print("created", item_id(ws, REPORT, "Report"))

if __name__ == "__main__":
    write_local()
    if len(sys.argv) > 2 and sys.argv[1] == "deploy":
        deploy(sys.argv[2])
