"""Push recovery records that failed to save during process_transcript.py"""
import os
import json
import sys
import time
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())

def push_recovery(filepath):
    with open(filepath, 'r') as f:
        records = json.load(f)

    print(f"Found {len(records)} records to push.\n")
    pushed = 0
    failed = []

    for i, record in enumerate(records):
        print(f"Pushing {i+1}/{len(records)}: {record['original_problem'][:60]}...")
        max_retries = 5
        success = False
        for attempt in range(max_retries):
            try:
                supabase.table("qa_flaw_deck").insert(record).execute()
                success = True
                break
            except Exception as e:
                wait = 2 ** attempt * 5
                print(f"  ⚠️ Attempt {attempt+1}/{max_retries} failed: {str(e)[:80]}")
                if attempt < max_retries - 1:
                    print(f"  ⏳ Retrying in {wait}s...")
                    time.sleep(wait)

        if success:
            pushed += 1
            print("  ✅ Pushed.")
        else:
            failed.append(record)
            print("  ❌ Still failing.")

    if failed:
        with open(filepath, 'w') as f:
            json.dump(failed, f, indent=2)
        print(f"\nDone. {pushed} pushed, {len(failed)} still failed (kept in {filepath}).")
    else:
        os.remove(filepath)
        print(f"\nDone. All {pushed} records pushed. Recovery file deleted.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/push_recovery.py <recovery_file.json>")
        sys.exit(1)
    push_recovery(sys.argv[1])
