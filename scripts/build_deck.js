// Build the v2 technical deep-dive deck (pptxgenjs). Numbers come from docs/findings_numbers.json.
// node build_deck.js <out.pptx> <assets_dir>
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const R = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/findings_numbers.json")));
const OUT = process.argv[2] || "DairyCo_v2_Technical_Deep_Dive.pptx";
const ASSETS = process.argv[3] || ".";
const IMG = path.join(ROOT, "docs/img");

const C = { ink: "05051E", ink2: "1A2229", blue: "0044FF", gold: "F6C42D", grey: "888888", grey2: "666666",
            panel: "F8F9FA", line: "E3E6EA", white: "FFFFFF", red: "C0392B", green: "1E8449", navy: "031042", ice: "A0B3DB" };
const F = "Montserrat";
const k = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2) + "M" : Math.round(v / 1e3) + "k");
const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Amr Dawoud";
pres.title = "DairyCo — How the answers were built (technical deep-dive)";

// ---------------------------------------------------------------- helpers
function label(s, t, dark = false) {
  s.addText(t.toUpperCase(), { x: 0.5, y: 0.35, w: 7.5, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3,
    color: dark ? C.ice : C.blue, margin: 0, isTextBox: true });
}
function title(s, t, opts = {}) {
  s.addText(t, { x: 0.5, y: 0.65, w: opts.w || 9, h: opts.h || 0.75, fontFace: F, fontSize: opts.size || 22, bold: true,
    color: opts.color || C.ink, margin: 0, valign: "top", isTextBox: true });
}
function brand(s, dark = false) {
  s.addText("TALIN", { x: 8.9, y: 0.35, w: 0.6, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3,
    color: dark ? C.white : C.grey, align: "right", margin: 0, isTextBox: true });
}
function footer(s, n) {
  s.addText(`DairyCo · Technical deep-dive · ${n}`, { x: 0.5, y: 5.3, w: 6, h: 0.2, fontFace: F, fontSize: 7, color: C.grey, margin: 0, isTextBox: true });
}
function panel(s, x, y, w, h, fill = C.panel) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08 });
}
function text(s, t, x, y, w, h, o = {}) {
  s.addText(t, Object.assign({ x, y, w, h, fontFace: F, fontSize: 10, color: C.ink2, margin: 0, valign: "top", isTextBox: true }, o));
}
function bullets(s, items, x, y, w, h, o = {}) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 12 }, breakLine: i < items.length - 1 } })),
    Object.assign({ x, y, w, h, fontFace: F, fontSize: 10, color: C.ink2, margin: 0, valign: "top", paraSpaceAfter: 5, isTextBox: true }, o));
}
function stat(s, value, lab, x, y, w, color = C.blue, size = 30) {
  text(s, value, x, y, w, 0.55, { fontSize: size, bold: true, color });
  text(s, lab, x, y + size * 0.019 + 0.05, w, 0.45, { fontSize: 8.5, color: C.grey2 });
}
function darkSlide() {
  const s = pres.addSlide();
  s.background = { path: path.join(ASSETS, "bg_dark.png") };
  return s;
}
function lightSlide() { const s = pres.addSlide(); s.background = { color: C.white }; return s; }
function table(s, rows, x, y, w, colW, o = {}) {
  const head = rows[0].map((h) => ({ text: h, options: { bold: true, color: C.white, fill: { color: C.navy }, fontSize: o.hs || 8 } }));
  const body = rows.slice(1).map((r, i) => r.map((c) => (typeof c === "object" ? c :
    { text: String(c), options: { fill: { color: i % 2 ? C.white : C.panel }, fontSize: o.fs || 8 } })));
  s.addTable([head, ...body], { x, y, w, colW, fontFace: F, color: C.ink2, border: { type: "solid", pt: 0.5, color: C.line },
    margin: 0.04, valign: "middle", rowH: o.rowH || 0.24, autoPage: false });
}
const chartBase = { catAxisLabelColor: C.grey2, valAxisLabelColor: C.grey2, catAxisLabelFontFace: F, valAxisLabelFontFace: F,
  catAxisLabelFontSize: 8, valAxisLabelFontSize: 8, valGridLine: { color: "EEEEEE", size: 0.5 }, catGridLine: { style: "none" },
  legendFontFace: F, legendFontSize: 8, titleFontFace: F, titleFontSize: 10, titleColor: C.ink, showTitle: true,
  dataLabelFontFace: F, dataLabelFontSize: 8 };
function shot(s, file, x, y, w, h) {
  s.addImage({ path: path.join(IMG, file), x, y, w, h });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.white, transparency: 100 }, line: { color: C.line, width: 0.75 } });
}
function placeholder(s, x, y, w, h, cap) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: C.panel }, line: { color: C.ice, width: 1, dashType: "dash" }, rectRadius: 0.06 });
  text(s, "SCREENSHOT", x + 0.15, y + h / 2 - 0.3, w - 0.3, 0.25, { fontSize: 8, bold: true, charSpacing: 3, color: C.blue, align: "center" });
  text(s, cap, x + 0.15, y + h / 2 - 0.02, w - 0.3, 0.5, { fontSize: 8.5, color: C.grey2, align: "center" });
}
let n = 0;
const next = () => ++n;

const H = R.headline, MB = R.margin_bridge, L1 = R.leak1_standard_cost, L2 = R.leak2_plant, L3 = R.leak3_channel,
      L4 = R.leak4_inventory, L5 = R.leak5_promo, ML = R.ml;

// ================================================================ 1 Title
{ const s = darkSlide(); next();
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 1.4, w: 0.5, h: 0, line: { color: C.gold, width: 2 } });
  s.addText("DAIRYCO STRATEGY REVIEW · PART 2", { x: 0.5, y: 0.5, w: 6, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3, color: C.ice, margin: 0, isTextBox: true });
  brand(s, true);
  s.addText("How the Answers Were Built", { x: 0.5, y: 1.6, w: 8.5, h: 1.0, fontFace: F, fontSize: 36, bold: true, color: C.white, margin: 0, isTextBox: true });
  s.addText("Technical deep-dive: data investigation, Microsoft Fabric architecture, semantic model, AI and the path to production",
    { x: 0.5, y: 2.7, w: 7.8, h: 0.7, fontFace: F, fontSize: 13, color: C.ice, margin: 0, isTextBox: true });
  s.addText("Amr Dawoud", { x: 0.5, y: 4.6, w: 5, h: 0.25, fontFace: F, fontSize: 11, bold: true, color: C.white, margin: 0, isTextBox: true });
  s.addText("BI Consultant & AI Engineer", { x: 0.5, y: 4.85, w: 5, h: 0.25, fontFace: F, fontSize: 9, color: C.ice, margin: 0, isTextBox: true });
  s.addNotes("Part 2 of the DairyCo review. The first session covered the five profit leaks. This pack shows the work behind them: how the data was investigated, how the platform is built in Microsoft Fabric, how every KPI is governed, and what it takes to run this in production.");
}

