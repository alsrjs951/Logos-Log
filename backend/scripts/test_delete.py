import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

url = os.getenv("SUPABASE_URL")
if url:
    url = url.split("/rest/v1")[0].strip()
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Missing Supabase credentials")
    sys.exit(1)

supabase = create_client(url, key)

try:
    print("Clearing all remaining documents...")
    total_deleted = 0
    while True:
        res = supabase.table("documents").select("id").limit(200).execute()
        ids = [r["id"] for r in res.data]
        if not ids:
            break
        supabase.table("documents").delete().in_("id", ids).execute()
        total_deleted += len(ids)
        print(f"Deleted {len(ids)} rows. Cumulative deleted: {total_deleted}")
        
    # Final count check
    final_res = supabase.table("documents").select("id", count="exact").limit(0).execute()
    print(f"Cleanup done. Remaining rows: {final_res.count}")
except Exception as e:
    print("Error during cleanup:", e)
