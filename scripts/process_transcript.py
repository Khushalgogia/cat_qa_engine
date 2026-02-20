import os
import json
import sys
from google import genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

ERROR_CATEGORIES = [
    "Algebraic Sign Error",
    "Ignoring Negative Root",
    "Integer Constraint Missed",
    "Ratio Misapplied",
    "At-Least vs Exactly Confusion",
    "Division by Variable Without Checking Zero",
    "Proportionality Assumed Equal",
    "Calculation Shortcut Trap",
    "Misread Constraint"
]

CALL_1_PROMPT = """
You are analyzing a transcript of a CAT exam quantitative aptitude class.
The teacher explains concepts and solves problems out loud. Students attempt problems and the teacher gives correct answers.

Task: Find every moment where a problem was fully solved by the teacher — meaning the problem was stated AND the teacher walked through the complete solution.

For each such problem, extract:
a) The problem statement in clean mathematical language.
b) The teacher's solution as numbered logical steps. Each step is one clear mathematical action.

IMPORTANT RULES:
- Do NOT solve anything yourself. Only extract what the teacher actually said and did.
- If a problem's explanation is incomplete or unclear, skip it entirely.
- MAXIMUM 10 steps per solution. If the teacher used more than 10 steps, merge trivially related consecutive steps so the total is at most 10.
- Return a JSON array only. No text outside the JSON.
- Each element: {{"problem_statement": "...", "solution_steps": ["step 1", "step 2", ...]}}

Transcript:
{transcript}
"""

CALL_2_PROMPT = """
Below is a math problem and solution steps extracted from a class transcript.
Clean up the language so each step is one precise mathematical action.
Do not change any numbers, logic, or mathematical operations. Only improve clarity.
Return the exact same JSON structure with cleaner language.

{extracted}
"""

CALL_3_PROMPT = """
Below is a correct step-by-step solution to a math problem.
Your task: Introduce exactly one conceptual error into exactly one step.

The error must come from this list:
{categories}

Rules:
- Make the error subtle — the kind a student under time pressure would miss.
- Steps after the corrupted step must follow logically from the corrupted step (as if the student continued with the wrong value).
- Do not make it obviously wrong.
- The corrupted solution must have AT MOST 10 steps total. If it exceeds 10, merge trivially related consecutive correct steps.

Return a JSON object with these exact keys:
- "corrupted_steps": full solution array with one step silently changed (MAX 10 steps)
- "flaw_step_number": the 1-based index of the corrupted step (integer)
- "error_category": which category from the list you used
- "explanation": one sentence explaining exactly what was corrupted and why it is wrong
- "trap_axiom": a single vivid sentence capturing the underlying rule being violated. No formulas. Pure logic. Slightly poetic but sharp. Like a rule you would tattoo on your wrist.

Return only valid JSON. No text outside the JSON.

Problem: {problem}
Correct steps: {steps}
"""

def call_llm(prompt, max_retries=5):
    import time
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            text = response.text.strip()
            # Strip markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** attempt * 10  # 10s, 20s, 40s, 80s, 160s
                print(f"  ⏳ Rate limited. Waiting {wait}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded for Gemini API")

def process_transcript(filepath):
    transcript_name = os.path.basename(filepath)
    
    with open(filepath, 'r') as f:
        transcript = f.read()

    print("\n--- CALL 1: Extracting problems from transcript ---")
    raw1 = call_llm(CALL_1_PROMPT.format(transcript=transcript))
    extracted = json.loads(raw1)
    print(f"Found {len(extracted)} problems.")

    print("\n--- CALL 2: Sanitizing solutions ---")
    raw2 = call_llm(CALL_2_PROMPT.format(extracted=json.dumps(extracted, indent=2)))
    sanitized = json.loads(raw2)

    saved = 0
    skipped = 0

    for i, item in enumerate(sanitized):
        print(f"\n--- CALL 3: Corrupting problem {i+1}/{len(sanitized)} ---")
        print(f"Problem: {item['problem_statement'][:80]}...")

        raw3 = call_llm(CALL_3_PROMPT.format(
            categories=json.dumps(ERROR_CATEGORIES),
            problem=item['problem_statement'],
            steps=json.dumps(item['solution_steps'])
        ))
        corruption = json.loads(raw3)

        # QUALITY CHECK — you review before saving
        print(f"\nProblem: {item['problem_statement']}")
        print(f"Corrupted steps:")
        for j, step in enumerate(corruption['corrupted_steps'], 1):
            marker = " ← FLAW" if j == corruption['flaw_step_number'] else ""
            print(f"  Step {j}: {step}{marker}")
        print(f"Category: {corruption['error_category']}")
        print(f"Explanation: {corruption['explanation']}")
        print(f"Trap Axiom: {corruption['trap_axiom']}")

        # Validate step count — Telegram polls max 10 options
        if len(corruption['corrupted_steps']) > 10:
            print(f"  ⚠️ Still {len(corruption['corrupted_steps'])} steps after corruption. Telegram max is 10. Skipping.")
            skipped += 1
            continue

        confirm = input("\nPush to database? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Skipped.")
            skipped += 1
            continue

        supabase.table("qa_flaw_deck").insert({
            "source_file": transcript_name,
            "original_problem": item["problem_statement"],
            "solution_steps": corruption["corrupted_steps"],
            "flawed_step_number": corruption["flaw_step_number"],
            "explanation": corruption["explanation"],
            "trap_axiom": corruption["trap_axiom"],
            "error_category": corruption["error_category"],
            "status": "unseen"
        }).execute()

        saved += 1
        print("Saved.")

    print(f"\nDone. {saved} saved, {skipped} skipped from {transcript_name}.")

if __name__ == "__main__":
    process_transcript(sys.argv[1])