// ================================================================ 2 What this pack adds
{ const s = lightSlide(); next(); label(s, "What this pack adds"); brand(s);
  title(s, "The first session answered 'what'. This one shows the evidence and the platform behind it.");
  const cols = [
    ["01 · Evidence", ["EDA of all 22 source files before modelling", "17 data-quality rules, all logged, none silently fixed", "Every figure recomputed from the governed gold layer (one script, one JSON)"]],
    ["02 · Platform (live in Fabric)", ["Bronze → Silver → Gold lakehouses, metadata-driven", "Incremental MERGE proven on an August data drop", "Direct Lake model: 23 tables, 95 measures, RLS + OLS", "3-page management report on the model"]],
    ["03 · Operate & extend", ["Dev → Prod deployment pipeline, code in Git", "Payroll protected in three layers", "Forecasting prototype tracked in MLflow", "Conversational analytics design and governance"]]];
  cols.forEach(([h, items], i) => { const x = 0.5 + i * 3.05; panel(s, x, 1.75, 2.85, 2.85);
    text(s, h, x + 0.2, 1.95, 2.5, 0.3, { fontSize: 11, bold: true, color: C.blue });
    bullets(s, items, x + 0.2, 2.35, 2.5, 2.1, { fontSize: 9.5 }); });
  const nums = [["22", "source entities"], ["75,354", "invoice lines"], ["17", "DQ rules"], ["95", "governed measures"], ["2", "workspaces (Dev / Prod)"]];
  nums.forEach(([v, l], i) => { stat(s, v, l, 0.5 + i * 1.85, 4.68, 1.7, C.ink, 18); });
  footer(s, n);
}

// ================================================================ 3 Headline recomputed + margin bridge
{ const s = lightSlide(); next(); label(s, "The headline, recomputed from the governed model"); brand(s);
  title(s, "Revenue +7.6%, gross profit −5.4%. Mix and one stale cost explain the whole margin drop.", { w: 9 });
  stat(s, "+" + pct(H.rev_growth), "Net revenue, Jan–Aug 2026 vs 2025 (like-for-like)", 0.5, 1.65, 2.1);
  stat(s, pct(H.gp_growth), "Gross profit, same period", 0.5, 2.7, 2.1, C.red);
  stat(s, pct(H.gm_2025) + " → " + pct(H.gm_2026), "Gross margin: a clean step in Jan 2026, flat within each year", 0.5, 3.75, 2.4, C.ink, 20);
  const labels = ["GM 2025", "Mix: Milk share " + pct(MB.milk_share_2025, 0) + "→" + pct(MB.milk_share_2026, 0), "Milk cost +6% vs standard", "GM 2026"];
  const base = [0, MB.after_mix, MB.after_cost, 0].map((v) => +(v * 100).toFixed(2));
  const vis = [MB.gm_2025, -MB.mix_pp, -MB.cost_pp, H.gm_2026].map((v) => +(v * 100).toFixed(2));
  s.addChart(pres.charts.BAR, [{ name: "base", labels, values: base }, { name: "value", labels, values: vis }],
    Object.assign({}, chartBase, { x: 3.2, y: 1.55, w: 6.3, h: 3.55, barDir: "col", barGrouping: "stacked", chartColors: [C.white, C.blue],
      showLegend: false, valAxisMinVal: 20, valAxisMaxVal: 30, showValue: false, title: "Gross margin bridge (percentage points)",
      valAxisLabelFormatCode: "0\"%\"" }));
  text(s, `−${(-MB.mix_pp * 100).toFixed(2)} pp`, 5.0, 2.05, 1.2, 0.25, { fontSize: 9, bold: true, color: C.red, align: "center" });
  text(s, `−${(-MB.cost_pp * 100).toFixed(2)} pp`, 6.45, 2.45, 1.2, 0.25, { fontSize: 9, bold: true, color: C.red, align: "center" });
  footer(s, n);
  s.addNotes(`Mix effect = 2026 category mix priced at 2025 category margins (${pct(MB.gm_2025, 2)} -> ${pct(MB.after_mix, 2)}). Cost effect = actual vs standard COGS on Milk SKUs 1001-1005 (${pct(MB.after_mix, 2)} -> ${pct(MB.after_cost, 2)}). Nothing else moved: category margins outside Milk are unchanged.`);
}

// ================================================================ 4 Hypotheses -> verdicts
{ const s = lightSlide(); next(); label(s, "Approach: hypotheses first, then evidence"); brand(s);
  title(s, "Eight hypotheses, each tied to a management decision and tested against the data");
  const V = (t, c) => ({ text: t, options: { bold: true, color: c, fill: { color: C.white }, fontSize: 8 } });
  table(s, [["#", "Hypothesis", "Test (data)", "Verdict"],
    ["H1", "Margin is falling because of mix and cost, not price", "GM bridge by category; COGS vs Qty × standard cost", V("Confirmed", C.green)],
    ["H2", "ERP standard costs are out of date", "COGS / standard ratio by SKU and month", V("Confirmed: 1.06× on 5 Milk SKUs", C.green)],
    ["H3", "Some sell-in is channel loading, not demand", "ERP sell-in vs distributor sell-out and stock", V("Confirmed: Nile (301) only", C.green)],
    ["H4", "Promotions buy volume, not profit", "Uplift vs 8-week baseline; incremental GP vs support", V("Confirmed: 0 of 37 pay back", C.green)],
    ["H5", "Stock-outs and ageing stock share one root cause", "Forecast bias by category; plan vs forecast; cover", V("Confirmed: biased forecast copied into plan", C.green)],
    ["H6", "Plan attainment hides a quality gap", "Actual vs good output; scrap by plant × shift", V("Confirmed: Plant 2 and Shift C", C.green)],
    ["H7", "Rising overtime is driving cost", "OT trend; OT vs scrap by cell", V("Partly: structural, not rising", "B9770E")],
    ["H8", "Conflicting KPIs come from data definitions", "Same KPI across sources; DQ rules", V("Confirmed: 17 rules, 36.6k rows", C.green)]],
    0.5, 1.5, 9, [0.4, 3.1, 3.2, 2.3], { rowH: 0.36, fs: 8 });
  footer(s, n);
}

