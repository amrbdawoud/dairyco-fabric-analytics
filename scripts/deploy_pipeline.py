"""Build and deploy pl_dairyco_daily (bronze -> silver -> gold [-> ml]) into a workspace.
   python deploy_pipeline.py <workspace_name>
Notebook IDs are resolved by name in the target workspace, so the same script deploys Dev or Prod."""
import base64, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fabric import workspace_id, item_id, call, lro

ws_name = sys.argv[1]
ws = workspace_id(ws_name)
steps = [("Bronze ingest", "nb_01_bronze_ingest", {"load_date_filter": "@pipeline().parameters.load_date_filter"}),
         ("Silver transform", "nb_02_silver_transform", {"full_reload": "@pipeline().parameters.full_reload"}),
         ("Gold star schema", "nb_03_gold_star_schema", {}),
         ("ML demand forecast", "nb_05_ml_demand_forecast", {})]
acts, prev = [], None
for name, nb, params in steps:
    nid = item_id(ws, nb, "Notebook")
    if not nid:
        print("skip (not deployed):", nb); continue
    p = {"batch_id": {"value": {"value": "@pipeline().RunId", "type": "Expression"}, "type": "string"}}
    for k, v in params.items():
        p[k] = {"value": {"value": v, "type": "Expression"}, "type": "string"}
    acts.append({"name": name, "type": "TridentNotebook",
                 "dependsOn": [{"activity": prev, "dependencyConditions": ["Succeeded"]}] if prev else [],
                 "policy": {"timeout": "0.02:00:00", "retry": 2, "retryIntervalInSeconds": 120, "secureOutput": False, "secureInput": False},
                 "typeProperties": {"notebookId": nid, "workspaceId": ws, "parameters": p}})
    prev = name
content = {"properties": {
    "description": "DairyCo daily load: metadata-driven bronze ingest, silver conform+DQ gate, gold star schema, ML forecast. "
                   "Direct Lake model picks up new gold data automatically (no import refresh).",
    "activities": acts,
    "parameters": {"load_date_filter": {"type": "string", "defaultValue": ""}, "full_reload": {"type": "string", "defaultValue": "false"}}}}
pathlib.Path("pipelines/pl_dairyco_daily.json").write_text(json.dumps(content, indent=1))
definition = {"parts": [{"path": "pipeline-content.json", "payload": base64.b64encode(json.dumps(content).encode()).decode(),
                         "payloadType": "InlineBase64"}]}
pid = item_id(ws, "pl_dairyco_daily", "DataPipeline")
if pid:
    lro(call("POST", f"/workspaces/{ws}/items/{pid}/updateDefinition", {"definition": definition})); print("updated", pid)
else:
    lro(call("POST", f"/workspaces/{ws}/items", {"displayName": "pl_dairyco_daily", "type": "DataPipeline", "definition": definition}))
    print("created", item_id(ws, "pl_dairyco_daily", "DataPipeline"))
