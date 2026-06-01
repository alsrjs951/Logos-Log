import os
import sys
import json
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
    res = supabase.table("documents").select("id", count="exact").limit(0).execute()
    print("Total rows in documents table:", res.count)
    
    # Also print uploaded files count
    EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))
    TRACK_FILE = os.path.join(EMBEDDING_DIR, 'uploaded_files.json')
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r') as f:
            uploaded = json.load(f)
        print("Total files uploaded:", len(uploaded))
    else:
        print("uploaded_files.json does not exist yet.")
except Exception as e:
    print("Error getting count:", e)