// ================================================================ 5 Data landscape
{ const s = lightSlide(); next(); label(s, "Exploratory data analysis"); brand(s);
  title(s, "Five systems, mixed grains, one 20-month window: only Jan–Aug is like-for-like");
  const src = [["ERP + WMS", "9 CSV extracts", "75,354 invoice lines · 1,659 returns · 12,503 weekly batch snapshots · targets", "Net = gross − discount on 100% of lines"],
               ["Salesforce CRM", "3 API-style extracts", "180 accounts · 780 opportunities · 3,234 activities", "Modern Trade & Key Accounts only (24% of revenue)"],
               ["Distributor platform", "2 JSONL feeds + CSV", "11,605 outlet sell-out rows · 2,880 stock rows · 540 outlets", "Receipts = ERP sell-in exactly"],
               ["Production + MRP", "4 CSV extracts", "960 orders (month × plant × line × shift × SKU) · forecast · downtime · MRP", "Actual = good + scrap on 100%"],
               ["HR + Payroll", "3 CSV extracts", "342 employees · 6,840 payroll and attendance rows", "Sensitive: aggregate before publishing"]];
  src.forEach(([a, b, c, d], i) => { const y = 1.55 + i * 0.72; panel(s, 0.5, y, 9, 0.62);
    text(s, a, 0.7, y + 0.1, 1.9, 0.25, { fontSize: 10, bold: true, color: C.blue }); text(s, b, 0.7, y + 0.35, 1.9, 0.2, { fontSize: 8, color: C.grey2 });
    text(s, c, 2.65, y + 0.12, 4.2, 0.45, { fontSize: 8.5 }); text(s, d, 7.0, y + 0.12, 2.35, 0.45, { fontSize: 8.5, italic: true, color: C.grey2 }); });
  footer(s, n);
  s.addNotes("Key patterns: seasonality peaks Mar-May, trough in September; five Milk SKUs double from Jan 2026 while all others fall 18-27%; Nile's sell-out drops about 30% from Jan 2026; Promo 9999 is the only deep discount. Cross-source scale differs (targets 24x revenue, payroll ~4.5x monthly revenue, warehouse stock 80-130 days of cover), so those sources are used for relative comparison only.");
}

// ================================================================ 6 Data quality
{ const s = lightSlide(); next(); label(s, "Data quality: flag, don't silently fix"); brand(s);
  title(s, "17 rules run on every load. Anomalies are mapped and logged; only value-breaking rules stop the pipeline.", { size: 20 });
  const dq = R.dq.filter((d) => d.violations > 0).sort((a, b) => b.violations - a.violations).slice(0, 10);
  table(s, [["Rule", "Issue", "Rows", "Severity"], ...dq.map((d) => [d.rule_id, d.rule, d.violations.toLocaleString("en-US"), d.severity])],
    0.5, 1.6, 5.9, [0.7, 3.8, 0.7, 0.7], { rowH: 0.3, fs: 7.5 });
  panel(s, 6.65, 1.6, 2.85, 3.35);
  text(s, "How issues are treated", 6.85, 1.75, 2.5, 0.3, { fontSize: 10, bold: true, color: C.blue });
  bullets(s, ["Duplicate customers → mapped to a master; both IDs kept (728 → 720)", "Region labels → customer-master region; raw label kept for audit",
    "CRM float/blank IDs → cast + name match (100% linked)", "UNKNOWN distributor SKUs → recovered from suffix, flagged",
    "Hard gate: net ≠ gross − discount, actual ≠ good + scrap → gold is not refreshed"], 6.85, 2.1, 2.5, 2.8, { fontSize: 8.5 });
  footer(s, n);
}

// ================================================================ 7 Divider
{ const s = darkSlide(); next(); brand(s, true);
  s.addText("THE PLATFORM", { x: 0.5, y: 0.5, w: 6, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3, color: C.ice, margin: 0, isTextBox: true });
  s.addText("One governed path from raw files to every number management sees", { x: 0.5, y: 1.9, w: 8, h: 1.2, fontFace: F, fontSize: 28, bold: true, color: C.white, margin: 0, isTextBox: true });
  s.addText("Built and running in Microsoft Fabric: workspaces DairyCo_v2_Dev and DairyCo_v2_Prod", { x: 0.5, y: 3.3, w: 8, h: 0.4, fontFace: F, fontSize: 12, color: C.ice, margin: 0, isTextBox: true });
}

// ================================================================ 8 Architecture diagram
{ const s = lightSlide(); next(); label(s, "Fabric architecture"); brand(s);
  title(s, "Medallion lakehouse → Direct Lake semantic model → report, AI and Copilot", { size: 20 });
  const box = (x, y, w, h, head, sub, fill, fc = C.white) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.06 });
    text(s, head, x + 0.08, y + 0.08, w - 0.16, 0.25, { fontSize: 9, bold: true, color: fc });
    text(s, sub, x + 0.08, y + 0.33, w - 0.16, h - 0.38, { fontSize: 7, color: fc }); };
  const arrow = (x1, y1, x2, y2) => s.addShape(pres.shapes.LINE, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color: C.grey, width: 1.25, endArrowType: "triangle" } });
  // sources
  ["ERP + WMS (CSV)", "Salesforce (API)", "Distributor (JSONL)", "Production + MRP", "HR + Payroll"].forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.55 + i * 0.52, w: 1.35, h: 0.42, fill: { color: C.panel }, line: { color: C.line }, rectRadius: 0.05 });
    text(s, t, 0.55, 1.62 + i * 0.52, 1.25, 0.3, { fontSize: 7.5, bold: true, align: "center" }); });
  arrow(1.9, 2.6, 2.1, 2.6);
  box(2.1, 1.55, 1.45, 2.5, "Landing + Bronze", "lh_bronze\nFiles/landing/<source>/load_date=…\nConfig-driven ingest of 22 entities\nSchema-on-read, audit columns\nAppend-only, _ingestion_log", "2D4A8A");
  arrow(3.6, 2.8, 3.8, 2.8);
  box(3.8, 1.55, 1.45, 2.5, "Silver", "lh_silver\nTyped, conformed, de-duplicated\nSales: watermark + MERGE\n17 DQ rules → dq_issues\nHard gate on bad values\nPayroll stays here (restricted)", "1F3D7A");
  arrow(5.3, 2.8, 5.5, 2.8);
  box(5.5, 1.55, 1.45, 2.5, "Gold", "lh_gold\nStar schema: 9 dims, 11 facts\nPromo attribution\nLabour aggregated (≥5/cell)\nML outputs\nV-Order for Direct Lake", C.navy);
  arrow(7.0, 2.8, 7.2, 2.8);
  box(7.2, 1.55, 2.3, 1.15, "Semantic model (Direct Lake)", "DairyCo Analytics · 95 measures · time intelligence · dynamic RLS + OLS · TMDL in Git", C.blue);
  box(7.2, 2.8, 1.1, 1.25, "Report", "3 pages: Executive, Commercial, Operations", "2E6BFF");
  box(8.4, 2.8, 1.1, 1.25, "AI", "MLflow forecast · data agent (design)", "2E6BFF");
  // orchestration + ALM band
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.1, y: 4.2, w: 4.85, h: 0.45, fill: { color: "FFF7DC" }, line: { color: C.gold }, rectRadius: 0.05 });
  text(s, "pl_dairyco_daily: bronze → silver (DQ gate) → gold → ML · batch_id = pipeline RunId · 2 retries per step", 2.2, 4.27, 4.7, 0.35, { fontSize: 7.5, bold: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.2, y: 4.2, w: 2.3, h: 0.45, fill: { color: "FFF7DC" }, line: { color: C.gold }, rectRadius: 0.05 });
  text(s, "Git + deployment pipeline: Dev → Prod", 7.3, 4.27, 2.1, 0.35, { fontSize: 7.5, bold: true });
  text(s, "Security: business users only reach the semantic model. Bronze and silver are engineering-only; employee-level pay never reaches gold.", 0.5, 4.85, 9, 0.3, { fontSize: 8, italic: true, color: C.grey2 });
  footer(s, n);
}

