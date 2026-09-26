"""Upload the candidate-pack source extracts to lh_bronze/Files/landing/<source>/load_date=<d>/.

Sales.csv is split into an initial load (<= 2026-07-31) and an incremental drop (Aug 2026)
so the watermark/MERGE path in silver can be demonstrated.
Usage: python upload_landing.py <data_dir> <workspace_id> <lakehouse_id> [initial|incremental]
"""
import csv, io, sys, pathlib
from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient

SOURCE_MAP = {"01_ERP_WMS": "erp", "02_Salesforce_CRM": "crm", "03_Distributor_Platform": "distributor",
              "04_Production_MRP": "mrp", "05_HR_Payroll": "hr"}
INITIAL_DATE, INCR_DATE, CUTOFF = "2026-08-01", "2026-09-01", "2026-08-01"

def split_sales(path):
    rows = list(csv.reader(open(path, newline="")))
    hdr, body = rows[0], rows[1:]
    i = hdr.index("InvoiceDate")
    def dump(rs):
        b = io.StringIO(); w = csv.writer(b, lineterminator="\n"); w.writerow(hdr); w.writerows(rs); return b.getvalue().encode()
    return dump([r for r in body if r[i] < CUTOFF]), dump([r for r in body if r[i] >= CUTOFF])

def main(data_dir, ws, lh, mode):
    fs = DataLakeServiceClient("https://onelake.dfs.fabric.microsoft.com", credential=AzureCliCredential()).get_file_system_client(ws)
    def put(rel, data):
        fs.get_file_client(f"{lh}/Files/{rel}").upload_data(data, overwrite=True); print("uploaded", rel, len(data))
    for f in sorted(pathlib.Path(data_dir).rglob("*")):
        if not f.is_file(): continue
        src = SOURCE_MAP[f.parent.name]
        if f.name == "Sales.csv":
            init, incr = split_sales(f)
            if mode == "initial": put(f"landing/{src}/load_date={INITIAL_DATE}/{f.name}", init)
            else: put(f"landing/{src}/load_date={INCR_DATE}/{f.name}", incr)
        elif mode == "initial":
            put(f"landing/{src}/load_date={INITIAL_DATE}/{f.name}", f.read_bytes())

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "initial")
