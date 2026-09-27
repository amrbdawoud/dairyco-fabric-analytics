"""Minimal Fabric REST helper for operating the DairyCo workspaces from a workstation.

    python fabric.py items    <workspace_name>
    python fabric.py run      <workspace_name> <notebook_name> [--params '{"k": "v"}']
    python fabric.py pipeline <workspace_name> <pipeline_name>
    python fabric.py logs     <workspace_name> <notebook_name>

Item definitions are not deployed from here: they live in fabric/ (Fabric Git integration) and are promoted
Dev -> Prod by the deployment pipeline. This helper runs jobs, waits for them and fetches Spark driver errors.
"""
import json, sys, time
import requests
from azure.identity import AzureCliCredential

API = "https://api.fabric.microsoft.com/v1"
HDR = {"x-ms-fabric-skill": "spark-cli"}
_cred = AzureCliCredential()


def _h():
    return {**HDR, "Authorization": "Bearer " + _cred.get_token("https://api.fabric.microsoft.com/.default").token}


def call(method, path, body=None, ok=(200, 201, 202)):
    for attempt in range(6):
        r = requests.request(method, path if path.startswith("http") else API + path, headers=_h(), json=body)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 20))); continue
        if r.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:2000]}")
        return r
    raise RuntimeError("throttled")


def lro(r):
    """Poll a 202 long-running operation to completion; return the final operation JSON."""
    if r.status_code != 202:
        return r.json() if r.text else {}
    loc = r.headers["Location"]
    while True:
        time.sleep(int(r.headers.get("Retry-After", 3)))
        r = call("GET", loc)
        st = r.json().get("status")
        if st in ("Succeeded", "Failed", "Undefined"):
            if st != "Succeeded":
                raise RuntimeError(json.dumps(r.json())[:2000])
            return r.json()


def workspace_id(name):
    ws = [w for w in call("GET", "/workspaces").json()["value"] if w["displayName"] == name]
    if len(ws) != 1:
        raise SystemExit(f"workspace {name!r}: {len(ws)} matches")
    return ws[0]["id"]


def items(ws, type_=None):
    out, url = [], f"/workspaces/{ws}/items" + (f"?type={type_}" if type_ else "")
    while url:
        j = call("GET", url).json()
        out += j["value"]
        url = j.get("continuationUri")
    return out


def item_id(ws, name, type_):
    m = [i for i in items(ws, type_) if i["displayName"] == name]
    return m[0]["id"] if m else None


def run(ws_name, nb_name, params=None, timeout=3600):
    ws = workspace_id(ws_name)
    nid = item_id(ws, nb_name, "Notebook")
    body = {}
    if params:
        body = {"executionData": {"parameters": {k: {"value": v, "type": "string"} for k, v in params.items()}}}
    r = call("POST", f"/workspaces/{ws}/items/{nid}/jobs/instances?jobType=RunNotebook", body)
    loc = r.headers["Location"]
    print("job", loc.rsplit("/", 1)[-1])
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(20)
        j = call("GET", loc).json()
        st = j.get("status")
        print(f"  {int(time.time()-t0)}s {st}", flush=True)
        if st in ("Completed", "Failed", "Cancelled", "Deduped"):
            if st != "Completed":
                print(json.dumps(j.get("failureReason"), indent=1))
                sys.exit(1)
            return j
    sys.exit("timeout")


def logs(ws_name, nb_name, fname="stdout", grep=r"AnalysisException|Py4JJavaError|\w+Error:|\[[A-Z_]{6,}\]"):
    """Print error lines from the driver stderr of the notebook's most recent Spark session."""
    import re
    ws = workspace_id(ws_name); nid = item_id(ws, nb_name, "Notebook")
    sess = sorted(call("GET", f"/workspaces/{ws}/notebooks/{nid}/livySessions").json()["value"],
                  key=lambda x: x.get("submittedDateTime", ""))[-1]
    base = f"/workspaces/{ws}/notebooks/{nid}/livySessions/{sess['livyId']}/applications/{sess['sparkApplicationId']}"
    txt = call("GET", base + "/logs?type=driver&fileName=" + fname + "&isDownload=true").text
    for l in txt.splitlines():
        if re.search(grep, l) and "WARN" not in l[:40]:
            print(l[:400])


def run_pipeline(ws_name, name, params=None, timeout=5400):
    ws = workspace_id(ws_name); pid = item_id(ws, name, "DataPipeline")
    r = call("POST", f"/workspaces/{ws}/items/{pid}/jobs/instances?jobType=Pipeline",
             {"executionData": {"parameters": params or {}}})
    loc = r.headers["Location"]; t0 = time.time(); print("pipeline job", loc.rsplit("/", 1)[-1])
    while time.time() - t0 < timeout:
        time.sleep(30)
        j = call("GET", loc).json(); st = j.get("status"); print(f"  {int(time.time()-t0)}s {st}", flush=True)
        if st in ("Completed", "Failed", "Cancelled", "Deduped"):
            if st != "Completed": print(json.dumps(j.get("failureReason"), indent=1)); sys.exit(1)
            return j


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        p = json.loads(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[4] == "--params" else None
        run(sys.argv[2], sys.argv[3], p)
    elif cmd == "logs":
        logs(sys.argv[2], sys.argv[3])
    elif cmd == "pipeline":
        run_pipeline(sys.argv[2], sys.argv[3])
    elif cmd == "items":
        for i in items(workspace_id(sys.argv[2])):
            print(i["type"], i["displayName"], i["id"])