// ================================================================ 9 Decisions & alternatives
{ const s = lightSlide(); next(); label(s, "Key technical decisions"); brand(s);
  title(s, "Each choice has a credible alternative, and a reason it wasn't chosen here");
  table(s, [["Decision", "Chosen", "Alternative", "Why"],
    ["Engine", "Lakehouse + PySpark", "Fabric Warehouse (T-SQL)", "JSONL feeds, regex SKU mapping, MERGE and DQ logging in one engine; gold can move to a Warehouse for a SQL-first team"],
    ["Layers", "3 lakehouses", "1 lakehouse, 3 schemas", "Each lakehouse is a permission boundary: raw payroll never shares a surface with business users"],
    ["Ingestion", "Config-driven notebook", "One Copy activity per file", "New source = one JSON line; the same contract works later with Mirroring or Copy jobs"],
    ["Incremental", "Watermark + Delta MERGE", "Full reload / CDC", "Sales is the only high-volume entity; MERGE absorbs late corrections; masters are small"],
    ["Model mode", "Direct Lake", "Import / DirectQuery", "No refresh schedule or data copy; Import only if calculated columns or non-Fabric sources dominate"],
    ["Model as code", "TMDL generated + REST", "Hand-built in Desktop", "Every object documented (feeds Copilot), diff-able in Git, deployable to any stage"],
    ["Security", "Dynamic RLS + OLS + aggregation", "Static role per region", "One role for all regions via a mapping table; payroll protected in three layers"],
    ["Capacity", "F2 for build", "F64", "11 MB of data runs on F2; F64 for production (Copilot, free viewers, headroom)"]],
    0.5, 1.5, 9, [1.1, 1.6, 1.6, 4.7], { rowH: 0.38, fs: 7.5 });
  footer(s, n);
}

// ================================================================ 10 Ingestion + incremental
{ const s = lightSlide(); next(); label(s, "Ingestion and incremental processing"); brand(s);
  title(s, "Adding a source is one line of config. Adding a month is a MERGE, not a reload.");
  panel(s, 0.5, 1.55, 4.3, 3.45, "0B1530");
  text(s, '{ "source": "erp",\n  "file": "Sales.csv",\n  "format": "csv",\n  "bronze_table": "erp_sales",\n  "load_type": "incremental",\n  "business_key": ["InvoiceID"],\n  "sensitivity": "internal",\n  "owner": "Finance/Commercial IT" }',
    0.7, 1.7, 3.9, 2.2, { fontFace: "Courier New", fontSize: 9, color: "D6E4FF" });
  text(s, "config/ingestion_config.json: 22 entities. Bronze scans landing/<source>/load_date=…/, skips files already in _ingestion_log (idempotent) and logs a bad file without stopping the others.",
    0.7, 3.95, 3.9, 0.9, { fontSize: 8.5, color: C.ice });
  const steps = [["71,631", "invoice lines in the initial load (to 31 Jul 2026)"], ["+3,723", "August lines dropped as load_date=2026-09-01"],
                 ["75,354", "rows after MERGE on InvoiceID, 2 batches, watermark advanced"], ["0", "rows changed when the pipeline re-ran with no new file"]];
  steps.forEach(([v, l], i) => { const y = 1.55 + i * 0.86; panel(s, 5.05, y, 4.45, 0.76);
    text(s, v, 5.25, y + 0.12, 1.4, 0.5, { fontSize: 20, bold: true, color: i === 2 ? C.green : C.blue });
    text(s, l, 6.7, y + 0.16, 2.7, 0.5, { fontSize: 9 }); });
  footer(s, n);
}

// ================================================================ 11 Star schema
{ const s = lightSlide(); next(); label(s, "Analytics-ready model"); brand(s);
  title(s, "A star schema with conformed dimensions, so every fact slices the same way");
  const dims = [["Date", 0.5, 1.5], ["Product", 0.5, 2.38], ["Region (RLS)", 0.5, 3.26], ["Customer", 0.5, 4.14],
                ["Distributor", 8.1, 1.5], ["Warehouse", 8.1, 2.38], ["Promotion", 8.1, 3.26], ["Production Unit", 8.1, 4.14]];
  dims.forEach(([t, x, y]) => { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.4, h: 0.55, fill: { color: C.blue }, line: { color: C.blue }, rectRadius: 0.06 });
    text(s, t, x, y + 0.16, 1.4, 0.25, { fontSize: 8.5, bold: true, color: C.white, align: "center" }); });
  const facts = [["Sales", "invoice line"], ["Returns", "return line"], ["Sales Target", "month × region × category"], ["Promotion Performance", "promotion"],
                 ["Inventory Snapshot", "week × DC × SKU"], ["Distributor Month", "month × distributor × SKU"], ["Demand Forecast", "month × SKU"],
                 ["Production", "production order"], ["Labour", "month × plant × line × shift"], ["CRM Opportunity / Activity", "record"], ["ML Forecast / Rebalancing", "SKU × month / DC × SKU"]];
  facts.forEach(([t, g], i) => { const col = i % 2, row = Math.floor(i / 2); const x = 2.25 + col * 2.8, y = 1.5 + row * 0.56;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.65, h: 0.48, fill: { color: C.panel }, line: { color: C.line }, rectRadius: 0.05 });
    text(s, t, x + 0.1, y + 0.05, 2.45, 0.22, { fontSize: 8.5, bold: true, color: C.navy }); text(s, "grain: " + g, x + 0.1, y + 0.27, 2.45, 0.2, { fontSize: 7, color: C.grey2 }); });
  text(s, "Integer keys · month facts join on the first day of the month, so one Date dimension serves all · Region names denormalised onto Customer / Distributor / Warehouse to avoid ambiguous paths · category targets linked virtually (TREATAS)",
    0.5, 4.9, 9, 0.3, { fontSize: 7.5, italic: true, color: C.grey2 });
  footer(s, n);
}

