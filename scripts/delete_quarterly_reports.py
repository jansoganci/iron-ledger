#!/usr/bin/env python3
"""Delete all quarterly reports from the database.

This fixes the issue where old quarterly reports (created before Decimal fix)
cause the frontend to crash when trying to render them.
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from supabase import create_client

# Load from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    sys.exit(1)

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Fetching quarterly reports...")
result = db.table("reports").select("id, period, report_type").eq("report_type", "quarterly").execute()

if not result.data:
    print("✓ No quarterly reports found in database.")
    sys.exit(0)

print(f"Found {len(result.data)} quarterly reports:")
for r in result.data:
    print(f"  - {r['id']} (period: {r['period']})")

print("\nDeleting quarterly reports...")
delete_result = db.table("reports").delete().eq("report_type", "quarterly").execute()

print(f"✓ Deleted {len(result.data)} quarterly reports successfully!")
print("\nYou can now generate new quarterly reports with the fixed Decimal serialization.")
