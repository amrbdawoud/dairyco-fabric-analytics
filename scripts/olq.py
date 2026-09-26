"""Query Delta tables in OneLake locally with DuckDB (verification only).
   python olq.py <lakehouse> "<sql using table names as views>"   (tables referenced must be listed via --t)
   python olq.py lh_bronze --t erp_sales,_ingestion_log "select ..."
"""
import sys, duckdb
from azure.identity import AzureCliCredential
from deltalake import DeltaTable
WS = "13f3caf0-07d5-45b6-aba0-319b493a9692"
LH = {"lh_bronze": "b283782d-8f21-401a-86d7-4aa51f744a72", "lh_silver": "f3de4535-b563-4c1a-8c44-c2ce71db6984",
      "lh_gold": "e874ccb7-c908-445a-9469-181d36b50b7b"}
tok = AzureCliCredential().get_token("https://storage.azure.com/.default").token
opts = {"bearer_token": tok, "use_fabric_endpoint": "true"}
def table(lh, t):
    return DeltaTable(f"abfss://{WS}@onelake.dfs.fabric.microsoft.com/{LH[lh]}/Tables/{t}", storage_options=opts).to_pyarrow_table()
if __name__ == "__main__":
    lh = sys.argv[1]; ts = sys.argv[3].split(","); sql = sys.argv[4]
    con = duckdb.connect()
    for t in ts:
        l, _, n = t.rpartition(".")
        con.register(n, table(l or lh, n))
    print(con.sql(sql).df().to_string(max_rows=200, max_colwidth=60))