// ================================================================ 12 Semantic model & KPIs
{ const s = lightSlide(); next(); label(s, "Semantic model and mandatory KPIs"); brand(s);
  title(s, "One definition per KPI, and unreliable ones say so instead of inventing a number", { size: 20 });
  const G = (t) => ({ text: t, options: { bold: true, color: C.green, fontSize: 7.5 } }), A = (t) => ({ text: t, options: { bold: true, color: "B9770E", fontSize: 7.5 } }), Rr = (t) => ({ text: t, options: { bold: true, color: C.red, fontSize: 7.5 } });
  table(s, [["KPI (measure)", "Definition", "Status"],
    ["Net Revenue", "Invoiced net sales (after on-invoice discount), before returns", G("Reliable")],
    ["Sales Volume", "Units invoiced (packs)", G("Reliable")],
    ["Gross Profit / Gross Margin %", "Net revenue − actual COGS; ÷ net revenue", G("Reliable")],
    ["Revenue Growth %", "Like-for-like: same dates last year, actuals only (Jan–Aug)", A("YTD only: 20 months of data")],
    ["Target Attainment %", "Net revenue ÷ target (category via TREATAS)", Rr("Targets ≈24× actuals: use Index")],
    ["Return Rate %", "Return value ÷ net revenue, by return date", G("Reliable (definition stated)")],
    ["Inventory", "Latest weekly snapshot, semi-additive, at standard cost", A("Scale caveat")],
    ["Stockout Proxy %", "Share of DC × SKU × weeks with zero available stock", Rr("Proxy: no order/backorder data")],
    ["Production Plan Attainment %", "Actual ÷ planned, shown next to good ÷ planned", G("Reliable (both views)")]],
    0.5, 1.5, 6.2, [1.7, 3.1, 1.4], { rowH: 0.33, fs: 7.5 });
  panel(s, 6.95, 1.5, 2.55, 3.35);
  text(s, "Like-for-like growth (DAX)", 7.1, 1.62, 2.3, 0.25, { fontSize: 9, bold: true, color: C.blue });
  text(s, "VAR _dates =\n  CALCULATETABLE(\n    VALUES('Date'[Date]),\n    'Date'[Is Actuals Period] = TRUE())\nRETURN\n  CALCULATE([Net Revenue],\n    DATEADD(_dates, -1, YEAR))",
    7.1, 1.92, 2.3, 1.6, { fontFace: "Courier New", fontSize: 7.5, color: C.ink });
  text(s, "Without this, Sep–Dec 2025 would be compared with empty 2026 months. Every measure carries a description, which a Copilot or data agent reads when answering.", 7.1, 3.55, 2.3, 1.2, { fontSize: 7.5, color: C.grey2 });
  footer(s, n);
}

// ================================================================ 13 Security
{ const s = lightSlide(); next(); label(s, "Security and sensitive data"); brand(s);
  title(s, "Payroll is protected in three layers; regional managers see only their regions");
  const layers = [["1 · Minimise", "Employee-level pay never leaves lh_silver. Gold holds plant × line × shift × month totals; the build fails if any cell has fewer than 5 people."],
                  ["2 · Isolate", "Bronze and silver are engineering-only. Business users get Read/Build on the semantic model, never lakehouse or SQL endpoint access."],
                  ["3 · Secure the model", "Regional Manager role: dynamic RLS (Region ∈ regions mapped to USERPRINCIPALNAME()), plus OLS hiding labour-cost columns. Executive role: no filter."]];
  layers.forEach(([h, b], i) => { const y = 1.55 + i * 1.12; panel(s, 0.5, y, 5.4, 1.0);
    text(s, h, 0.7, y + 0.12, 5, 0.25, { fontSize: 10.5, bold: true, color: C.blue }); text(s, b, 0.7, y + 0.42, 5.0, 0.55, { fontSize: 8.5 }); });
  panel(s, 6.15, 1.55, 3.35, 3.25, "0B1530");
  text(s, "roles/Regional Manager.tmdl", 6.3, 1.68, 3.1, 0.25, { fontSize: 8, bold: true, color: C.gold });
  text(s, "tablePermission Region =\n  'Region'[Region Key] IN\n  CALCULATETABLE(\n    VALUES('Security User\n      Region'[Region Key]),\n    'Security User Region'\n      [User UPN] =\n      USERPRINCIPALNAME())\n\ntablePermission Labour\n  columnPermission\n    'Total Labour Cost' = none",
    6.3, 1.98, 3.1, 2.8, { fontFace: "Courier New", fontSize: 7.5, color: "D6E4FF" });
  footer(s, n);
}

// ================================================================ 14 Report page 1
{ const s = lightSlide(); next(); label(s, "Management report · page 1 of 3"); brand(s);
  title(s, "Executive Performance: headline, margin break and five leaks", { size: 18, h: 0.4 });
  shot(s, "report_page-1.png", 1.5, 1.15, 7.0, 7.0 * 1817 / 3200);
  footer(s, n);
}
// ================================================================ 15 Report pages 2-3
{ const s = lightSlide(); next(); label(s, "Management report · pages 2 and 3"); brand(s);
  title(s, "Commercial and Operations pages drill from the headline to the cause", { size: 18 });
  shot(s, "report_page-2.png", 0.5, 1.45, 4.4, 4.4 * 1817 / 3200); shot(s, "report_page-3.png", 5.1, 1.45, 4.4, 4.4 * 1817 / 3200);
  text(s, "Commercial: SKU growth, distributor scorecard (sell-out, cover, excess stock), sell-in vs sell-out, promotion ROI", 0.5, 4.05, 4.4, 0.5, { fontSize: 8, color: C.grey2 });
  text(s, "Operations: plant × shift scrap/OT/absence, forecast bias, cover, downtime, AI backtest, live data-quality log", 5.1, 4.05, 4.4, 0.5, { fontSize: 8, color: C.grey2 });
  footer(s, n);
}
// ================================================================ 16 Inside Fabric (screenshot slots)
{ const s = lightSlide(); next(); label(s, "Inside the Fabric workspace"); brand(s);
  title(s, "What is running today in DairyCo_v2_Dev and DairyCo_v2_Prod", { size: 18 });
  placeholder(s, 0.5, 1.4, 4.4, 1.75, "Workspace lineage view: landing → lh_bronze → lh_silver → lh_gold → DairyCo Analytics → DairyCo Management");
  placeholder(s, 5.1, 1.4, 4.4, 1.75, "pl_dairyco_daily run: four green activities with durations");
  placeholder(s, 0.5, 3.3, 4.4, 1.75, "Semantic model diagram view (star schema) or TMDL view");
  placeholder(s, 5.1, 3.3, 4.4, 1.75, "Deployment pipeline Dev → Prod, or the MLflow experiment run comparison");
  footer(s, n);
}

