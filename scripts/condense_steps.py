"""One-time script to condense existing DB problems with >10 steps to ≤10 steps."""
import os, json
from dotenv import load_dotenv
from supabase import create_client
from google import genai

load_dotenv()

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

r = sb.table("qa_flaw_deck").select("id, solution_steps, flawed_step_number, original_problem").execute()
over_limit = [p for p in r.data if isinstance(p["solution_steps"], list) and len(p["solution_steps"]) > 10]
print(f"Condensing {len(over_limit)} problems with >10 steps...\n")

for p in over_limit:
    steps = p["solution_steps"]
    flaw_idx = p["flawed_step_number"]
    n_steps = len(steps)
    print(f"  Problem {p['id'][:8]}...: {n_steps} steps, flaw at step {flaw_idx}")

    prompt = f"""You have a math solution with {n_steps} numbered steps.
The flaw is in step {flaw_idx}.
Condense this into EXACTLY 10 steps or fewer by merging trivially related consecutive steps.
CRITICAL: The flawed step must remain identifiable — do NOT merge it with a correct step.

Current steps:
{json.dumps(steps, indent=2)}

Return ONLY a JSON object with:
- "condensed_steps": array of max 10 steps
- "new_flaw_step_number": the 1-based index of the flawed step in the condensed version

Return only valid JSON."""

    import time
    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            break
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                wait = 2 ** attempt * 10
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise

    new_steps = result["condensed_steps"]
    new_flaw = result["new_flaw_step_number"]
    print(f"  -> Condensed to {len(new_steps)} steps, flaw now at step {new_flaw}")

    if len(new_steps) <= 10:
        sb.table("qa_flaw_deck").update({
            "solution_steps": new_steps,
            "flawed_step_number": new_flaw
        }).eq("id", p["id"]).execute()
        print(f"  OK Updated in DB")
    else:
        print(f"  WARN Still over 10, skipping")

print("\nDone.")
