"""Export the deployed report to PDF (Power BI ExportTo API) for visual QA / screenshots.
   python export_report.py <workspace> <out.pdf>"""
import sys, time, pathlib, requests
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fabric import workspace_id, item_id
from dax import h, PBI
ws = workspace_id(sys.argv[1]); rid = item_id(ws, "DairyCo Management", "Report")
r = requests.post(f"{PBI}/groups/{ws}/reports/{rid}/ExportTo", headers=h(), json={"format": "PDF"})
if r.status_code != 202: sys.exit(f"{r.status_code} {r.text[:2000]}")
eid = r.json()["id"]
while True:
    time.sleep(10)
    st = requests.get(f"{PBI}/groups/{ws}/reports/{rid}/exports/{eid}", headers=h()).json()
    print(st["status"], st.get("percentComplete"))
    if st["status"] in ("Succeeded", "Failed"): break
if st["status"] == "Failed": sys.exit(str(st))
pathlib.Path(sys.argv[2]).write_bytes(requests.get(f"{PBI}/groups/{ws}/reports/{rid}/exports/{eid}/file", headers=h()).content)
print("saved", sys.argv[2])