// ================================================================ 17 Divider leaks
{ const s = darkSlide(); next(); brand(s, true);
  s.addText("THE FIVE LEAKS · EVIDENCE", { x: 0.5, y: 0.5, w: 6, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3, color: C.ice, margin: 0, isTextBox: true });
  s.addText("Same story as the first session, now traceable to a measure and a formula", { x: 0.5, y: 1.8, w: 8.5, h: 1.2, fontFace: F, fontSize: 28, bold: true, color: C.white, margin: 0, isTextBox: true });
  const rows = [["Leak", "v1", "v2 (recomputed)"], ["1 Stale standard cost", "157k", k(L1.cost_variance_2026)], ["2 Plant & shift scrap", "243k", k(L2.avoidable_scrap_cost_conservative) + " (stretch " + k(L2.avoidable_scrap_cost) + ")"],
    ["3 Channel stuffing (Nile)", "161.7k", k(L3.nile_excess_value)], ["4 Near-expiry stock", "540k", k(L4.near_expiry_last_snapshot) + " latest · " + k(L4.avg_near_expiry_total) + " avg"],
    ["5 Promotion spend", "1.86M, unmeasurable", k(L5.support_total) + ", measured: 0 pay back"]];
  s.addTable(rows.map((r, i) => r.map((c) => ({ text: c, options: { color: i ? C.white : C.gold, bold: i === 0, fontSize: 9, fill: { color: C.navy } } }))),
    { x: 0.5, y: 3.2, w: 8.5, colW: [2.8, 2.2, 3.5], fontFace: F, border: { type: "solid", pt: 0.5, color: "22306B" }, rowH: 0.3, margin: 0.05 });
}

// ---- leak slide helper
function leak(num, lab, head, big, bigLab, method, action, measure) {
  const s = lightSlide(); next(); label(s, `Leak 0${num} — ${lab}`); brand(s);
  title(s, head, { w: 9, size: 19 });
  text(s, big, 0.5, 1.5, 3.8, 0.7, { fontSize: 36, bold: true, color: C.red });
  text(s, bigLab, 0.5, 2.2, 3.8, 0.45, { fontSize: 9, color: C.grey2 });
  panel(s, 0.5, 2.75, 3.8, 1.25);
  text(s, "HOW IT IS MEASURED", 0.65, 2.85, 3.5, 0.2, { fontSize: 7.5, bold: true, charSpacing: 2, color: C.blue });
  text(s, method, 0.65, 3.08, 3.5, 0.9, { fontSize: 8.5 });
  panel(s, 0.5, 4.1, 3.8, 1.05, "EEF3FF");
  text(s, "ACTION → TRACK", 0.65, 4.2, 3.5, 0.2, { fontSize: 7.5, bold: true, charSpacing: 2, color: C.blue });
  text(s, action, 0.65, 4.42, 3.5, 0.7, { fontSize: 8.5 });
  text(s, "Measure: " + measure, 4.6, 5.05, 4.9, 0.2, { fontSize: 7.5, italic: true, color: C.grey2, align: "right" });
  footer(s, n);
  return s;
}

