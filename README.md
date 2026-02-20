# CAT QA Engine 🎯

> A two-system CAT prep engine: **Spot the Flaw** (corrupted solutions + spaced repetition) + **Math Sprint** (speed drills with debt queues). Fully automated via GitHub Actions + Supabase Edge Functions + Telegram.

---

## Table of Contents
1. [What This App Does](#what-this-app-does)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Step 1: Create Supabase Project](#step-1-create-supabase-project)
5. [Step 2: Create Telegram Bot](#step-2-create-telegram-bot)
6. [Step 3: Get Gemini API Key](#step-3-get-gemini-api-key)
7. [Step 4: Set Up Your Mac](#step-4-set-up-your-mac)
8. [Step 5: Configure Environment](#step-5-configure-environment)
9. [Step 6: Push to GitHub](#step-6-push-to-github)
10. [Step 7: Add GitHub Secrets](#step-7-add-github-secrets)
11. [How Each Script Works](#how-each-script-works)
12. [All Prompts Used](#all-prompts-used)
13. [Daily Workflow](#daily-workflow)
14. [Cron Schedule](#cron-schedule)
15. [Troubleshooting](#troubleshooting)

---

## What This App Does

Two interconnected systems, one brain, zero overlap:

### System 1: Spot the Flaw (Afternoon)
You record your CAT class audio. This app:
1. **Transcribes** it using OpenAI Whisper (locally on your Mac)
2. **Extracts** every solved math problem from the transcript using Gemini AI
3. **Corrupts** one step in each solution with a subtle, realistic error
4. **Stores** everything in a Supabase database
5. **Delivers** one "Spot the Flaw" quiz poll to your Telegram every day at 2 PM
6. **Auto-detects** whether you caught the flaw or missed it (from your poll answer)
7. **Sends** the underlying trap axiom at 10 PM as a bedtime thought
8. **Resurfaces** missed problems on Mon/Wed/Fri mornings (graveyard nudge)

### System 2: Math Sprint (Morning)
9. **Generates** 109 contextual math flashcards (reciprocals, squares, cubes, primes, tables)
10. **Delivers** 5-question speed drills at 8:30 AM with inline keyboard buttons
11. **Wrong answers add debt** — each miss adds that question back to the end of the queue
12. **Real-time interaction** via Supabase Edge Function — messages edit in-place, no page refresh
13. **Targets your weak spots** — sprint questions are calibrated by your flaw-detection errors

### Weekly Report
14. **Sends** a combined error fingerprint + sprint stats report every Sunday

Everything is **fully automated** via GitHub Actions + Supabase Edge Functions.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   YOUR MAC (Local)                    │
│                                                       │
│  audio/*.mp3/m4a  ──→  transcribe.py (Whisper)        │
│                            │                          │
│                            ▼                          │
│  transcripts/*.txt  ──→  process_transcript.py        │
│                          (3 Gemini API calls)         │
│                            │                          │
│  generate_questions.py  ──┤  (one-time, 109 questions)│
│                            ▼                          │
│                      Supabase Database                │
└──────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  GITHUB ACTIONS  │ │  SUPABASE    │ │  TELEGRAM        │
│  (Scheduled)     │ │  EDGE FUNC   │ │  (Your Phone)    │
│                  │ │              │ │                  │
│  deliver_problem │ │  sprint-     │ │  Quiz polls      │
│  handle_reply    │ │  webhook     │ │  Inline buttons  │
│  deliver_axiom   │ │  (real-time  │ │  Sprint drills   │
│  deliver_sprint  │ │   button     │ │  Axioms          │
│  graveyard_check │ │   handler)   │ │  Reports         │
│  weekly_report   │ │              │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

---

## Prerequisites

- A Mac with Python 3.11+ installed
- A free [Supabase](https://supabase.com) account
- A [Telegram](https://telegram.org) account
- A [Google AI Studio](https://aistudio.google.com) account (for Gemini API key)
- A [GitHub](https://github.com) account
- `ffmpeg` installed (`brew install ffmpeg`)

---

## Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → Sign up → New Project
2. Name it `cat-qa-engine`, choose a region, set a database password
3. Wait for the project to be created
4. Go to **Settings → API** and copy:
   - **Project URL** (looks like `https://xxxxxx.supabase.co`)
   - **Service Role Key** (under "service_role", starts with `eyJ...`)

5. Go to **SQL Editor** and run this SQL to create ALL tables:

```sql
-- ═══════════════════════════════════════
-- SYSTEM 1: SPOT THE FLAW TABLES
-- ═══════════════════════════════════════

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
  caught boolean
);

create table settings (
  key text primary key,
  value text
);

insert into settings (key, value) values ('todays_problem_id', '');
insert into settings (key, value) values ('todays_axiom', '');

-- ═══════════════════════════════════════
-- SYSTEM 2: MATH SPRINT TABLES
-- ═══════════════════════════════════════

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

### Database Schema Explained

| Table | System | Purpose |
|-------|--------|---------|
| `qa_flaw_deck` | Flaw | Problems with corrupted solutions (`unseen` → `delivered` → `caught`/`missed`) |
| `daily_log` | Flaw | One row per delivered problem, tracking if caught |
| `settings` | Flaw | Key-value store for today's problem ID and axiom |
| `math_sprints` | Sprint | 109 flashcard questions with options and correct answer index |
| `sprint_sessions` | Sprint | Active sprint sessions with question queue and debt counter |
| `sprint_logs` | Sprint | Per-answer log for analytics (correct/wrong, category, debt attempt) |

---

## Step 2: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "QA CAT Tutor")
4. Choose a username (e.g., `qa_cat_tutor_bot`)
5. Copy the **Bot Token** (looks like `1234567890:AAE2tkzzOC-dQCzZlXVQx4PRMCKmzo27ZlA`)
6. **Get your Chat ID**:
   - Search for **@userinfobot** on Telegram
   - Send it any message
   - It will reply with your chat ID (a number like `887984036`)

---

## Step 3: Get Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → Create API Key
3. Copy the key (starts with `AIza...`)

---

## Step 4: Set Up Your Mac

Open Terminal and run these commands one by one:

```bash
# Create project folder (or clone from GitHub)
mkdir cat_qa_engine
cd cat_qa_engine

# Create all directories
mkdir -p scripts transcripts audio .github/workflows

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install google-genai supabase==2.3.5 gotrue==1.3.0 python-telegram-bot==20.7 python-dotenv httpx==0.25.2

# Install Whisper (local transcription only)
pip install openai-whisper

# Install ffmpeg (needed by Whisper)
brew install ffmpeg
```

### Project Structure

```
cat_qa_engine/
├── audio/                          ← Drop class audio files here
├── transcripts/                    ← Transcripts auto-saved here
├── scripts/
│   ├── transcribe.py               ← Audio → text (Whisper, local)
│   ├── process_transcript.py       ← Extract + corrupt problems (Gemini → Supabase)
│   ├── generate_questions.py       ← One-time: populate 109 sprint questions
│   ├── deliver_problem.py          ← Daily quiz poll (Telegram)
│   ├── deliver_axiom.py            ← Nightly axiom (Telegram)
│   ├── deliver_sprint.py           ← Morning sprint with inline keyboard
│   ├── handle_reply.py             ← Detect poll answer, update DB
│   ├── graveyard_check.py          ← Resurface missed problems
│   ├── weekly_report.py            ← Combined flaw + sprint report
│   └── register_webhook.py         ← One-time: register Telegram webhook
├── supabase/
│   └── functions/
│       └── sprint-webhook/
│           └── index.ts            ← Edge Function: handles inline button taps
├── .github/
│   └── workflows/
│       ├── daily_problem.yml
│       ├── handle_reply.yml
│       ├── nightly_axiom.yml
│       ├── graveyard_nudge.yml
│       ├── weekly_report.yml
│       └── math_sprint.yml         ← Morning sprint delivery
├── .env                            ← Your credentials (DO NOT commit)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Step 5: Configure Environment

Create a `.env` file in the project root:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_service_role_key_here
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_gemini_api_key_here
```

Create a `.gitignore` file:

```
.env
venv/
__pycache__/
*.pyc
audio/
transcripts/*.txt
```

Create a `requirements.txt` file:

```
google-genai
supabase==2.3.5
gotrue==1.3.0
python-telegram-bot==20.7
python-dotenv
httpx==0.25.2
```

---

## Step 6: Push to GitHub

```bash
git init
git add .
git commit -m "initial setup"
git remote add origin https://github.com/YOUR_USERNAME/cat_qa_engine.git
git push -u origin main
```

---

## Step 7: Add GitHub Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 5 secrets one by one:

| Secret Name | Value |
|-------------|-------|
| `SUPABASE_URL` | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | Your service role key |
| `TELEGRAM_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID number |
| `GEMINI_API_KEY` | Your Gemini API key |

---

## How Each Script Works

### 1. `scripts/transcribe.py` — Audio → Text (Local Only)

**What it does**: Uses OpenAI Whisper to convert audio files to text transcripts.

**How to use**:
```bash
source venv/bin/activate
python scripts/transcribe.py audio/class_01_percentages.mp3
```

**Output**: Saves `transcripts/class_01_percentages.txt`

**Full code**:
```python
import whisper
import sys
import os

def transcribe(audio_path):
    print(f"Loading Whisper model...")
    model = whisper.load_model("base")  # use "small" for better accuracy

    print(f"Transcribing {audio_path}... this may take a few minutes.")
    result = model.transcribe(audio_path)

    # Always save to transcripts/ directory
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

---

### 2. `scripts/process_transcript.py` — The Intelligence Layer (Local Only)

**What it does**: Takes a transcript, makes 3 Gemini API calls to:
1. **Extract** every fully-solved problem from the transcript
2. **Sanitize** the solution steps for clarity
3. **Corrupt** one step with a subtle, realistic error

After each corruption, it shows you the result and asks `y/n` before saving to Supabase.

**How to use**:
```bash
python scripts/process_transcript.py transcripts/class_01_percentages.txt
```

**You review each problem** in the terminal and press `y` to save or `n` to skip. This quality gate takes ~2 minutes per class.

**Full code**: See [scripts/process_transcript.py](scripts/process_transcript.py) — includes all 3 Gemini prompts below.

---

### 3. `scripts/deliver_problem.py` — Daily Quiz (GitHub Actions)

**What it does**:
1. Picks one `unseen` problem from `qa_flaw_deck`
2. Sends the problem statement to Telegram
3. Sends a quiz poll with solution steps as options
4. Updates DB: status → `delivered`, logs in `daily_log`
5. Saves axiom and problem ID to `settings` for the nightly script

**Full code**: See [scripts/deliver_problem.py](scripts/deliver_problem.py)

---

### 4. `scripts/deliver_axiom.py` — Nightly Axiom (GitHub Actions)

**What it does**: Reads today's axiom from `settings` and sends it to Telegram as a bedtime thought.

**Full code**: See [scripts/deliver_axiom.py](scripts/deliver_axiom.py)

---

### 5. `scripts/handle_reply.py` — Auto-Detect Poll Answer (GitHub Actions)

**What it does**:
1. Reads your quiz poll answer from Telegram
2. Compares your chosen option to the correct flaw step
3. If correct → marks as `caught`; if wrong → marks as `missed`
4. Updates both `qa_flaw_deck.status` and `daily_log.caught`
5. Sends a ✅ or ❌ confirmation to Telegram

Also accepts text replies: "caught", "missed", "got it", "nope" (text overrides poll answer).

**Full code**: See [scripts/handle_reply.py](scripts/handle_reply.py)

---

### 6. `scripts/graveyard_check.py` — Missed Problem Nudge (GitHub Actions)

**What it does**:
1. Finds the oldest problem with status `missed`
2. Sends it to Telegram as a graveyard review
3. You reply "got it" (remembers the trap) or "nope" (still foggy)

**Full code**: See [scripts/graveyard_check.py](scripts/graveyard_check.py)

---

### 7. `scripts/weekly_report.py` — Combined Report (GitHub Actions)

**What it does**:
1. Queries all `daily_log` entries — aggregates by error category
2. Shows blind spots (most-missed) and strengths (most-caught)
3. **Sprint stats**: total answers, correct count, debt repaid, slowest category

**Full code**: See [scripts/weekly_report.py](scripts/weekly_report.py)

---

### 8. `scripts/generate_questions.py` — Question Bank (One-Time, Local)

**What it does**:
1. Generates 109 raw math questions across 5 categories programmatically
2. Wraps each question in a contextual business scenario using Gemini AI
3. Inserts all questions into `math_sprints` table

**Categories**: reciprocals (19), squares (30), cubes (15), primes (25), tables (20)

**How to use** (run once):
```bash
source venv/bin/activate
python scripts/generate_questions.py
# Review sample output → type 'y' to insert
```

---

### 9. `scripts/deliver_sprint.py` — Morning Sprint (GitHub Actions)

**What it does**:
1. Reads your missed flaw categories and maps them to sprint categories
2. Selects 5 questions: 2 from weak spots + 3 random (least-attempted first)
3. Creates a session in `sprint_sessions` with the question queue
4. Sends the first question with 4 inline keyboard buttons
5. Edge Function handles all subsequent button taps in real-time

**Debt queue mechanics**: Wrong answers are appended to the end of the queue. You must answer them all correctly before the sprint ends. Each wrong answer costs you one extra question.

---

### 10. `supabase/functions/sprint-webhook/index.ts` — Edge Function

**What it does** (runs on Supabase, always-on):
1. Receives inline keyboard taps via Telegram webhook
2. Checks if the selected option matches the correct answer
3. If wrong → appends question to debt queue, shows "❌ added to debt queue"
4. If right → shows "✅ Correct!"
5. **Edits the message in-place** with the next question (no new messages)
6. When all questions (including debt) are done → shows sprint summary
7. Logs every answer in `sprint_logs` for analytics

**Deployment** (one-time):
```bash
brew install supabase/tap/supabase
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase secrets set TELEGRAM_TOKEN=your_token
supabase functions deploy sprint-webhook --no-verify-jwt
```

---

### 11. `scripts/register_webhook.py` — Webhook Registration (One-Time)

**What it does**: Tells Telegram to send only `callback_query` events (inline button taps) to the Edge Function. Text messages still flow through `getUpdates` for `handle_reply.py`.

**Run once after deploying the Edge Function**:
```bash
python scripts/register_webhook.py
```

---

## All Prompts Used

### Prompt 1: Extract Problems from Transcript

```
You are analyzing a transcript of a CAT exam quantitative aptitude class.
The teacher explains concepts and solves problems out loud. Students attempt
problems and the teacher gives correct answers.

Task: Find every moment where a problem was fully solved by the teacher —
meaning the problem was stated AND the teacher walked through the complete solution.

For each such problem, extract:
a) The problem statement in clean mathematical language.
b) The teacher's solution as numbered logical steps. Each step is one clear
   mathematical action.

Rules:
- Do NOT solve anything yourself. Only extract what the teacher actually said and did.
- If a problem's explanation is incomplete or unclear, skip it entirely.
- Return a JSON array only. No text outside the JSON.
- Each element: {"problem_statement": "...", "solution_steps": ["step 1", "step 2", ...]}
```

### Prompt 2: Sanitize Solution Steps

```
Below is a math problem and solution steps extracted from a class transcript.
Clean up the language so each step is one precise mathematical action.
Do not change any numbers, logic, or mathematical operations. Only improve clarity.
Return the exact same JSON structure with cleaner language.
```

### Prompt 3: Introduce a Subtle Flaw

```
Below is a correct step-by-step solution to a math problem.
Your task: Introduce exactly one conceptual error into exactly one step.

The error must come from this list:
- Algebraic Sign Error
- Ignoring Negative Root
- Integer Constraint Missed
- Ratio Misapplied
- At-Least vs Exactly Confusion
- Division by Variable Without Checking Zero
- Proportionality Assumed Equal
- Calculation Shortcut Trap
- Misread Constraint

Rules:
- Make the error subtle — the kind a student under time pressure would miss.
- Steps after the corrupted step must follow logically from the corrupted step
  (as if the student continued with the wrong value).
- Do not make it obviously wrong.

Return a JSON object with these exact keys:
- "corrupted_steps": full solution array with one step silently changed
- "flaw_step_number": the 1-based index of the corrupted step (integer)
- "error_category": which category from the list you used
- "explanation": one sentence explaining exactly what was corrupted and why
- "trap_axiom": a single vivid sentence capturing the underlying rule being
  violated. No formulas. Pure logic. Slightly poetic but sharp.

Return only valid JSON. No text outside the JSON.
```

---

## Daily Workflow

### Your Complete Daily Routine (~5 min total)

| Time | What Arrives | Your Action | Duration |
|------|-------------|-------------|----------|
| 8:30 AM | ⚡ Math Sprint (5 questions, inline keyboard) | Tap through questions. Wrong answers queue up. | 2-3 min |
| 2:00 PM | 🔍 Spot the Flaw quiz poll | Find the flaw, tap your answer | 1 min |
| — | ✅/❌ Auto-detected result | Nothing — it's automatic | — |
| 10:00 PM | 🌙 Trap axiom | Read 20 seconds, sleep on it | 20 sec |
| Mon/Wed/Fri 8 AM | ⚰️ Graveyard nudge | Reply "got it" or "nope" | 30 sec |
| Sunday 8:30 PM | 📊 Weekly fingerprint + sprint stats | Read your blind spots | 1 min |

### When You Get a New Class Recording (~15 minutes)

```bash
# Step 1: Transcribe (unattended, ~5 min for a 1-hour recording)
source venv/bin/activate
python scripts/transcribe.py audio/class_name.mp3

# Step 2: Process (interactive, ~10 min — you review and press y/n)
python scripts/process_transcript.py transcripts/class_name.txt
```

---

## Cron Schedule

All times shown in IST (UTC+5:30).

| Workflow | Cron (UTC) | IST Equivalent | Script |
|----------|-----------|----------------|--------|
| **Math Sprint** | `0 3 * * *` | 8:30 AM daily | `deliver_sprint.py` |
| Daily Problem | `30 8 * * *` | 2:00 PM daily | `deliver_problem.py` |
| Handle Reply | `10 9 * * *` | 2:40 PM daily | `handle_reply.py` |
| Nightly Axiom | `30 16 * * *` | 10:00 PM daily | `deliver_axiom.py` |
| Graveyard Nudge | `30 2 * * 1,3,5` | 8:00 AM Mon/Wed/Fri | `graveyard_check.py` |
| Weekly Report | `0 15 * * 0` | 8:30 PM Sunday | `weekly_report.py` |

### GitHub Actions Workflow Files

Each YAML file in `.github/workflows/` follows this pattern:

```yaml
name: Workflow Name

on:
  schedule:
    - cron: 'CRON_EXPRESSION'
  workflow_dispatch:  # allows manual trigger

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/SCRIPT_NAME.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

---

## Troubleshooting

### "Rate limited" / 429 errors from Gemini
The free tier has usage limits. `process_transcript.py` has built-in retry with exponential backoff (waits 10s → 20s → 40s → 80s → 160s). If you keep hitting limits, wait 1 minute and try again.

### Transcript saved to wrong folder
Fixed. `transcribe.py` always saves to `transcripts/` regardless of how you specify the audio path.

### Supabase "proxy" error
Fixed by pinning `gotrue==1.3.0` and `httpx==0.25.2`. These are already in `requirements.txt`.

### Gemini model not found (404)
We use `gemini-3-flash-preview`. If this becomes unavailable, check available models:
```python
from google import genai
client = genai.Client(api_key="YOUR_KEY")
for m in client.models.list():
    if 'flash' in m.name.lower():
        print(m.name)
```

### GitHub Actions not running
- Verify all 5 secrets are added correctly
- Test each workflow manually using the "Run workflow" button
- Check the Actions tab for error logs

### Bot not sending messages
- Verify `TELEGRAM_CHAT_ID` is your personal chat ID (get it from @userinfobot)
- Make sure you've started the bot by sending `/start` to it on Telegram

### Sprint buttons not working
- Verify the Edge Function is deployed: `supabase functions list`
- Check Edge Function logs: Supabase Dashboard → Edge Functions → sprint-webhook → Logs
- Verify webhook is registered: `python scripts/register_webhook.py`
- If webhook broke `handle_reply.py`: the webhook only captures `callback_query`, not text messages

### Edge Function errors
- Check that `TELEGRAM_TOKEN` secret is set: `supabase secrets list`
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are auto-provided by Supabase runtime

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `google-genai` | latest | Gemini AI API (new SDK) |
| `supabase` | 2.3.5 | Database client |
| `gotrue` | 1.3.0 | Supabase auth (pinned for compatibility) |
| `python-telegram-bot` | 20.7 | Telegram Bot API |
| `python-dotenv` | latest | Load .env files |
| `httpx` | 0.25.2 | HTTP client (pinned for compatibility) |
| `openai-whisper` | latest | Audio transcription (local only) |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Supabase (PostgreSQL) | Database for all tables |
| Supabase Edge Functions (Deno) | Real-time sprint webhook handler |
| GitHub Actions | Scheduled daily/weekly script execution |
| Telegram Bot API | Message delivery + inline keyboards |
| Gemini 3 Flash Preview | Problem extraction, corruption, question framing |
