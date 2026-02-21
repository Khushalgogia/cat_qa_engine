"""One-time script to condense existing DB problems with >10 steps to ≤10 steps."""
import os, json, time
from dotenv import load_dotenv
from supabase import create_client
from google import genai

load_dotenv()

sb = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())

r = sb.table("qa_flaw_deck").select("id, solution_steps, flawed_step_number, original_problem").execute()
over_limit = [p for p in r.data if isinstance(p["solution_steps"], list) and len(p["solution_steps"]) > 10]
print(f"Condensing {len(over_limit)} problems with >10 steps...\n")


def call_with_retry(prompt, max_retries=3):
    """Call LLM with rate-limit retry."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                wait = 2 ** attempt * 10
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded for rate-limit errors")


for p in over_limit:
    steps = p["solution_steps"]
    flaw_idx = p["flawed_step_number"]
    n_steps = len(steps)
    print(f"  Problem {p['id'][:8]}...: {n_steps} steps, flaw at step {flaw_idx}")

    current_steps = steps
    current_flaw = flaw_idx

    # Recursive re-prompt: up to 3 rounds if LLM keeps returning >10 steps
    for condense_round in range(3):
        n = len(current_steps)
        if condense_round == 0:
            prompt = f"""You have a math solution with {n} numbered steps.
The flaw is in step {current_flaw}.
Condense this into EXACTLY 10 steps or fewer by merging trivially related consecutive steps.
CRITICAL: The flawed step must remain identifiable — do NOT merge it with a correct step.

Current steps:
{json.dumps(current_steps, indent=2)}

Return ONLY a JSON object with:
- "condensed_steps": array of max 10 steps
- "new_flaw_step_number": the 1-based index of the flawed step in the condensed version

Return only valid JSON."""
        else:
            prompt = f"""You returned {n} steps in a previous condensation attempt. This is STILL over the limit.
You MUST return 10 steps or fewer. Merge more aggressively — combine any trivially related consecutive correct steps.
The flawed step (currently step {current_flaw}) must NOT be merged with a correct step.

Steps to re-condense:
{json.dumps(current_steps, indent=2)}

Return ONLY a JSON object with:
- "condensed_steps": array of MAXIMUM 10 steps
- "new_flaw_step_number": the 1-based index of the flawed step

Return only valid JSON."""

        result = call_with_retry(prompt)
        current_steps = result["condensed_steps"]
        current_flaw = result["new_flaw_step_number"]
        print(f"    Round {condense_round + 1}: condensed to {len(current_steps)} steps, flaw at step {current_flaw}")

        if len(current_steps) <= 10:
            break

    if len(current_steps) <= 10:
        sb.table("qa_flaw_deck").update({
            "solution_steps": current_steps,
            "flawed_step_number": current_flaw
        }).eq("id", p["id"]).execute()
        print(f"  OK Updated in DB")
    else:
        print(f"  WARN Still over 10 after 3 rounds, skipping")

print("\nDone.")