// ================================================================ 18 Leak 1
{ const cats = ["Milk", "Yogurt", "Juice", "Cheese"];
  const s = leak(1, "Standard costing", "Five Milk SKUs have cost exactly 6% more than the ERP standard since January 2026",
    k(L1.cost_variance_2026), "Actual COGS above standard, Jan–Aug 2026 (SKUs 1001–1005 at 1.06× standard; all others 1.00×)",
    "Cost Variance vs Standard = actual COGS − Qty × ERP standard cost, per invoice line. Milk margin: " + pct(L1.milk_gm_at_std_2026) + " at standard vs " + pct(L1.milk_gm_actual_2026) + " actual.",
    "Refresh Milk standard costs now; move to quarterly re-costing. Track: Cost Variance vs Standard → 0, and Gross Margin % vs at-standard gap.",
    "Cost Variance vs Standard · Gross Margin % at Standard Cost");
  s.addChart(pres.charts.BAR, [{ name: "GM 2025", labels: cats, values: cats.map((c) => +(MB.cat_gm_2025[c] * 100).toFixed(1)) },
                               { name: "GM 2026", labels: cats, values: cats.map((c) => +(MB.cat_gm_2026[c] * 100).toFixed(1)) }],
    Object.assign({}, chartBase, { x: 4.6, y: 1.45, w: 4.9, h: 3.5, barDir: "col", chartColors: [C.ice, C.blue], showLegend: true, legendPos: "b",
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", title: "Gross margin % by category: only Milk moved", valAxisMinVal: 0 }));
}
// ================================================================ 19 Leak 2
{ const rows = L2.by_plant_shift;
  const s = leak(2, "Plant attainment", "Plan attainment reads 99.8%, but Plant 2 and night shifts scrap 3–5× more",
    k(L2.avoidable_scrap_cost_conservative), `Avoidable scrap cost over 20 months if every order ran at the Plant 1 average scrap rate (${pct(L2.benchmark_plant1_avg, 2)}). Stretch target, Plant 1 day shifts (${pct(L2.benchmark_scrap, 2)}): ${k(L2.avoidable_scrap_cost)}`,
    `Good-output attainment is ${pct(L2.good_attainment)} vs ${pct(L2.plan_attainment)} on actual. Overtime per head and scrap move together across plant × shift cells (r = ${L2.corr_ot_scrap_cells.toFixed(2)}), but company overtime is flat year on year.`,
    "Standardise Plant 2 changeover and QA practice; rebalance Shift C staffing and loading. Track: Good Output Attainment %, Scrap Rate % by shift, Avoidable Scrap Cost.",
    "Avoidable Scrap Cost · Scrap Rate % · Good Output Attainment %");
  s.addChart(pres.charts.BAR, [{ name: "Scrap rate %", labels: rows.map((r) => r.plant.replace("Plant ", "P") + " " + r.shift.replace("Shift ", "")), values: rows.map((r) => +(r.scrap / r.act * 100).toFixed(2)) }],
    Object.assign({}, chartBase, { x: 4.6, y: 1.45, w: 4.9, h: 3.5, barDir: "col", chartColors: [C.blue], showLegend: false, showValue: true, dataLabelPosition: "outEnd",
      dataLabelFormatCode: "0.0", title: "Scrap rate % by plant × shift (20 months)", valAxisMinVal: 0 }));
}
// ================================================================ 20 Leak 3
{ const m = L3.nile_monthly; const lab = m.map((r) => r.year_month.slice(2));
  const s = leak(3, "Channel stuffing", "Nile Distribution's stock tripled while its consumer sell-out fell 29%",
    k(L3.nile_excess_value), "Nile stock above the 0.6-month cover every peer runs at, valued at DairyCo's sell-in price (Aug 2026)",
    "ERP shows Nile growing +5.2%. Distributor feed: sell-through fell to 58% (peers ≈ 88%); months of cover rose from 0.6 to 2.75. Stock above peer cover × sell-in unit price.",
    "Cap Nile allocation to sell-out + normal cover; move distributor targets to sell-out. Track: Sell-through %, Distributor Months of Cover, Excess Channel Stock Value.",
    "Sell-through % · Distributor Months of Cover · Excess Channel Stock Value");
  s.addChart(pres.charts.LINE, [{ name: "Sell-in", labels: lab, values: m.map((r) => r.sell_in) }, { name: "Sell-out", labels: lab, values: m.map((r) => r.sell_out) },
                                { name: "Stock", labels: lab, values: m.map((r) => r.stock) }],
    Object.assign({}, chartBase, { x: 4.6, y: 1.45, w: 4.9, h: 3.5, chartColors: [C.ice, C.blue, C.red], lineSize: 2, lineDataSymbol: "none", showLegend: true, legendPos: "b",
      title: "Nile Distribution: units per month (YY-MM)", catAxisLabelFontSize: 7 }));
}
// ================================================================ 21 Leak 4
{ const cats = ["Milk", "Yogurt", "Juice", "Cheese"]; const cv = (c, y) => L4.cover_days.find((r) => r.category === c && r.year === y);
  const fb = (c) => L4.forecast_bias.filter((r) => r.category === c).map((r) => r.bias);
  const s = leak(4, "Stock vs demand", "Stock was never re-allocated when demand moved: Milk runs lean while Yogurt ages",
    k(L4.near_expiry_last_snapshot), `Stock with ≤25% of shelf life left at the latest snapshot (${pct(L4.near_expiry_last_snapshot / L4.stock_value_last_snapshot, 0)} of stock value; ${k(L4.avg_near_expiry_total)} on an average week)`,
    `Warehouse stock sits at ~545 units per SKU per DC in both years. Root cause: the MRP forecast is biased (Yogurt +${pct(fb("Yogurt")[1], 0)}, Milk ${pct(fb("Milk")[1], 0)}) and the production plan copies it almost exactly.`,
    "Correct the forecast bias (next slides) and set cover targets by shelf life per DC. Track: Forecast Bias %, Near-Expiry Stock %, Stockout Proxy % (until order data exists).",
    "Near-Expiry Stock Value · Days of Cover · Forecast Bias %");
  s.addChart(pres.charts.BAR, [{ name: "Days of cover 2026", labels: cats, values: cats.map((c) => +cv(c, 2026).cover_days.toFixed(0)) },
                               { name: "Shelf life (days)", labels: cats, values: cats.map((c) => cv(c, 2026).shelf_life) }],
    Object.assign({}, chartBase, { x: 4.6, y: 1.45, w: 4.9, h: 3.5, barDir: "col", chartColors: [C.blue, C.gold], showLegend: true, legendPos: "b", showValue: true,
      dataLabelPosition: "outEnd", dataLabelFormatCode: "0", title: "Days of cover vs shelf life, 2026 (scale caveat: stock vs invoices)" }));
}
// ================================================================ 22 Leak 5
{ const p = L5.p9999[0];
  const s = leak(5, "Promotion effectiveness", "Promotions can be measured after all, and none of them pays back",
    k(L5.net_return), `Net return on ${k(L5.support_total)} of promotion support (${pct(L5.support_vs_gp_pct, 1)} of gross profit): incremental GP minus support cost, 61 promotions`,
    `Invoice lines linked to promotions by product + region + date; baseline = 8 prior weeks. ${L5.paying_back} of ${L5.measurable} measurable promotions pay back; average lift ${pct(L5.avg_lift, 0)}. Stated discount ${pct(L5.stated_discount_avg, 1)} vs ${pct(L5.applied_discount_avg, 1)} actually invoiced.`,
    "Pause untargeted trade discounts; fund only promotions with a test/control design and a PromotionID on the invoice. Track: Promotion ROI %, Promotions Paying Back.",
    "Net Promotion Return · Promotion ROI % · Average Volume Lift %");
  panel(s, 4.6, 1.5, 4.9, 3.4);
  text(s, "PRM-9999: the only deep discount", 4.8, 1.65, 4.5, 0.3, { fontSize: 11, bold: true, color: C.navy });
  const kv = [["25%", "discount, the only promotion whose discount reached the invoice"], [p.promo_units + " vs " + Math.round(p.baseline_units), "units sold vs baseline: 0% lift"],
              [k(p.support_cost), "support cost (other promotions: 15–45k)"], [k(p.net_promo_return), "net return after support"]];
  kv.forEach(([v, l], i) => { stat(s, v, l, 4.8 + (i % 2) * 2.35, 2.1 + Math.floor(i / 2) * 1.35, 2.2, i === 3 ? C.red : C.blue, 20); });
}

// ================================================================ 23 AI prototype
{ const s = lightSlide(); next(); label(s, "AI use case A · prototyped"); brand(s);
  title(s, "Correcting the forecast bias cuts error by ~40%, and a simple rule gets most of the way", { size: 19 });
  const cats = ["Yogurt", "Milk", "Cheese", "Juice"];
  s.addChart(pres.charts.BAR, [{ name: "MRP forecast (today)", labels: [...cats, "All SKUs"], values: [...cats.map((c) => +(ML.by_category[c].mrp * 100).toFixed(1)), +(ML.wape_mrp * 100).toFixed(1)] },
                               { name: "Rule: MRP × trailing actual/forecast", labels: [...cats, "All SKUs"], values: [...cats.map((c) => +(ML.by_category[c].rule * 100).toFixed(1)), +(ML.wape_rule * 100).toFixed(1)] },
                               { name: "ML correction model", labels: [...cats, "All SKUs"], values: [...cats.map((c) => +(ML.by_category[c].ml * 100).toFixed(1)), +(ML.wape_ml * 100).toFixed(1)] }],
    Object.assign({}, chartBase, { x: 0.5, y: 1.45, w: 5.4, h: 3.6, barDir: "col", chartColors: ["C9CED6", C.gold, C.blue], showLegend: true, legendPos: "b",
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", title: "Forecast error (WAPE %), 6-month rolling-origin backtest", valAxisMinVal: 0 }));
  panel(s, 6.15, 1.45, 3.35, 3.6);
  text(s, "What was built", 6.3, 1.57, 3.1, 0.25, { fontSize: 10, bold: true, color: C.blue });
  bullets(s, ["nb_05: gradient-boosted trees predicting the correction ratio actual ÷ MRP from the SKU's recent bias, momentum, season and category",
    "Rolling-origin backtest: each month predicted using only earlier data, against MRP, naive and a rule",
    "MLflow experiment + registered model; scores next month into gold every pipeline run",
    "Feeds a DC × SKU rebalancing table (target cover = 50% of shelf life)"], 6.3, 1.87, 3.1, 1.9, { fontSize: 8 });
  text(s, "Recommendation", 6.3, 3.8, 3.1, 0.25, { fontSize: 10, bold: true, color: C.blue });
  text(s, "Ship the rule now: explainable and free. Run ML as the challenger, and promote it once promotion calendar, weather/Ramadan and outlet sell-out are added.", 6.3, 4.08, 3.1, 0.95, { fontSize: 8 });
  footer(s, n);
}

// ================================================================ 24 AI B + conversational analytics
{ const s = lightSlide(); next(); label(s, "AI use case B and conversational analytics"); brand(s);
  title(s, "Use AI where rules stop working, and ground every answer in the governed model", { size: 19 });
  panel(s, 0.5, 1.5, 4.4, 3.55);
  text(s, "B · Distributor channel-risk score (designed)", 0.7, 1.62, 4.0, 0.3, { fontSize: 10, bold: true, color: C.blue });
  bullets(s, ["Problem: Nile loaded 3× stock while ERP showed it growing; by the time sell-in drops, revenue is already pulled forward",
    "Rule first (shipped): Sell-through < 85% or Cover > 1 month for 2 months → review",
    "AI adds: an anomaly score across cover trend, sell-through, outlet count, returns and mix drift, ranking emerging risk",
    "Data gap: only 6 distributors and no write-off history, so start unsupervised; add AR/payment data",
    "Embed: monthly score and drivers on the Commercial page, plus an Activator alert → logged action"], 0.7, 1.95, 4.0, 3.0, { fontSize: 8 });
  panel(s, 5.1, 1.5, 4.4, 3.55, "EEF3FF");
  text(s, "Conversational analytics (Fabric data agent)", 5.3, 1.62, 4.0, 0.3, { fontSize: 10, bold: true, color: C.blue });
  bullets(s, ["Grounded on the certified DairyCo Analytics model, not raw tables: answers use the same 95 measures as the dashboards",
    "Runs as the signed-in user: RLS and OLS apply, with no path to payroll",
    "Descriptions on every measure flag caveats (e.g. Stockout Proxy, Target Attainment), so the agent repeats them",
    "Verified answers for the top 20 executive questions; a 50-question test set gates every model change (≥95% correct)",
    "Shows the measure and filters used; refuses questions the data cannot answer and names the missing data"], 5.3, 1.95, 4.0, 3.0, { fontSize: 8 });
  footer(s, n);
}

// ================================================================ 25 Production readiness
{ const s = lightSlide(); next(); label(s, "Path to production"); brand(s);
  title(s, "What exists today, and what is needed before enterprise rollout", { size: 20 });
  table(s, [["Area", "Today (prototype)", "Before rollout"],
    ["Environments", "Dev + Prod workspaces, deployment pipeline (notebooks and pipeline auto-rebind)", "Dev / Test / Prod; Prod on F64; model data source rebound by deployment rule"],
    ["Source control", "Notebooks, pipeline, config, TMDL model, report, scripts in Git", "Workspace Git sync, PR review, feature workspaces"],
    ["Deployment", "Scripts deploy by name, resolving IDs per workspace", "GitHub Actions + fabric-cicd on merge to main"],
    ["Parameters", "Lakehouse names, pipeline params, batch_id = RunId", "Variable Library: thresholds (25% expiry, benchmarks)"],
    ["Monitoring", "Retries, per-file log, DQ hard gate before gold", "Activator/Teams alert on failure; Capacity Metrics; run-log report"],
    ["Data quality", "17 rules, current + history, on Operations page", "Owner and threshold per rule; schema-drift contract checks"],
    ["Lineage & catalogue", "Fabric lineage; every object described", "Endorse the model; Purview / OneLake catalog; KPI glossary"],
    ["Ownership", "Owner per source in ingestion config", "RACI: source owners fix DQ, BI team owns measures, KPI council signs off"]],
    0.5, 1.5, 9, [1.5, 3.75, 3.75], { rowH: 0.38, fs: 7.5 });
  footer(s, n);
}

// ================================================================ 26 Limitations / asks
{ const s = lightSlide(); next(); label(s, "Data gaps that need a business decision"); brand(s);
  title(s, "Four things only management can fix, and what each unlocks", { size: 20 });
  const asks = [["Restate the targets", "Targets are ~24× actual revenue at a fixed 35 EGP per unit. Unlocks: real Target Attainment %."],
                ["Capture order lines", "Requested vs delivered quantity, plus outlet out-of-stock checks. Unlocks: a true stockout and fill-rate KPI."],
                ["Distributor data contract", "Stock roll-forward must balance (it fails in 99% of rows). Unlocks: trusted channel-stock value."],
                ["Confirm source units", "Warehouse stock, payroll and CRM values are on different scales from invoices. Unlocks: cost-per-unit and cover in absolute terms."]];
  asks.forEach(([h, b], i) => { const x = 0.5 + (i % 2) * 4.6, y = 1.55 + Math.floor(i / 2) * 1.75; panel(s, x, y, 4.4, 1.55);
    text(s, String(i + 1).padStart(2, "0"), x + 0.2, y + 0.15, 0.6, 0.4, { fontSize: 18, bold: true, color: C.gold });
    text(s, h, x + 0.85, y + 0.2, 3.4, 0.3, { fontSize: 11, bold: true, color: C.navy }); text(s, b, x + 0.85, y + 0.55, 3.4, 0.9, { fontSize: 8.5 }); });
  footer(s, n);
}

// ================================================================ 27 Close
{ const s = darkSlide(); next(); brand(s, true);
  s.addText("NEXT 90 DAYS", { x: 0.5, y: 0.5, w: 6, h: 0.3, fontFace: F, fontSize: 9, bold: true, charSpacing: 3, color: C.ice, margin: 0, isTextBox: true });
  s.addText("Fix the leaks, measure them in the same model, then scale AI", { x: 0.5, y: 1.1, w: 8.5, h: 1.0, fontFace: F, fontSize: 26, bold: true, color: C.white, margin: 0, isTextBox: true });
  const steps = [["Weeks 1–4", "Re-cost Milk · cap Nile allocation · pause untargeted promotions · deploy the bias-corrected forecast rule"],
                 ["Weeks 5–8", "Plant 2 / Shift C standard work · DC cover targets by shelf life · order-line capture starts"],
                 ["Weeks 9–12", "Prod on F64 · CI/CD · data agent pilot with verified answers · ML forecast champion/challenger"]];
  steps.forEach(([h, b], i) => { const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.5, w: 2.85, h: 1.9, fill: { color: "0B1A55" }, line: { color: "22306B" }, rectRadius: 0.08 });
    s.addText(h, { x: x + 0.2, y: 2.65, w: 2.5, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: C.gold, margin: 0, isTextBox: true });
    s.addText(b, { x: x + 0.2, y: 3.0, w: 2.5, h: 1.3, fontFace: F, fontSize: 9, color: C.white, margin: 0, valign: "top", isTextBox: true }); });
  s.addText("Code and documentation: GitHub · amrbdawoud/dairyco-fabric-analytics", { x: 0.5, y: 4.75, w: 8.5, h: 0.3, fontFace: F, fontSize: 9, color: C.ice, margin: 0, isTextBox: true });
}

pres.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f, n, "slides"));
