"""Assemble docs/*.md into one styled PDF appendix (docs/DairyCo_Technical_Appendix.pdf)."""
import pathlib, markdown, weasyprint, datetime
ROOT = pathlib.Path(__file__).resolve().parents[1]; D = ROOT / "docs"
order = ["00_findings_and_recommendations.md", "01_architecture_and_decisions.md", "02_eda_and_data_quality.md",
         "06_semantic_model_reference.md", "03_security_and_production_readiness.md", "04_ai_and_advanced_analytics.md",
         "05_explainer_briefs_and_QA.md"]
body = ""
for f in order:
    html = markdown.markdown((D / f).read_text(), extensions=["tables", "fenced_code", "sane_lists"])
    body += f'<section>{html}</section>'
    if f.startswith("01"):
        body += '<section><h1>Management report (live in Fabric)</h1>' + "".join(
            f'<p class="cap">Page {i}</p><img src="img/report_page-{i}.png"/>' for i in (1, 2, 3)) + "</section>"
css = """
@page { size: A4 landscape; margin: 14mm 14mm 16mm 14mm;
        @bottom-left { content: "DairyCo · Technical appendix"; font: 7pt Montserrat; color: #888; }
        @bottom-right { content: counter(page); font: 7pt Montserrat; color: #888; } }
body { font-family: Montserrat, Arial, sans-serif; font-size: 8.6pt; color: #1A2229; line-height: 1.42; }
section { page-break-before: always; } section:first-of-type { page-break-before: auto; }
h1 { font-size: 18pt; color: #05051E; margin: 0 0 8pt; } h2 { font-size: 12.5pt; color: #0044FF; margin: 14pt 0 5pt; }
h3 { font-size: 10pt; color: #031042; margin: 10pt 0 4pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 7.6pt; page-break-inside: auto; }
tr { page-break-inside: avoid; } th { background: #031042; color: #fff; text-align: left; padding: 3pt 4pt; }
td { border-bottom: 0.5pt solid #E3E6EA; padding: 3pt 4pt; vertical-align: top; } tr:nth-child(even) td { background: #F8F9FA; }
code { font-family: "Courier New", monospace; font-size: 7pt; color: #031042; word-break: break-word; }
pre { background: #0B1530; color: #D6E4FF; padding: 6pt; border-radius: 4pt; } pre code { color: #D6E4FF; }
blockquote { border-left: 2pt solid #F6C42D; margin: 6pt 0; padding: 2pt 8pt; color: #333; background: #FFF9E6; }
img { width: 100%; border: 0.5pt solid #E3E6EA; margin-bottom: 6pt; } .cap { font-weight: bold; color: #0044FF; margin: 4pt 0 2pt; }
.cover { page-break-after: always; background: #031042; color: #fff; margin: -14mm; padding: 40mm 20mm; height: 180mm; }
.cover h1 { color: #fff; font-size: 30pt; } .cover p { color: #A0B3DB; font-size: 12pt; }
"""
cover = f"""<div class="cover"><p style="letter-spacing:3pt;font-size:9pt;font-weight:bold">DAIRYCO STRATEGY REVIEW · TECHNICAL APPENDIX</p>
<h1>How the answers were built</h1><p>Findings · architecture and decisions · EDA and data quality · semantic model reference ·
security and production readiness · AI and advanced analytics · explainer briefs and Q&amp;A</p>
<p style="margin-top:40mm;color:#fff;font-weight:bold">Amr Dawoud</p><p>BI Consultant &amp; AI Engineer · {datetime.date.today():%d %B %Y}</p></div>"""
html = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{cover}{body}</body></html>"
out = D / "DairyCo_Technical_Appendix.pdf"
weasyprint.HTML(string=html, base_url=str(D)).write_pdf(out)
print("wrote", out, out.stat().st_size // 1024, "KB")
