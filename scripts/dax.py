"""Run DAX against the deployed model (Power BI executeQueries) and trigger Direct Lake refresh (framing).
   python dax.py <workspace> refresh
   python dax.py <workspace> "EVALUATE ..." [--as user@upn]"""
import sys, time, json, pathlib, requests
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fabric import workspace_id, item_id, _cred
PBI = "https://api.powerbi.com/v1.0/myorg"
def h(): return {"Authorization": "Bearer " + _cred.get_token("https://analysis.windows.net/powerbi/api/.default").token}
def model(ws_name):
    ws = workspace_id(ws_name); return ws, item_id(ws, "DairyCo Analytics", "SemanticModel")
def refresh(ws_name):
    ws, sm = model(ws_name)
    r = requests.post(f"{PBI}/groups/{ws}/datasets/{sm}/refreshes", headers=h(), json={"type": "full"}); r.raise_for_status()
    while True:
        time.sleep(10)
        st = requests.get(f"{PBI}/groups/{ws}/datasets/{sm}/refreshes?$top=1", headers=h()).json()["value"][0]
        if st["status"] != "Unknown":
            print(st["status"], st.get("serviceExceptionJson", "")); return
def query(ws_name, q, user=None):
    ws, sm = model(ws_name)
    body = {"queries": [{"query": q}], "serializerSettings": {"includeNulls": True}}
    if user: body["impersonatedUserName"] = user
    r = requests.post(f"{PBI}/groups/{ws}/datasets/{sm}/executeQueries", headers=h(), json=body)
    if r.status_code != 200: print(r.status_code, r.text[:3000]); sys.exit(1)
    res = r.json()["results"][0]
    if "error" in res: print(json.dumps(res["error"])[:3000]); sys.exit(1)
    return res["tables"][0]["rows"]
if __name__ == "__main__":
    if sys.argv[2] == "refresh": refresh(sys.argv[1])
    else:
        rows = query(sys.argv[1], sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else None)
        for r in rows: print({k.split("[")[-1].rstrip("]"): (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
