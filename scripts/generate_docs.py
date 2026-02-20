"""Generate complete self-contained Documentation.md from all source files."""
import os

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(path):
    with open(os.path.join(PROJECT, path)) as f:
        return f.read().strip()

def code_block(content, lang=""):
    return f"```{lang}\n{content}\n```"

sections = []

# ══════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════
sections.append("""# CAT QA Engine — Complete Clone-Ready Documentation

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
""")

# ══════════════════════════════════════════════════
# ALL SOURCE FILES
# ══════════════════════════════════════════════════

source_files = [
    ("scripts/transcribe.py", "python", "Audio → text transcription using OpenAI Whisper. Runs locally on your Mac."),
    ("scripts/process_transcript.py", "python", "The intelligence layer. Makes 3 Gemini API calls per problem: extract → sanitize → corrupt. Interactive — you approve each corruption before saving."),
    ("scripts/generate_questions.py", "python", "One-time script. Generates 109 raw math questions programmatically, wraps each in a contextual scenario via Gemini, and inserts into Supabase."),
    ("scripts/deliver_problem.py", "python", "Daily quiz delivery (2 PM). Picks unseen problems ordered by source_file (chronological). Falls back to revision rounds when bank is exhausted."),
    ("scripts/deliver_axiom.py", "python", "Nightly axiom delivery (10 PM). Checks daily_log for caught/missed and frames the message accordingly."),
    ("scripts/deliver_sprint.py", "python", "Morning sprint delivery (8:30 AM). Selects 5 questions with yesterday-miss guarantee and weak-spot weighting."),
    ("scripts/handle_reply.py", "python", "Reply detection (6 PM). Cycles webhook (delete → getUpdates → restore). Handles graveyard replies first, then flaw replies, with reminder fallback."),
    ("scripts/graveyard_check.py", "python", "Pre-sleep recall (10:05 PM). Resurfaces oldest missed problem. Writes to graveyard_pending_id so handle_reply.py can route replies correctly."),
    ("scripts/weekly_report.py", "python", "Combined report (Sunday 8:30 PM). Error fingerprint by category + sprint stats. Excludes revision rounds."),
    ("scripts/register_webhook.py", "python", "One-time webhook registration. Tells Telegram to send only callback_query events to the Edge Function."),
    ("scripts/batch_transcribe.sh", "bash", "Batch transcription. Processes all audio files in audio/ that don't already have transcripts. Run once for backlog."),
    ("supabase/functions/sprint-webhook/index.ts", "typescript", "Supabase Edge Function. Handles inline button taps in real-time. Wrong answers add to debt queue. Edits messages in-place."),
]

for filepath, lang, description in source_files:
    try:
        content = read(filepath)
        sections.append(f"### `{filepath}`\n\n{description}\n\n{code_block(content, lang)}\n")
    except FileNotFoundError:
        sections.append(f"### `{filepath}`\n\n{description}\n\n*(File not found)*\n")

# ══════════════════════════════════════════════════
# WORKFLOW FILES
# ══════════════════════════════════════════════════

sections.append("### GitHub Actions Workflows\n\nCreate each file in `.github/workflows/`:\n")

workflow_files = [
    "math_sprint.yml",
    "daily_problem.yml",
    "handle_reply.yml",
    "nightly_axiom.yml",
    "graveyard_nudge.yml",
    "weekly_report.yml",
]

for wf in workflow_files:
    try:
        content = read(f".github/workflows/{wf}")
        sections.append(f"#### `.github/workflows/{wf}`\n\n{code_block(content, 'yaml')}\n")
    except FileNotFoundError:
        sections.append(f"#### `.github/workflows/{wf}`\n\n*(File not found)*\n")

# ══════════════════════════════════════════════════
# REMAINING SECTIONS
# ══════════════════════════════════════════════════

sections.append("""---

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
""")

# ══════════════════════════════════════════════════
# WRITE THE FILE
# ══════════════════════════════════════════════════

output_path = os.path.join(PROJECT, "Documentation.md")
with open(output_path, "w") as f:
    f.write("\n\n".join(sections))

print(f"Documentation written to {output_path}")
print(f"Total length: {os.path.getsize(output_path):,} bytes")
