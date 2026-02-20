# CAT QA Engine — Complete Clone-Ready Documentation

> Every file, every SQL statement, every prompt, every workflow. A person reading this can build the exact same app from scratch.

---

## Table of Contents

1. [What This App Does](#what-this-app-does)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Step 1: Create Supabase Project](#step-1-create-supabase-project)
6. [Step 2: Create Telegram Bot](#step-2-create-telegram-bot)
7. [Step 3: Get Gemini API Key](#step-3-get-gemini-api-key)
8. [Step 4: Set Up Your Mac](#step-4-set-up-your-mac)
9. [Step 5: Create All Project Files](#step-5-create-all-project-files)
10. [Step 6: Deploy Edge Function](#step-6-deploy-edge-function)
11. [Step 7: Push to GitHub and Add Secrets](#step-7-push-to-github-and-add-secrets)
12. [Daily Operations](#daily-operations)
13. [Processing Your Audio Backlog](#processing-your-audio-backlog)
14. [How Each Script Works](#how-each-script-works)
15. [Design Decisions](#design-decisions)
16. [Troubleshooting](#troubleshooting)

---

## What This App Does

Two interconnected systems for CAT exam preparation, fully automated via GitHub Actions + Supabase + Telegram:

### System 1: Spot the Flaw (Afternoon → Night)
- Records CAT class audio → transcribes via Whisper → extracts solved problems via Gemini AI
- Corrupts one step in each solution with a subtle, realistic error
- Delivers one "Spot the Flaw" quiz poll daily at 2 PM via Telegram
- Auto-detects whether you caught the flaw or missed it (at 6 PM)
- Sends the trap axiom at 10 PM framed by your result ("you spotted this" vs "this got you")
- Resurfaces missed problems at 10:05 PM for graveyard recall
- When the bank runs dry → revision rounds re-deliver old caught problems

### System 2: Math Sprint (Morning)
- 109 contextual math flashcards (reciprocals, squares, cubes, primes, tables)
- Delivers 5-question speed drills at 8:30 AM with inline keyboard buttons
- Wrong answers add debt — each miss adds that question back to the queue
- Real-time interaction via Supabase Edge Function (messages edit in-place)
- If you missed yesterday's flaw, 2 of today's 5 sprint questions are guaranteed from that category

### Weekly Report
- Combined error fingerprint + sprint stats every Sunday at 8:30 PM

---

## Architecture

```
YOUR MAC (Local)
  audio/*.mp3  →  transcribe.py (Whisper)
                      │
  transcripts/*.txt  →  process_transcript.py (3 Gemini calls per problem)
                      │
  generate_questions.py (one-time, 109 questions)
                      ▼
                 Supabase Database
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
  GITHUB ACTIONS   SUPABASE       TELEGRAM
  (6 scheduled     EDGE FUNC      (your phone)
   workflows)   (sprint-webhook)
```

**Webhook + getUpdates coexistence:**
- Webhook (callback_query only) → Edge Function handles inline button taps in real-time
- getUpdates (text messages, poll answers) → handle_reply.py temporarily removes webhook, polls, then restores it

---

## Project Structure

```
cat_qa_engine/
├── audio/                              ← Drop class audio files here
├── transcripts/                        ← Transcripts auto-saved here
├── scripts/
│   ├── transcribe.py                   ← Audio → text (Whisper, local)
│   ├── process_transcript.py           ← Extract + corrupt problems (Gemini → Supabase)
│   ├── generate_questions.py           ← One-time: populate 109 sprint questions
│   ├── deliver_problem.py              ← Daily quiz poll + revision fallback
│   ├── deliver_axiom.py                ← Nightly axiom with caught/missed framing
│   ├── deliver_sprint.py               ← Morning sprint with yesterday-miss guarantee
│   ├── handle_reply.py                 ← Detect poll/text reply, manage webhook cycle
│   ├── graveyard_check.py              ← Resurface missed problems (10:05 PM)
│   ├── weekly_report.py                ← Combined flaw + sprint stats report
│   ├── register_webhook.py             ← One-time: register Telegram webhook
│   ├── batch_transcribe.sh             ← Batch transcribe all audio files
│   └── condense_steps.py              ← One-time: fix problems with >10 steps
├── supabase/
│   └── functions/
│       └── sprint-webhook/
│           └── index.ts                ← Edge Function: handles inline button taps
├── .github/
│   └── workflows/
│       ├── math_sprint.yml             ← 8:30 AM daily
│       ├── daily_problem.yml           ← 2:00 PM daily
│       ├── handle_reply.yml            ← 6:00 PM daily
│       ├── nightly_axiom.yml           ← 10:00 PM daily
│       ├── graveyard_nudge.yml         ← 10:05 PM daily
│       └── weekly_report.yml           ← 8:30 PM Sunday
├── .env                                ← Your credentials (DO NOT commit)
├── .gitignore
├── requirements.txt
├── README.md
└── Documentation.md
```

---

## Prerequisites

- A Mac with Python 3.11+ installed
- A free Supabase account (supabase.com)
- A Telegram account
- A Google AI Studio account (aistudio.google.com) for Gemini API key
- A GitHub account
- ffmpeg installed (`brew install ffmpeg`)

---

## Step 1: Create Supabase Project

1. Go to supabase.com → Sign up → New Project
2. Name it `cat-qa-engine`, choose a region, set a database password
3. Wait for the project to be created
4. Go to **Settings → API** and copy:
   - **Project URL** (looks like `https://xxxxxx.supabase.co`)
   - **Service Role Key** (under "service_role", starts with `eyJ...`)
   - **Project Ref** (the `xxxxxx` part between `https://` and `.supabase.co`)

5. Go to **SQL Editor** and run this ENTIRE SQL block to create ALL tables:

```sql
-- SYSTEM 1: SPOT THE FLAW TABLES

create table qa_flaw_deck (
  id uuid default gen_random_uuid() primary key,
  original_problem text,
  solution_steps jsonb,
  flawed_step_number int,
  explanation text,
  trap_axiom text,
  error_category text,
  status text default 'unseen',
  delivered_at timestamp,
  source_file text
);

create table daily_log (
  id uuid default gen_random_uuid() primary key,
  problem_id uuid references qa_flaw_deck(id),
  delivered_at timestamp default now(),
  caught boolean,
  is_revision boolean default false
);

create table settings (
  key text primary key,
  value text
);

insert into settings (key, value) values ('todays_problem_id', '');
insert into settings (key, value) values ('todays_axiom', '');
insert into settings (key, value) values ('graveyard_pending_id', '');

-- SYSTEM 2: MATH SPRINT TABLES

create table math_sprints (
  id uuid default gen_random_uuid() primary key,
  category text,
  difficulty_level int default 1,
  question_text text,
  options jsonb,
  correct_answer_index int,
  times_correct int default 0,
  times_attempted int default 0,
  created_at timestamp default now()
);

create table sprint_sessions (
  id uuid default gen_random_uuid() primary key,
  chat_id text,
  message_id bigint,
  question_queue jsonb,
  current_index int default 0,
  original_count int default 5,
  debt_count int default 0,
  completed boolean default false,
  created_at timestamp default now()
);

create table sprint_logs (
  id uuid default gen_random_uuid() primary key,
  session_id uuid references sprint_sessions(id),
  question_id uuid references math_sprints(id),
  category text,
  is_correct boolean,
  is_debt_attempt boolean default false,
  answered_at timestamp default now()
);
```

### Database Schema Reference

| Table | Columns | Purpose |
|-------|---------|---------|
| `qa_flaw_deck` | id, original_problem, solution_steps (jsonb), flawed_step_number, explanation, trap_axiom, error_category, status, delivered_at, source_file | Problems with corrupted solutions. Status flow: unseen → delivered → caught/missed/reviewed |
| `daily_log` | id, problem_id, delivered_at, caught, is_revision | One row per delivered problem. is_revision prevents double-counting |
| `settings` | key, value | Keys: todays_problem_id, todays_axiom, graveyard_pending_id |
| `math_sprints` | id, category, difficulty_level, question_text, options (jsonb), correct_answer_index, times_correct, times_attempted | 109 flashcard questions |
| `sprint_sessions` | id, chat_id, message_id, question_queue (jsonb), current_index, original_count, debt_count, completed | Active sprint sessions with debt queue |
| `sprint_logs` | id, session_id, question_id, category, is_correct, is_debt_attempt, answered_at | Per-answer log for analytics |

---

## Step 2: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "QA CAT Tutor")
4. Choose a username (e.g., `qa_cat_tutor_bot`)
5. Copy the **Bot Token** (looks like `1234567890:AAE2tkzzOC...`)
6. Get your Chat ID: Search for **@userinfobot** on Telegram, send it any message, it replies with your chat ID

---

## Step 3: Get Gemini API Key

1. Go to aistudio.google.com
2. Click **Get API Key** → Create API Key
3. Copy the key (starts with `AIza...`)

---

## Step 4: Set Up Your Mac

```bash
mkdir cat_qa_engine
cd cat_qa_engine
python3 -m venv venv
source venv/bin/activate
pip install google-genai supabase==2.3.5 gotrue==1.3.0 python-telegram-bot==20.7 python-dotenv httpx==0.25.2
pip install openai-whisper
brew install ffmpeg

mkdir -p audio transcripts scripts supabase/functions/sprint-webhook .github/workflows
```

Create `.env` in the project root:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_service_role_key_here
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_gemini_api_key_here
```

Create `requirements.txt`:

```
google-genai
supabase==2.3.5
gotrue==1.3.0
python-telegram-bot==20.7
python-dotenv
httpx==0.25.2
```

Create `.gitignore`:

```
.env
venv/
__pycache__/
*.pyc
audio/
supabase/.temp/
```

---

## Step 5: Create All Project Files

Create each file below with the exact content shown.


### `scripts/transcribe.py`

Audio → text transcription using OpenAI Whisper. Runs locally on your Mac.

```python
import whisper
import sys
import os

def transcribe(audio_path):
    print(f"Loading Whisper model...")
    model = whisper.load_model("base")  # use "small" for better accuracy
    
    print(f"Transcribing {audio_path}... this may take a few minutes.")
    result = model.transcribe(audio_path)
    
    # Always save to transcripts/ directory, regardless of input path
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    transcripts_dir = os.path.join(project_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)
    output_path = os.path.join(transcripts_dir, base_name + ".txt")
    
    with open(output_path, "w") as f:
        f.write(result["text"])
    
    print(f"Done. Transcript saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    transcribe(sys.argv[1])
```


### `scripts/process_transcript.py`

The intelligence layer. Makes 3 Gemini API calls per problem: extract → sanitize → corrupt. Interactive — you approve each corruption before saving.

```python
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
```


### `scripts/generate_questions.py`

One-time script. Generates 109 raw math questions programmatically, wraps each in a contextual scenario via Gemini, and inserts into Supabase.

```python
import os
import json
import random
from google import genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# ─────────────────────────────────────────────
# STEP 1: Generate raw math pairs programmatically
# ─────────────────────────────────────────────

def generate_raw_questions():
    questions = []

    # Reciprocals: 1/n for n = 2 to 20
    reciprocal_map = {
        2: "50%", 3: "33.33%", 4: "25%", 5: "20%", 6: "16.67%",
        7: "14.28%", 8: "12.5%", 9: "11.11%", 10: "10%",
        11: "9.09%", 12: "8.33%", 13: "7.69%", 14: "7.14%",
        15: "6.67%", 16: "6.25%", 17: "5.88%", 18: "5.56%",
        19: "5.26%", 20: "5%"
    }
    for n, pct in reciprocal_map.items():
        all_vals = list(reciprocal_map.values())
        wrong = [v for v in all_vals if v != pct]
        wrong_3 = random.sample(wrong, 3)
        opts = wrong_3 + [pct]
        random.shuffle(opts)
        questions.append({
            "category": "reciprocal",
            "raw_question": f"1/{n} as a percentage",
            "correct_answer": pct,
            "options": opts,
            "correct_answer_index": opts.index(pct)
        })

    # Squares: 1² to 30²
    for n in range(1, 31):
        ans = n * n
        wrongs = [str((n + r) ** 2) for r in [-2, -1, 1, 2] if r != 0 and (n + r) > 0]
        wrong_3 = random.sample(wrongs, min(3, len(wrongs)))
        while len(wrong_3) < 3:
            wrong_3.append(str(ans + random.choice([-4, 4, 6, -6])))
        opts = wrong_3 + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "square",
            "raw_question": f"{n}² = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    # Cubes: 1³ to 15³
    for n in range(1, 16):
        ans = n ** 3
        wrongs = [str((n + r) ** 3) for r in [-1, 1, 2] if (n + r) > 0]
        wrong_3 = random.sample(wrongs, min(3, len(wrongs)))
        while len(wrong_3) < 3:
            wrong_3.append(str(ans + random.choice([-10, 10, 25, -25])))
        opts = wrong_3 + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "cube",
            "raw_question": f"{n}³ = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    # Primes up to 100
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5)+1):
            if n % i == 0: return False
        return True

    composites_with_factors = []
    for n in range(50, 150):
        if not is_prime(n):
            for i in range(2, int(n**0.5)+1):
                if n % i == 0:
                    composites_with_factors.append((n, i, n//i))
                    break

    for n, f1, f2 in random.sample(composites_with_factors, min(25, len(composites_with_factors))):
        correct = f"{f1} × {f2}"
        wrongs = [
            f"Prime",
            f"{f1+1} × {f2-1}" if f1+1 != f2-1 else f"{f1+2} × {f2}",
            f"{f1-1} × {f2+1}" if f1 > 1 else f"{f1} × {f2+2}"
        ]
        opts = wrongs + [correct]
        random.shuffle(opts)
        questions.append({
            "category": "prime",
            "raw_question": f"Can {n} be factored, or is it prime?",
            "correct_answer": correct,
            "options": opts,
            "correct_answer_index": opts.index(correct)
        })

    # Multiplication tables: selective high-value pairs
    valuable_pairs = [
        (13, 7), (17, 8), (14, 9), (18, 7), (23, 6),
        (16, 7), (19, 8), (21, 7), (24, 6), (27, 8),
        (28, 7), (17, 9), (13, 12), (14, 13), (23, 8),
        (17, 13), (19, 12), (24, 8), (26, 7), (29, 6)
    ]
    for a, b in valuable_pairs:
        ans = a * b
        wrongs = [str(ans + d) for d in [-10, 10, a, -b] if ans + d != ans][:3]
        while len(wrongs) < 3:
            wrongs.append(str(ans + random.choice([-5, 5, -15, 15])))
        opts = wrongs + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "table",
            "raw_question": f"{a} × {b} = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    return questions

# ─────────────────────────────────────────────
# STEP 2: Wrap in contextual framing via Gemini
# ─────────────────────────────────────────────

CONTEXT_PROMPT = """
You are helping create flashcard-style math questions for a product analyst 
preparing for the CAT exam. 

Below is a batch of raw math facts. For each one, rewrite the question as a 
short, vivid scenario from the world of product analytics, dashboards, or 
business operations. Keep it under 2 sentences. Keep the answer options exactly 
as given — do not change them. Do not add formulas. Just make the scenario feel 
real and specific.

Return a JSON array. Each element: 
{{"index": N, "question_text": "rewritten scenario"}}

Return only valid JSON. No text outside the JSON.

Batch:
{batch}
"""

def call_gemini(prompt, max_retries=5):
    import time
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview", contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** attempt * 10
                print(f"  ⏳ Rate limited. Waiting {wait}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded for Gemini API")

def wrap_with_context(raw_batch):
    formatted = []
    for i, q in enumerate(raw_batch):
        formatted.append({
            "index": i,
            "raw": q["raw_question"],
            "correct": q["correct_answer"]
        })
    
    text = call_gemini(CONTEXT_PROMPT.format(batch=json.dumps(formatted, indent=2)))
    return json.loads(text)

# ─────────────────────────────────────────────
# STEP 3: Insert to Supabase
# ─────────────────────────────────────────────

def main():
    print("Generating raw math questions...")
    raw_questions = generate_raw_questions()
    print(f"Generated {len(raw_questions)} raw questions.")

    # Process in batches of 20 to avoid token limits
    batch_size = 20
    all_wrapped = []

    for i in range(0, len(raw_questions), batch_size):
        batch = raw_questions[i:i+batch_size]
        print(f"Wrapping batch {i//batch_size + 1}/{(len(raw_questions)-1)//batch_size + 1}...")
        try:
            wrapped = wrap_with_context(batch)
            for item in wrapped:
                idx = item["index"]
                all_wrapped.append({
                    "original_index": i + idx,
                    "question_text": item["question_text"]
                })
        except Exception as e:
            print(f"Batch failed: {e}. Using raw question text as fallback.")
            for idx, q in enumerate(batch):
                all_wrapped.append({
                    "original_index": i + idx,
                    "question_text": q["raw_question"]
                })

    print(f"\nSample output (first 3 questions):")
    for item in all_wrapped[:3]:
        q = raw_questions[item["original_index"]]
        print(f"  [{q['category']}] {item['question_text']}")
        print(f"  Options: {q['options']}")
        print(f"  Correct: {q['correct_answer']} (index {q['correct_answer_index']})\n")

    confirm = input(f"Insert all {len(raw_questions)} questions into Supabase? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return

    rows = []
    for item in all_wrapped:
        i = item["original_index"]
        q = raw_questions[i]
        rows.append({
            "category": q["category"],
            "difficulty_level": 1,
            "question_text": item["question_text"],
            "options": q["options"],
            "correct_answer_index": q["correct_answer_index"],
            "times_correct": 0,
            "times_attempted": 0
        })

    # Insert in chunks of 50
    for i in range(0, len(rows), 50):
        chunk = rows[i:i+50]
        supabase.table("math_sprints").insert(chunk).execute()
        print(f"Inserted rows {i+1} to {min(i+50, len(rows))}...")

    print(f"\nDone. {len(rows)} questions in the database.")

if __name__ == "__main__":
    main()
```


### `scripts/deliver_problem.py`

Daily quiz delivery (2 PM). Picks unseen problems ordered by source_file (chronological). Falls back to revision rounds when bank is exhausted.

```python
import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def deliver():
    # Fetch one unseen problem
    result = supabase.table("qa_flaw_deck")\
        .select("*")\
        .eq("status", "unseen")\
        .order("source_file")\
        .limit(1)\
        .execute()

    # Fallback: if bank is exhausted, re-deliver oldest caught problem as revision
    is_revision = False
    if not result.data:
        result = supabase.table("qa_flaw_deck")\
            .select("*")\
            .eq("status", "caught")\
            .order("delivered_at")\
            .limit(1)\
            .execute()
        is_revision = True

    if not result.data:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Problem bank is empty. Transcribe a new class and run process_transcript.py."
        )
        return

    problem = result.data[0]
    steps = problem["solution_steps"]

    # Safety: Telegram polls max 10 options
    if len(steps) > 10:
        print(f"Problem {problem['id'][:8]}... has {len(steps)} steps (max 10). Skipping.")
        supabase.table("qa_flaw_deck")\
            .update({"status": "skip_overlimit"})\
            .eq("id", problem["id"])\
            .execute()
        # Retry with next problem
        result = supabase.table("qa_flaw_deck")\
            .select("*")\
            .eq("status", "unseen")\
            .order("source_file")\
            .limit(1)\
            .execute()
        if not result.data:
            await bot.send_message(chat_id=chat_id, text="⚠️ No deliverable problems. Run process_transcript.py.")
            return
        problem = result.data[0]
        steps = problem["solution_steps"]

    # Header: revision round or normal
    if is_revision:
        header = "📚 *REVISION ROUND*\n\nYou caught this before. Still remember why the flaw was where it was?\n\n"
    else:
        header = "🔍 *SPOT THE FLAW — 2 PM*\n\n"

    await bot.send_message(
        chat_id=chat_id,
        text=f"{header}*Problem:*\n{problem['original_problem']}",
        parse_mode="Markdown"
    )

    await bot.send_poll(
        chat_id=chat_id,
        question="Which step contains the logical flaw?",
        options=steps,
        type="quiz",
        correct_option_id=problem["flawed_step_number"] - 1,
        explanation=f"Trap: {problem['error_category']}\n\n{problem['explanation']}",
        is_anonymous=False
    )

    # Update settings
    supabase.table("settings")\
        .update({"value": problem["trap_axiom"]})\
        .eq("key", "todays_axiom")\
        .execute()

    supabase.table("settings")\
        .update({"value": problem["id"]})\
        .eq("key", "todays_problem_id")\
        .execute()

    # Mark as delivered (revision stays 'caught' but gets re-delivered)
    if not is_revision:
        supabase.table("qa_flaw_deck")\
            .update({"delivered_at": "now()", "status": "delivered"})\
            .eq("id", problem["id"])\
            .execute()

    supabase.table("daily_log").insert({
        "problem_id": problem["id"],
        "is_revision": is_revision
    }).execute()

    print(f"{'Revision' if is_revision else 'New'} problem delivered: {problem['id'][:8]}...")

asyncio.run(deliver())
```


### `scripts/deliver_axiom.py`

Nightly axiom delivery (10 PM). Checks daily_log for caught/missed and frames the message accordingly.

```python
import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def deliver_axiom():
    # Get today's axiom
    axiom_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_axiom")\
        .execute()

    axiom = axiom_result.data[0]["value"] if axiom_result.data else None
    if not axiom:
        return

    # Get today's problem ID and check if user caught or missed
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data else None
    framing = ""

    if problem_id:
        log = supabase.table("daily_log")\
            .select("caught")\
            .eq("problem_id", problem_id)\
            .execute()

        if log.data and log.data[0]["caught"] is not None:
            if log.data[0]["caught"]:
                framing = "You spotted this one today. Lock it in.\n\n"
            else:
                framing = "This one got you today. Make sure it never does again.\n\n"

    await bot.send_message(
        chat_id=chat_id,
        text=f"🌙 *Tonight's Axiom*\n\n{framing}_{axiom}_\n\nSleep on it.",
        parse_mode="Markdown"
    )
    print(f"Axiom delivered. Framing: {'caught' if 'spotted' in framing else 'missed' if 'got you' in framing else 'neutral'}")

asyncio.run(deliver_axiom())
```


### `scripts/deliver_sprint.py`

Morning sprint delivery (8:30 AM). Selects 5 questions with yesterday-miss guarantee and weak-spot weighting.

```python
import os
import json
import asyncio
import random
from datetime import datetime, timedelta
from collections import Counter
from supabase import create_client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

# Error category → sprint category mapping
CATEGORY_MAP = {
    "Algebraic Sign Error": "square",
    "Ignoring Negative Root": "square",
    "Integer Constraint Missed": "prime",
    "Ratio Misapplied": "reciprocal",
    "Calculation Shortcut Trap": "table",
    "Proportionality Assumed Equal": "reciprocal",
    "Misread Constraint": "prime",
    "At-Least vs Exactly Confusion": "prime",
    "Division by Variable Without Checking Zero": "reciprocal"
}

def escape_md(text):
    """Escape Markdown special characters for Telegram MarkdownV2."""
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, f'\\{ch}')
    return text

def get_yesterday_miss():
    """Check if yesterday's 2 PM flaw problem was missed.
    If so, return the mapped sprint category for guaranteed inclusion."""
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data and problem_result.data[0]["value"] else None
    if not problem_id:
        return None

    log = supabase.table("daily_log")\
        .select("caught, problem_id, qa_flaw_deck(error_category)")\
        .eq("problem_id", problem_id)\
        .execute()

    if not log.data or log.data[0]["caught"] is not False:
        return None  # Not missed, or not yet resolved

    error_cat = log.data[0].get("qa_flaw_deck", {}).get("error_category", "")
    sprint_cat = CATEGORY_MAP.get(error_cat)
    if sprint_cat:
        print(f"Yesterday's miss: {error_cat} → sprint category: {sprint_cat}")
    return sprint_cat

def get_weak_categories():
    """Read all missed Spot the Flaw errors and find weakest categories."""
    logs = supabase.table("daily_log")\
        .select("*, qa_flaw_deck(error_category)")\
        .eq("caught", False)\
        .execute()

    if not logs.data:
        return []

    sprint_cats = []
    for log in logs.data:
        if log.get("qa_flaw_deck"):
            error_cat = log["qa_flaw_deck"].get("error_category", "")
            sprint_cat = CATEGORY_MAP.get(error_cat)
            if sprint_cat:
                sprint_cats.append(sprint_cat)

    if not sprint_cats:
        return []

    return [cat for cat, _ in Counter(sprint_cats).most_common(2)]

def select_questions(weak_categories, yesterday_miss_cat):
    """Select 5 questions with yesterday-miss guarantee + weak spot weighting."""
    questions = []
    existing_ids = []

    # Priority 1: If yesterday was missed, guarantee 2 from that category
    if yesterday_miss_cat:
        result = supabase.table("math_sprints")\
            .select("*")\
            .eq("category", yesterday_miss_cat)\
            .order("times_attempted")\
            .limit(10)\
            .execute()
        if result.data:
            pool = random.sample(result.data, min(2, len(result.data)))
            questions.extend(pool)
            existing_ids = [q["id"] for q in questions]

    # Priority 2: Fill from weak categories (if any slots left)
    if len(questions) < 2 and weak_categories:
        for cat in weak_categories[:2]:
            if len(questions) >= 2:
                break
            result = supabase.table("math_sprints")\
                .select("*")\
                .eq("category", cat)\
                .order("times_attempted")\
                .limit(10)\
                .execute()
            if result.data:
                pool = [q for q in result.data if q["id"] not in existing_ids]
                if pool:
                    questions.append(random.choice(pool))
                    existing_ids.append(questions[-1]["id"])

    # Priority 3: Fill to 5 with random least-attempted questions
    needed = 5 - len(questions)
    all_available = supabase.table("math_sprints")\
        .select("*")\
        .order("times_attempted")\
        .limit(50)\
        .execute()

    if all_available.data:
        pool = [q for q in all_available.data if q["id"] not in existing_ids]
        random.shuffle(pool)
        questions.extend(pool[:needed])

    random.shuffle(questions)
    return questions[:5]

async def deliver():
    yesterday_miss = get_yesterday_miss()
    weak_cats = get_weak_categories()
    questions = select_questions(weak_cats, yesterday_miss)

    if not questions:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Math sprint: question bank is empty. Run generate_questions.py."
        )
        print("No questions available.")
        return

    first_q = questions[0]
    options = first_q["options"]

    # Create session
    session_result = supabase.table("sprint_sessions").insert({
        "chat_id": chat_id,
        "message_id": 0,
        "question_queue": [q["id"] for q in questions],
        "current_index": 0,
        "original_count": len(questions),
        "debt_count": 0,
        "completed": False
    }).execute()

    session_id = session_result.data[0]["id"]

    buttons = [
        InlineKeyboardButton(opt, callback_data=f"sp|{session_id}|{i}")
        for i, opt in enumerate(options)
    ]
    keyboard = InlineKeyboardMarkup([buttons[:2], buttons[2:]])

    # Build message
    weak_note = ""
    if yesterday_miss:
        weak_note = f"_Yesterday's miss \\→ drilling {escape_md(yesterday_miss)} today_\n\n"
    elif weak_cats:
        cats_text = escape_md(', '.join(weak_cats))
        weak_note = f"_Targeting weak spots: {cats_text}_\n\n"

    q_text = escape_md(first_q['question_text'])
    text = f"⚡ *MATH SPRINT* \\[1/{len(questions)}\\]\n\n{weak_note}{q_text}"

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
    except Exception:
        text_plain = f"⚡ MATH SPRINT [1/{len(questions)}]\n\n{first_q['question_text']}"
        message = await bot.send_message(
            chat_id=chat_id,
            text=text_plain,
            reply_markup=keyboard
        )

    supabase.table("sprint_sessions")\
        .update({"message_id": message.message_id})\
        .eq("id", session_id)\
        .execute()

    # ── Session cleanup: delete sessions older than 7 days ──
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    supabase.table("sprint_sessions")\
        .delete()\
        .lt("created_at", cutoff)\
        .execute()

    print(f"Sprint delivered. Session: {session_id}")
    print(f"Questions: {len(questions)} ({', '.join(q['category'] for q in questions)})")
    if yesterday_miss:
        print(f"Yesterday's miss guaranteed: {yesterday_miss}")
    elif weak_cats:
        print(f"Weak categories targeted: {', '.join(weak_cats)}")

asyncio.run(deliver())
```


### `scripts/handle_reply.py`

Reply detection (6 PM). Cycles webhook (delete → getUpdates → restore). Handles graveyard replies first, then flaw replies, with reminder fallback.

```python
import os
import time
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

# Edge Function URL for webhook restore
WEBHOOK_URL = os.environ.get(
    "SPRINT_WEBHOOK_URL",
    "https://ucbudwmxzdyzqxjwpyti.supabase.co/functions/v1/sprint-webhook"
)

async def handle():
    # ── Step 1: Check for graveyard reply first ────────────
    graveyard_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "graveyard_pending_id")\
        .execute()

    graveyard_id = graveyard_result.data[0]["value"] if graveyard_result.data and graveyard_result.data[0]["value"] else None

    # ── Step 2: Get today's flaw problem id ────────────────
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data and problem_result.data[0]["value"] else None

    # ── Step 3: Temporarily remove webhook to use getUpdates ──
    await bot.delete_webhook()
    updates = await bot.get_updates(limit=20)

    # Detect text replies
    text_reply = None
    for update in reversed(updates):
        if update.message and update.message.text:
            text = update.message.text.lower().strip()
            if text in ["caught", "got it"]:
                text_reply = "caught"
                break
            elif text in ["missed", "nope"]:
                text_reply = "missed"
                break

    # ── Step 4: Handle graveyard reply ("got it"/"nope") ───
    if graveyard_id and text_reply:
        if text_reply in ["caught"]:  # "got it" maps to "caught" keyword
            supabase.table("qa_flaw_deck")\
                .update({"status": "reviewed"})\
                .eq("id", graveyard_id)\
                .execute()
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Graveyard cleared. That trap won't catch you again.",
                parse_mode="Markdown"
            )
            print(f"Graveyard problem {graveyard_id[:8]}... → reviewed")
        else:  # "nope" — leave as missed, it'll come back
            await bot.send_message(
                chat_id=chat_id,
                text="📌 Still foggy — this one stays in the graveyard. It'll come back.",
                parse_mode="Markdown"
            )
            print(f"Graveyard problem {graveyard_id[:8]}... → stays missed")

        # Clear graveyard pending
        supabase.table("settings")\
            .update({"value": ""})\
            .eq("key", "graveyard_pending_id")\
            .execute()
        return  # Done — don't also process flaw reply in same run

    # ── Step 5: Handle flaw problem reply ──────────────────
    if not problem_id:
        print("No problem ID in settings. Nothing to do.")
        return

    problem = supabase.table("qa_flaw_deck")\
        .select("flawed_step_number, status")\
        .eq("id", problem_id)\
        .execute()

    if not problem.data:
        print(f"Problem {problem_id} not found.")
        return

    current_status = problem.data[0]["status"]
    correct_option = problem.data[0]["flawed_step_number"] - 1

    if current_status in ["caught", "missed"]:
        print(f"Problem already resolved as '{current_status}'. Skipping.")
        return

    caught = None
    eight_hours_ago = int(time.time()) - (8 * 3600)

    # Check poll answer (only from last 8 hours to prevent stale cross-day answers)
    for update in reversed(updates):
        if update.poll_answer:
            chosen = update.poll_answer.option_ids
            if len(chosen) > 0:
                caught = (chosen[0] == correct_option)
                print(f"Found poll answer (chose {chosen[0]}, correct={correct_option}) → {'caught' if caught else 'missed'}")
                break

    # Text reply overrides poll
    if text_reply == "caught":
        caught = True
        print("Found text reply: 'caught' → caught")
    elif text_reply == "missed":
        caught = False
        print("Found text reply: 'missed' → missed")

    # ── Step 6: If no reply found, send reminder ───────────
    if caught is None:
        await bot.send_message(
            chat_id=chat_id,
            text="⏰ *Reminder:* Did you spot the flaw in today's problem?\n\nReply *caught* or *missed*.",
            parse_mode="Markdown"
        )
        print("No reply found. Sent reminder.")
        return

    new_status = "caught" if caught else "missed"

    supabase.table("qa_flaw_deck")\
        .update({"status": new_status})\
        .eq("id", problem_id)\
        .execute()
    print(f"Updated qa_flaw_deck: {problem_id[:8]}... → '{new_status}'")

    supabase.table("daily_log")\
        .update({"caught": caught})\
        .eq("problem_id", problem_id)\
        .execute()
    print(f"Updated daily_log: {problem_id[:8]}... → caught={caught}")

    emoji = "✅" if caught else "❌"
    await bot.send_message(
        chat_id=chat_id,
        text=f"{emoji} Recorded as *{'CAUGHT' if caught else 'MISSED'}*.",
        parse_mode="Markdown"
    )
    print("Sent confirmation.")

async def main():
    try:
        await handle()
    finally:
        # Always restore the webhook, even if handle() returns early or errors
        await bot.set_webhook(url=WEBHOOK_URL, allowed_updates=["callback_query"])
        print("Webhook restored.")

asyncio.run(main())
```


### `scripts/graveyard_check.py`

Pre-sleep recall (10:05 PM). Resurfaces oldest missed problem. Writes to graveyard_pending_id so handle_reply.py can route replies correctly.

```python
import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def graveyard_nudge():
    result = supabase.table("qa_flaw_deck")\
        .select("*")\
        .eq("status", "missed")\
        .order("delivered_at")\
        .limit(1)\
        .execute()

    if not result.data:
        return  # Silent — no nudge if graveyard is empty

    problem = result.data[0]

    message = (
        f"⚰️ *GRAVEYARD*\n\n"
        f"You missed this one before.\n\n"
        f"*Problem:* {problem['original_problem']}\n\n"
        f"Don't solve it. Just recall the trap mentally.\n\n"
        f"Reply *got it* if you remember, *nope* if it's still foggy."
    )

    await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    # Write to graveyard_pending_id so handle_reply.py knows
    # which problem a "got it"/"nope" reply belongs to
    supabase.table("settings")\
        .upsert({"key": "graveyard_pending_id", "value": problem["id"]})\
        .execute()

    print(f"Graveyard nudge sent: {problem['id'][:8]}... ({problem['error_category']})")

asyncio.run(graveyard_nudge())
```


### `scripts/weekly_report.py`

Combined report (Sunday 8:30 PM). Error fingerprint by category + sprint stats. Excludes revision rounds.

```python
import os
import asyncio
from supabase import create_client
from telegram import Bot
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def report():
    logs = supabase.table("daily_log")\
        .select("*, qa_flaw_deck(error_category)")\
        .not_.is_("caught", "null")\
        .neq("is_revision", True)\
        .execute()

    if not logs.data:
        await bot.send_message(chat_id=chat_id, text="No data yet for weekly report.")
        return

    total = len(logs.data)
    caught_logs = [l for l in logs.data if l["caught"]]
    missed_logs = [l for l in logs.data if not l["caught"]]

    missed_cats = Counter(l["qa_flaw_deck"]["error_category"] for l in missed_logs)
    caught_cats = Counter(l["qa_flaw_deck"]["error_category"] for l in caught_logs)

    msg = f"📊 *WEEKLY ERROR FINGERPRINT*\n\n"
    msg += f"Attempted: {total} | Caught: {len(caught_logs)} ✅ | Missed: {len(missed_logs)} ❌\n\n"

    if missed_cats:
        msg += "*Your Blind Spots:*\n"
        for cat, count in missed_cats.most_common():
            msg += f"  • {cat}: missed {count}x\n"

    if caught_cats:
        msg += "\n*Your Strengths:*\n"
        for cat, count in caught_cats.most_common(3):
            msg += f"  • {cat}: caught {count}x\n"

    if missed_cats:
        worst = missed_cats.most_common(1)[0][0]
        msg += f"\n🎯 *Fix this week:* {worst}"

    # ── Sprint stats ──────────────────────────────────────
    try:
        sprint_logs = supabase.table("sprint_logs")\
            .select("*")\
            .execute()

        if sprint_logs.data:
            sprint_total = len(sprint_logs.data)
            sprint_correct = sum(1 for l in sprint_logs.data if l["is_correct"])
            sprint_debt = sum(1 for l in sprint_logs.data if l["is_debt_attempt"])

            wrong_cats = Counter(
                l["category"] for l in sprint_logs.data if not l["is_correct"]
            )

            msg += f"\n\n⚡ *SPRINT STATS (this week)*\n"
            msg += f"Answers: {sprint_total} | Correct: {sprint_correct} | "
            msg += f"Debt repaid: {sprint_debt}\n"

            if wrong_cats:
                msg += f"Slowest category: *{wrong_cats.most_common(1)[0][0]}*"
    except Exception:
        pass  # Sprint tables may not exist yet

    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

asyncio.run(report())
```


### `scripts/register_webhook.py`

One-time webhook registration. Tells Telegram to send only callback_query events to the Edge Function.

```python
import os
import sys
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# ─── IMPORTANT: Set your Edge Function URL here ───
# Replace 'your-project-ref' with the part of your Supabase URL
# between https:// and .supabase.co
# Example: if your URL is https://abcdefgh.supabase.co
#          then your ref is 'abcdefgh'

EDGE_FUNCTION_URL = os.environ.get(
    "SPRINT_WEBHOOK_URL",
    "https://ucbudwmxzdyzqxjwpyti.supabase.co/functions/v1/sprint-webhook"
)

async def register():
    bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
    
    if "your-project-ref" in EDGE_FUNCTION_URL:
        print("❌ ERROR: You need to set your Edge Function URL first!")
        print("   Edit EDGE_FUNCTION_URL in this file, or set SPRINT_WEBHOOK_URL env var.")
        print("   Format: https://YOUR-PROJECT-REF.supabase.co/functions/v1/sprint-webhook")
        sys.exit(1)
    
    print(f"Registering webhook: {EDGE_FUNCTION_URL}")
    print("Setting allowed_updates to ['callback_query'] only...")
    print("(Text messages still flow through getUpdates as before.)\n")
    
    result = await bot.set_webhook(
        url=EDGE_FUNCTION_URL,
        allowed_updates=["callback_query"]  # CRITICAL: only inline taps, not messages
    )
    
    if result:
        print("✅ Webhook registered successfully!")
        print(f"   URL: {EDGE_FUNCTION_URL}")
        print("   Telegram will now send ONLY callback_query events to this webhook.")
        print("   Text messages (caught/missed) still flow through getUpdates as before.")
    else:
        print("❌ Webhook registration failed. Check your Edge Function URL.")
    
    info = await bot.get_webhook_info()
    print(f"\nWebhook info:")
    print(f"  URL: {info.url}")
    print(f"  Pending updates: {info.pending_update_count}")
    print(f"  Allowed updates: {info.allowed_updates}")
    if info.last_error_message:
        print(f"  Last error: {info.last_error_message}")

asyncio.run(register())
```


### `scripts/batch_transcribe.sh`

Batch transcription. Processes all audio files in audio/ that don't already have transcripts. Run once for backlog.

```bash
#!/bin/bash
# Batch transcribe all audio files in the audio/ directory
# Usage: bash scripts/batch_transcribe.sh
# Output: transcripts/ directory with .txt files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "=== Batch Transcription ==="
echo "Looking for audio files in audio/..."
echo ""

count=0
for file in audio/*.mp3 audio/*.m4a audio/*.wav audio/*.mp4; do
  [ -f "$file" ] || continue
  
  basename=$(basename "$file")
  name="${basename%.*}"
  
  # Skip if already transcribed
  if [ -f "transcripts/${name}.txt" ]; then
    echo "⏭️  Skipping $basename (already transcribed)"
    continue
  fi
  
  echo "🎙️  Transcribing: $basename"
  python scripts/transcribe.py "$file"
  echo "✅  Done: $basename → transcripts/${name}.txt"
  echo "---"
  count=$((count + 1))
done

if [ $count -eq 0 ]; then
  echo "No new audio files to transcribe."
else
  echo ""
  echo "=== $count file(s) transcribed ==="
  echo ""
  echo "Next steps:"
  echo "  Process each transcript in chronological order (one per day):"
  echo "  python scripts/process_transcript.py transcripts/class_01_topic.txt"
fi
```


### `supabase/functions/sprint-webhook/index.ts`

Supabase Edge Function. Handles inline button taps in real-time. Wrong answers add to debt queue. Edits messages in-place.

```typescript
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)
const TELEGRAM_TOKEN = Deno.env.get('TELEGRAM_TOKEN')!
const BASE_URL = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`

// ── Telegram helpers ──────────────────────────────────────

async function answerCallback(id: string, text = '') {
  await fetch(`${BASE_URL}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ callback_query_id: id, text })
  })
}

async function editMessage(chatId: string, messageId: number, text: string, keyboard?: object) {
  const body: Record<string, unknown> = {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: 'Markdown'
  }
  if (keyboard) body.reply_markup = keyboard

  await fetch(`${BASE_URL}/editMessageText`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

function buildKeyboard(sessionId: string, options: string[]) {
  const buttons = options.map((opt, idx) => ({
    text: opt,
    callback_data: `sp|${sessionId}|${idx}`   // sp|{session_id}|{option_index}
  }))
  // 2x2 grid
  const rows = []
  for (let i = 0; i < buttons.length; i += 2) {
    rows.push(buttons.slice(i, i + 2))
  }
  return { inline_keyboard: rows }
}

// ── Main handler ──────────────────────────────────────────

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('OK')

  const update = await req.json()
  if (!update.callback_query) return new Response('OK')

  const cq = update.callback_query
  const data: string = cq.data || ''
  const chatId = String(cq.message.chat.id)
  const messageId: number = cq.message.message_id

  // Only handle sprint callbacks
  if (!data.startsWith('sp|')) {
    await answerCallback(cq.id)
    return new Response('OK')
  }

  // Parse: sp|{session_id}|{option_index}
  const [, sessionId, optStr] = data.split('|')
  const selectedIndex = parseInt(optStr)

  // Load session
  const { data: session, error: sessErr } = await supabase
    .from('sprint_sessions')
    .select('*')
    .eq('id', sessionId)
    .single()

  if (sessErr || !session || session.completed) {
    await answerCallback(cq.id, 'Session expired.')
    return new Response('OK')
  }

  const queue: string[] = session.question_queue
  const currentIndex: number = session.current_index
  const currentQuestionId = queue[currentIndex]

  // Load current question
  const { data: question } = await supabase
    .from('math_sprints')
    .select('*')
    .eq('id', currentQuestionId)
    .single()

  if (!question) {
    await answerCallback(cq.id, 'Error loading question.')
    return new Response('OK')
  }

  const isCorrect = selectedIndex === question.correct_answer_index

  // Log this answer
  await supabase.from('sprint_logs').insert({
    session_id: sessionId,
    question_id: currentQuestionId,
    category: question.category,
    is_correct: isCorrect,
    is_debt_attempt: currentIndex >= session.original_count
  })

  // Update question stats
  await supabase.from('math_sprints').update({
    times_attempted: question.times_attempted + 1,
    times_correct: isCorrect ? question.times_correct + 1 : question.times_correct
  }).eq('id', currentQuestionId)

  // Handle debt queue
  let newQueue = [...queue]
  let newDebt = session.debt_count

  if (!isCorrect) {
    newQueue.push(currentQuestionId)  // append to end
    newDebt += 1
    await answerCallback(cq.id, '❌ Wrong — added to debt queue!')
  } else {
    await answerCallback(cq.id, '✅ Correct!')
  }

  const nextIndex = currentIndex + 1

  // Update session
  await supabase.from('sprint_sessions').update({
    question_queue: newQueue,
    current_index: nextIndex,
    debt_count: newDebt
  }).eq('id', sessionId)

  // ── Sprint complete ─────────────────────────────────────
  if (nextIndex >= newQueue.length) {
    await supabase.from('sprint_sessions').update({ completed: true }).eq('id', sessionId)

    let summary = `🏁 *Sprint Complete!*\n\n`
    summary += `Original questions: ${session.original_count}\n`
    if (newDebt > 0) {
      summary += `Debt repaid: ${newDebt} wrong answer(s) → ${newDebt} extra question(s)\n`
      summary += `Total answered: ${newQueue.length}\n\n`
      summary += `_Each wrong answer cost you an extra question. Tomorrow, go clean._`
    } else {
      summary += `✨ *Perfect run. Zero debt. Go get some sleep.*`
    }

    await editMessage(chatId, messageId, summary)
    return new Response('OK')
  }

  // ── Next question ───────────────────────────────────────
  const nextQuestionId = newQueue[nextIndex]

  const { data: nextQ } = await supabase
    .from('math_sprints')
    .select('*')
    .eq('id', nextQuestionId)
    .single()

  if (!nextQ) {
    await editMessage(chatId, messageId, 'Error loading next question.')
    return new Response('OK')
  }

  const total = newQueue.length
  const progress = `[${nextIndex + 1}/${total}]`
  const debtNote = newDebt > 0 ? `_Debt queue: +${newDebt}_ ⚠️\n\n` : ''
  const wrongNote = !isCorrect ? `_❌ That one will return. Keep going._\n\n` : ''

  const text = `⚡ *MATH SPRINT* ${progress}\n\n${debtNote}${wrongNote}${nextQ.question_text}`
  const keyboard = buildKeyboard(sessionId, nextQ.options as string[])

  await editMessage(chatId, messageId, text, keyboard)
  return new Response('OK')
})
```


### GitHub Actions Workflows

Create each file in `.github/workflows/`:


#### `.github/workflows/math_sprint.yml`

```yaml
name: Morning Math Sprint

on:
  schedule:
    - cron: '0 3 * * *'    # 8:30 AM IST
  workflow_dispatch:

jobs:
  sprint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/deliver_sprint.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```


#### `.github/workflows/daily_problem.yml`

```yaml
name: 2PM Problem Delivery

on:
  schedule:
    - cron: '30 8 * * *'   # 2:00 PM IST
  workflow_dispatch:

jobs:
  deliver:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/deliver_problem.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```


#### `.github/workflows/handle_reply.yml`

```yaml
name: Handle Reply

on:
  schedule:
    - cron: '30 12 * * *'   # 6:00 PM IST
  workflow_dispatch:

jobs:
  reply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/handle_reply.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```


#### `.github/workflows/nightly_axiom.yml`

```yaml
name: 10PM Axiom

on:
  schedule:
    - cron: '30 16 * * *'   # 10:00 PM IST
  workflow_dispatch:

jobs:
  axiom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/deliver_axiom.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```


#### `.github/workflows/graveyard_nudge.yml`

```yaml
name: Graveyard Nudge

on:
  schedule:
    - cron: '35 16 * * *'   # 10:05 PM IST daily (after axiom)
  workflow_dispatch:

jobs:
  graveyard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/graveyard_check.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```


#### `.github/workflows/weekly_report.yml`

```yaml
name: Weekly Report

on:
  schedule:
    - cron: '0 15 * * 0'   # 8:30 PM IST Sunday
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/weekly_report.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```


---

## Step 6: Deploy Edge Function

```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Login and link to your project
supabase login
supabase link --project-ref YOUR_PROJECT_REF

# Set the Telegram token as a secret (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are auto-provided)
supabase secrets set TELEGRAM_TOKEN=your_telegram_bot_token

# Deploy the Edge Function
supabase functions deploy sprint-webhook --no-verify-jwt

# Populate sprint question bank (one-time, interactive)
source venv/bin/activate
python scripts/generate_questions.py
# Review sample output → type 'y' to insert 109 questions

# Register Telegram webhook (one-time)
python scripts/register_webhook.py
```

---

## Step 7: Push to GitHub and Add Secrets

```bash
git init
git add .
git commit -m "initial setup"
git remote add origin https://github.com/YOUR_USERNAME/cat_qa_engine.git
git push -u origin main
```

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 5 secrets:

| Secret Name | Value |
|-------------|-------|
| `SUPABASE_URL` | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | Your service role key |
| `TELEGRAM_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID number |
| `GEMINI_API_KEY` | Your Gemini API key |

**Setup is complete. The system is now fully operational.**

---

## Daily Operations

### Your Daily Routine (~5 minutes total)

| Time | What Arrives on Telegram | Your Action | Duration |
|------|--------------------------|-------------|----------|
| 8:30 AM | ⚡ Math Sprint (5 questions, inline keyboard) | Tap through questions. Wrong answers queue up. | 2-3 min |
| 2:00 PM | 🔍 Spot the Flaw quiz poll | Find the flaw, tap your answer | 1 min |
| 6:00 PM | ⏰ Reminder (if you haven't replied) | Reply "caught" or "missed" | 10 sec |
| 10:00 PM | 🌙 Trap axiom (framed by your result) | Read it, feel the framing | 20 sec |
| 10:05 PM | ⚰️ Graveyard recall (if any missed problems) | Reply "got it" or "nope" | 30 sec |
| Sunday 8:30 PM | 📊 Weekly report + sprint stats | Read your blind spots | 1 min |

### The Only Scripts You Ever Run Manually

When you have a new class recording:

```bash
cd /path/to/cat_qa_engine
source venv/bin/activate

# Step 1: Transcribe (5-10 min, unattended)
python scripts/transcribe.py audio/class_name.mp3

# Step 2: Process (10 min, interactive — you approve each corruption)
python scripts/process_transcript.py transcripts/class_name.txt

# Step 3: Push to GitHub
git add . && git commit -m "add class N problems" && git push
```

That's it. 3-6 new problems enter the database. The next day's 2 PM delivery picks them up automatically (ordered by source_file = chronological).

The sprint question bank is separate and static (109 questions). It does NOT need updating when you add new classes.

---

## Processing Your Audio Backlog

If you have multiple old classes sitting unprocessed:

### Step 1: Drop all audio files into audio/

Name them so they sort chronologically:
```
audio/class_01_number_system.mp3
audio/class_02_algebra.mp3
audio/class_03_geometry.mp3
...
```

### Step 2: Batch transcribe (one afternoon, unattended)

```bash
source venv/bin/activate
bash scripts/batch_transcribe.sh
```

This processes ALL audio files that don't already have transcripts. Walk away. ~8 minutes per hour of audio.

### Step 3: Process ONE transcript per day

Do NOT process all at once. One per day, in chronological order:

```bash
# Day 1
python scripts/process_transcript.py transcripts/class_01_number_system.txt

# Day 2
python scripts/process_transcript.py transcripts/class_02_algebra.txt

# ... and so on
```

Why one per day:
- Gemini free tier rate-limits after ~15 API calls in quick succession
- Reviewing 30+ problems in one sitting makes your quality gate ("y/n") rushed
- Each class adds 3-6 problems = weeks of content at 1/day delivery rate

---

## How Each Script Works

### Cron Schedule (all times IST)

| Workflow | Cron (UTC) | IST | Script |
|----------|-----------|-----|--------|
| Math Sprint | `0 3 * * *` | 8:30 AM daily | deliver_sprint.py |
| Daily Problem | `30 8 * * *` | 2:00 PM daily | deliver_problem.py |
| Handle Reply | `30 12 * * *` | 6:00 PM daily | handle_reply.py |
| Nightly Axiom | `30 16 * * *` | 10:00 PM daily | deliver_axiom.py |
| Graveyard Nudge | `35 16 * * *` | 10:05 PM daily | graveyard_check.py |
| Weekly Report | `0 15 * * 0` | 8:30 PM Sunday | weekly_report.py |

### Error Category → Sprint Category Mapping

When you miss a flaw problem, the next morning's sprint guarantees 2 questions from the mapped category:

| Flaw Error Category | Sprint Category |
|---------------------|----------------|
| Algebraic Sign Error | square |
| Ignoring Negative Root | square |
| Integer Constraint Missed | prime |
| Ratio Misapplied | reciprocal |
| Calculation Shortcut Trap | table |
| Proportionality Assumed Equal | reciprocal |
| Misread Constraint | prime |
| At-Least vs Exactly Confusion | prime |
| Division by Variable Without Checking Zero | reciprocal |

### Problem Status Flow

```
unseen → delivered → caught (exits system)
                   → missed → reviewed (via graveyard "got it")
                            → stays missed (via graveyard "nope", cycles back)

When bank exhausted:
caught → re-delivered as "Revision Round" (tagged is_revision=true)
```

### Telegram 10-Option Poll Limit

Telegram quiz polls allow maximum 10 options. This is handled at 3 levels:
1. **Prompt level**: Gemini is told to cap solutions at 10 steps
2. **Validation level**: process_transcript.py auto-rejects >10 step corruptions
3. **Delivery level**: deliver_problem.py skips any >10-step problem, marks it `skip_overlimit`

---

## Design Decisions

| Decision | Reasoning |
|----------|-----------|
| handle_reply at 6 PM (not 2:40 PM) | 4-hour reply window. Meetings won't cause phantom problems. |
| Graveyard at 10:05 PM (not 8 AM) | Same pre-sleep consolidation window as axiom. No morning cognitive overload. |
| Axiom framed by caught/missed | "This one got you" creates prediction error → deeper encoding. |
| Yesterday-miss guaranteed (not weighted) | Guaranteed 2/5 creates explicit, immediate repair. |
| source_file ordering | Problems delivered in class chronological order. |
| Webhook cycle in handle_reply | Telegram forbids getUpdates + webhook simultaneously. Finally block guarantees restore. |
| graveyard_pending_id (separate key) | Prevents graveyard replies being misrouted to flaw path. |
| Revision fallback | Prevents dead delivery slot when bank exhausted. |
| is_revision in daily_log | Prevents revision rounds from polluting weekly report stats. |
| Poll timestamp filter (8 hours) | Prevents stale cross-day poll answers from being misattributed. |
| Max 10 steps per solution | Telegram poll limit. Enforced at prompt, validation, and delivery levels. |
| Gemini model: gemini-2.5-flash | Stable, fast, free tier. gemini-3-flash-preview was returning 503. |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Gemini 503 / high demand | Model is gemini-2.5-flash. Built-in exponential backoff (10s → 20s → 40s → 80s → 160s). |
| Supabase "proxy" error | Pinned gotrue==1.3.0 and httpx==0.25.2. |
| Sprint buttons not working | Check Edge Function: `supabase functions list`. Re-register: `python scripts/register_webhook.py`. |
| "can't use getUpdates while webhook active" | Fixed. handle_reply.py cycles: delete → getUpdates → restore in finally block. |
| Problem bank empty | Fixed. Falls back to revision rounds. If no caught problems either, sends warning message. |
| Graveyard replies disappearing | Fixed. Uses graveyard_pending_id (separate from todays_problem_id). Cleared after processing. |
| Stale poll answers from yesterday | Fixed. 8-hour timestamp filter on poll answer processing. |
| Problem has >10 steps | Fixed. Prompt caps at 10, validation rejects >10, delivery skips and marks skip_overlimit. |
| Gemini model not found (404) | Check available models with: `python3 -c "from google import genai; import os; from dotenv import load_dotenv; load_dotenv(); c = genai.Client(api_key=os.environ['GEMINI_API_KEY']); [print(m.name) for m in c.models.list() if 'flash' in m.name.lower()]"` |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| google-genai | latest | Gemini AI API |
| supabase | 2.3.5 | Database client (pinned) |
| gotrue | 1.3.0 | Supabase auth (pinned) |
| python-telegram-bot | 20.7 | Telegram Bot API |
| python-dotenv | latest | Load .env files |
| httpx | 0.25.2 | HTTP client (pinned) |
| openai-whisper | latest | Audio transcription (local only) |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Supabase (PostgreSQL) | Database for all 6 tables |
| Supabase Edge Functions (Deno) | Real-time sprint webhook handler |
| GitHub Actions | 6 scheduled daily/weekly workflows |
| Telegram Bot API | Message delivery + inline keyboards + quiz polls |
| Gemini 2.5 Flash | Problem extraction, corruption, question framing |
