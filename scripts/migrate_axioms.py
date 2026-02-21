"""
One-time migration script: Convert all legacy string trap_axioms
in qa_flaw_deck to the new 3-part Cognitive Anchor JSON format.

Usage:
    python scripts/migrate_axioms.py

Requires: SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY env vars (or .env file)
"""

import os
import json
import time
from supabase import create_client
from google import genai
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())

CONVERSION_PROMPT = """You are given a math problem, its error category, and a legacy "trap axiom" 
(a single sentence describing the underlying rule being violated).

Your task: Convert this into a richer 3-part Cognitive Anchor JSON object.

Legacy axiom: {axiom}
Error category: {category}
Problem context: {problem}

Return ONLY a valid JSON object with exactly these 3 keys:
- "core_rule": one crisp sentence stating the fundamental mathematical rule being violated. No formulas. Pure logic. Sharp and absolute.
- "mental_model": a vivid analogy or visual metaphor that makes the rule intuitive. Use everyday objects or scenarios. Make it so clear a 10-year-old would get it.
- "anchor_question": a reflective question the student should ask themselves BEFORE making this kind of mistake again. Phrased as "Before you..., ask yourself: ...?"

Return only valid JSON. No text outside the JSON."""


def convert_axiom(axiom, category, problem, max_retries=3):
    """Call Gemini to convert a string axiom into a 3-part JSON."""
    prompt = CONVERSION_PROMPT.format(axiom=axiom, category=category, problem=problem)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)

            # Validate all 3 keys exist
            assert "core_rule" in result, "Missing core_rule"
            assert "mental_model" in result, "Missing mental_model"
            assert "anchor_question" in result, "Missing anchor_question"
            return result

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** attempt * 10
                print(f"    ⏳ Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    ❌ Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    return None
    return None


def migrate():
    # Fetch all rows from qa_flaw_deck
    result = supabase.table("qa_flaw_deck")\
        .select("id, trap_axiom, error_category, original_problem")\
        .execute()

    rows = result.data
    print(f"Found {len(rows)} total problems in qa_flaw_deck.\n")

    migrated = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(rows):
        axiom = row["trap_axiom"]
        problem_id = row["id"][:8]

        # Check if already in JSON format
        if isinstance(axiom, dict):
            print(f"  [{i+1}/{len(rows)}] {problem_id}... already JSON. Skipping.")
            skipped += 1
            continue

        if isinstance(axiom, str):
            try:
                parsed = json.loads(axiom)
                if isinstance(parsed, dict) and "core_rule" in parsed:
                    print(f"  [{i+1}/{len(rows)}] {problem_id}... already JSON string. Skipping.")
                    skipped += 1
                    continue
            except (json.JSONDecodeError, TypeError):
                pass  # It's a legacy string — needs conversion

        print(f"  [{i+1}/{len(rows)}] {problem_id}... Converting: \"{str(axiom)[:60]}...\"")

        new_axiom = convert_axiom(
            axiom=axiom,
            category=row.get("error_category", "Unknown"),
            problem=row.get("original_problem", "")[:300]  # truncate for prompt efficiency
        )

        if new_axiom:
            # Store as JSON string in the text column
            supabase.table("qa_flaw_deck")\
                .update({"trap_axiom": json.dumps(new_axiom)})\
                .eq("id", row["id"])\
                .execute()

            print(f"    ✅ Migrated!")
            print(f"       Rule: {new_axiom['core_rule'][:80]}...")
            migrated += 1
        else:
            print(f"    ❌ Failed to convert. Leaving as-is.")
            failed += 1

        # Small delay to avoid rate limits
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Migration complete!")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped (already JSON): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(rows)}")


if __name__ == "__main__":
    migrate()
