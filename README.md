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
9. [Step 6: Deploy Edge Function](#step-6-deploy-edge-function)
10. [Step 7: Push to GitHub & Add Secrets](#step-7-push-to-github--add-secrets)
11. [How Each Script Works](#how-each-script-works)
12. [All Prompts Used](#all-prompts-used)
13. [Daily Workflow](#daily-workflow)
14. [Cron Schedule](#cron-schedule)
15. [Design Decisions](#design-decisions)
16. [Troubleshooting](#troubleshooting)
17. [Dependencies](#dependencies)

---

## What This App Does

Two interconnected systems, one brain, zero overlap:

### System 1: Spot the Flaw (Afternoon → Night)
You record your CAT class audio. This app:
1. **Transcribes** it using OpenAI Whisper (locally on your Mac)
2. **Extracts** every solved math problem from the transcript using Gemini AI
3. **Corrupts** one step in each solution with a subtle, realistic error
4. **Stores** everything in a Supabase database
5. **Delivers** one "Spot the Flaw" quiz poll to your Telegram every day at 2 PM
6. **Auto-detects** whether you caught the flaw or missed it (real-time via Edge Function)
7. **Sends** the underlying trap axiom at 10 PM framed by your result ("you spotted this" vs "this got you")
8. **Resurfaces** missed problems at 10:05 PM as graveyard recall (same consolidation window)
9. When the bank runs dry → **revision rounds** re-deliver old caught problems

### System 2: Math Sprint (Morning)
10. **Generates** 109 contextual math flashcards (reciprocals, squares, cubes, primes, tables)
11. **Delivers** 5-question speed drills at 8:30 AM with inline keyboard buttons
12. **Wrong answers add debt** — each miss adds that question back to the end of the queue
13. **Real-time interaction** via Supabase Edge Function — messages edit in-place
14. **Yesterday's miss guarantee** — if you missed a flaw yesterday, today's sprint guarantees 2 questions from that category
15. **Session cleanup** — old sprint sessions auto-delete after 7 days

### Weekly Report
16. **Sends** a combined error fingerprint + sprint stats report every Sunday

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
│  deliver_sprint  │ │  sprint-     │ │  Sprint drills   │
│  deliver_problem │ │  webhook     │ │  Quiz polls      │
│  deliver_axiom   │ │  (real-time  │ │  Inline buttons  │
│  graveyard_check │ │   buttons,   │ │  Axioms          │
│  weekly_report   │ │   polls,     │ │  Graveyard       │
│                  │ │   graveyard) │ │  Reports         │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

### Real-Time Edge Function
- **Webhook** (`callback_query` + `poll_answer`) → Edge Function handles sprint buttons, graveyard buttons, and quiz poll answers in real-time
- No `getUpdates` polling needed — everything is event-driven

### Known Behaviors
- **Cold start delay**: On the Supabase free tier, the Edge Function goes to sleep after inactivity. The first morning sprint button tap may take 2-4 seconds. Subsequent taps are instant (<200ms). Don't spam-click if it hangs on the first question.

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
   - **Project Ref** (the `xxxxxx` part between `https://` and `.supabase.co`)

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
insert into settings (key, value) values ('graveyard_pending_id', '');

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

### Database Schema

| Table | System | Purpose |
|-------|--------|---------|
| `qa_flaw_deck` | Flaw | Problems with corrupted solutions (`unseen` → `delivered` → `caught`/`missed`/`reviewed`) |
| `daily_log` | Flaw | One row per delivered problem, tracks if caught |
| `settings` | Both | Key-value store: `todays_problem_id`, `todays_axiom`, `graveyard_pending_id` |
| `math_sprints` | Sprint | 109 flashcard questions with options and correct answer index |
| `sprint_sessions` | Sprint | Active sprint sessions with question queue and debt counter |
| `sprint_logs` | Sprint | Per-answer log for analytics |

---

## Step 2: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "QA CAT Tutor")
4. Choose a username (e.g., `qa_cat_tutor_bot`)
5. Copy the **Bot Token** (looks like `1234567890:AAE2tkzzOC...`)
6. **Get your Chat ID**: Search for **@userinfobot** on Telegram, send it any message, it replies with your chat ID

---

## Step 3: Get Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → Create API Key
3. Copy the key (starts with `AIza...`)

---

## Step 4: Set Up Your Mac

```bash
# Clone or create project
git clone https://github.com/YOUR_USERNAME/cat_qa_engine.git
cd cat_qa_engine

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install google-genai 'supabase>=2.11.0' 'python-telegram-bot>=21.0' python-dotenv

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
│   ├── deliver_problem.py          ← Daily quiz poll + revision fallback + auto-condense
│   ├── deliver_axiom.py            ← Nightly axiom with caught/missed framing
│   ├── deliver_sprint.py           ← Morning sprint with yesterday-miss guarantee
│   ├── graveyard_check.py          ← Resurface missed problems with inline buttons (10:05 PM)
│   ├── weekly_report.py            ← Combined flaw + sprint stats report
│   └── register_webhook.py         ← One-time: register Telegram webhook
├── supabase/
│   └── functions/
│       └── sprint-webhook/
│           └── index.ts            ← Edge Function: sprint buttons + poll answers + graveyard
├── .github/
│   └── workflows/
│       ├── math_sprint.yml         ← 8:30 AM daily
│       ├── daily_problem.yml       ← 2:00 PM daily

│       ├── nightly_axiom.yml       ← 10:00 PM daily
│       ├── graveyard_nudge.yml     ← 10:05 PM daily
│       └── weekly_report.yml       ← 8:30 PM Sunday
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

Create `requirements.txt`:

```
google-genai
supabase>=2.11.0
python-telegram-bot>=21.0
python-dotenv
```

---

## Step 6: Deploy Edge Function

The Edge Function runs on Supabase and handles real-time sprint button taps. This is a one-time setup:

```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Login and link
supabase login
supabase link --project-ref YOUR_PROJECT_REF

# Set secrets (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are auto-provided)
supabase secrets set TELEGRAM_TOKEN=your_telegram_bot_token
supabase secrets set TELEGRAM_CHAT_ID=your_chat_id

# Deploy
supabase functions deploy sprint-webhook --no-verify-jwt

# Populate question bank (one-time, local, interactive)
source venv/bin/activate
python scripts/generate_questions.py
# Review sample output → type 'y' to insert 109 questions

# Register webhook (one-time)
python scripts/register_webhook.py
```

---

## Step 7: Push to GitHub & Add Secrets

```bash
git init
git add .
git commit -m "initial setup"
git remote add origin https://github.com/YOUR_USERNAME/cat_qa_engine.git
git push -u origin main
```

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|-------------|-------|
| `SUPABASE_URL` | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | Your service role key |
| `TELEGRAM_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID number |
| `GEMINI_API_KEY` | Your Gemini API key |

---

## How Each Script Works

### 1. `transcribe.py` — Audio → Text (Local Only)

Uses OpenAI Whisper to convert audio files to text transcripts. Always saves output to `transcripts/` directory regardless of input path.

```bash
source venv/bin/activate
python scripts/transcribe.py audio/class_01_percentages.mp3
```

---

### 2. `process_transcript.py` — The Intelligence Layer (Local Only)

Makes 3 Gemini API calls per problem:
1. **Extract** every fully-solved problem from the transcript
2. **Sanitize** the solution steps for clarity
3. **Corrupt** one step with a subtle, realistic error

Shows you each corruption for `y/n` approval before saving to Supabase. Includes retry logic with exponential backoff for rate limits.

```bash
python scripts/process_transcript.py transcripts/class_01_percentages.txt
```

---

### 3. `deliver_problem.py` — Daily Quiz (GitHub Actions, 2 PM)

1. Picks one `unseen` problem from `qa_flaw_deck`
2. Sends problem statement + quiz poll to Telegram
3. Updates DB: status → `delivered`, logs in `daily_log`
4. Saves axiom and problem ID to `settings`
5. **Revision fallback**: if no unseen problems remain, re-delivers the oldest caught problem as "📚 Revision Round"

---

### 4. Poll Answer + Graveyard Handling — Edge Function (Real-Time)

Formerly handled by `handle_reply.py` (deleted). Now processed instantly by the Edge Function:

**Poll answers**: When you answer the 2 PM quiz poll, the Edge Function receives the `poll_answer` event, looks up `todays_problem_id` from settings, compares your answer to `flawed_step_number - 1`, and updates `qa_flaw_deck` + `daily_log` immediately.

**Graveyard buttons**: When you tap ✅ Got It or ❌ Still Foggy on the graveyard nudge, the Edge Function handles it instantly:
- Got It → status → `reviewed` (exits graveyard permanently)
- Still Foggy → stays `missed` (comes back next cycle)

**Idempotency**: The Edge Function checks if a problem is already resolved before updating, preventing duplicate processing.

---

### 5. `deliver_axiom.py` — Nightly Axiom with Framing (GitHub Actions, 10 PM)

1. Reads today's axiom from `settings`
2. Checks `daily_log` whether you caught or missed
3. Frames the message accordingly:
   - **Caught**: "🌙 You spotted this one today. Lock it in. _[axiom]_"
   - **Missed**: "🌙 This one got you today. Make sure it never does again. _[axiom]_"
4. The emotional framing creates prediction error signals that drive deeper memory encoding

---

### 6. `graveyard_check.py` — Missed Problem Recall (GitHub Actions, 10:05 PM)

1. Finds the oldest `missed` problem
2. Sends it to Telegram with **inline buttons** (✅ Got It / ❌ Still Foggy)
3. The problem ID is embedded in the button callback data — no cross-script state needed
4. Tapping a button → Edge Function handles it instantly (see section 4 above)

**Why 10:05 PM?** Runs 5 minutes after the axiom. Your brain is already in reflection mode. Graveyard recall + axiom consolidation happen in the same pre-sleep window = neurologically superior to morning delivery.

---

### 7. `weekly_report.py` — Combined Report (GitHub Actions, Sunday 8:30 PM)

1. Aggregates flaw detection results by error category
2. Shows blind spots (most-missed) and strengths (most-caught)
3. Includes **sprint stats**: total answers, correct count, debt repaid, slowest category

---

### 8. `generate_questions.py` — Question Bank (One-Time, Local)

Generates 109 raw math questions programmatically across 5 categories:
- **Reciprocals** (19): 1/n as percentages (1/2 to 1/20)
- **Squares** (30): n² for n=1 to 30
- **Cubes** (15): n³ for n=1 to 15
- **Primes** (25): factoring composite numbers vs identifying primes
- **Tables** (20): high-value multiplication pairs (13×7, 17×8, etc.)

Wraps each question in a contextual product analytics scenario using Gemini AI (e.g., "1/2 as %" becomes "In an A/B test with two equally sized variants, what percentage goes to treatment?").

```bash
source venv/bin/activate
python scripts/generate_questions.py
# Review → type 'y' → 109 questions inserted
```

---

### 9. `deliver_sprint.py` — Morning Sprint (GitHub Actions, 8:30 AM)

**Question selection priority**:
1. **Yesterday-miss guarantee**: If yesterday's 2 PM flaw was missed → **2 of 5 sprint questions** come from that error category's mapped sprint category. Not weighted — guaranteed.
2. **Weak spot weighting**: If no yesterday miss, reads all-time missed categories
3. **Fill to 5** with random, least-attempted questions

**Debt queue**: Wrong answers append the question to the end. You must clear all debt before the sprint ends.

**Session cleanup**: Deletes sprint sessions older than 7 days at the end of each delivery.

---

### 10. `sprint-webhook/index.ts` — Edge Function (Supabase)

Runs on Supabase Deno runtime. Handles 3 types of Telegram events:

**Sprint callbacks** (`sp|{session_id}|{option_index}`):
1. If wrong → appends to debt queue, shows "❌ added to debt queue"
2. If right → shows "✅ Correct!"
3. **Edits the message in-place** with next question (no new messages)
4. On completion → shows sprint summary with debt stats
5. Logs every answer in `sprint_logs`

**Poll answers** (2 PM quiz): Compares answer to correct flaw step, updates DB + sends confirmation.

**Graveyard callbacks** (`gy|{problem_id}|{action}`): Updates problem status and edits message to remove buttons.

---

### 11. `register_webhook.py` — Webhook Registration (One-Time)

Tells Telegram to send `callback_query` + `poll_answer` events to the Edge Function. All interactive events (sprint buttons, graveyard buttons, quiz answers) are handled in real-time.

---

## All Prompts Used

### Prompt 1: Extract Problems from Transcript

```
You are analyzing a transcript of a CAT exam quantitative aptitude class.
The teacher explains concepts and solves problems out loud.

Task: Find every moment where a problem was fully solved by the teacher.

For each, extract:
a) The problem statement in clean mathematical language.
b) The teacher's solution as numbered logical steps.

Rules:
- Do NOT solve anything yourself. Only extract what the teacher actually did.
- If incomplete or unclear, skip entirely.
- Return JSON array: [{"problem_statement": "...", "solution_steps": ["step 1", ...]}]
```

### Prompt 2: Sanitize Solution Steps

```
Clean up language so each step is one precise mathematical action.
Do not change numbers, logic, or operations. Only improve clarity.
Return exact same JSON structure.
```

### Prompt 3: Introduce a Subtle Flaw

```
Introduce exactly one conceptual error from this list:
- Algebraic Sign Error, Ignoring Negative Root, Integer Constraint Missed
- Ratio Misapplied, Calculation Shortcut Trap, Misread Constraint
- At-Least vs Exactly Confusion, Division by Variable Without Checking Zero
- Proportionality Assumed Equal

The error must be subtle. Steps after corruption follow logically from the wrong value.

Return JSON: {"corrupted_steps": [...], "flaw_step_number": N, "error_category": "...",
"explanation": "...", "trap_axiom": "a single vivid sentence, no formulas, pure logic"}
```

### Prompt 4: Question Context Wrapping (Sprint)

```
Rewrite each raw math fact as a short scenario from product analytics/dashboards.
Keep under 2 sentences. Keep answer options exactly as given.
Return JSON: [{"index": N, "question_text": "rewritten scenario"}]
```

---

## Daily Workflow

### Your Complete Daily Routine (~5 min total)

| Time | What Arrives | Your Action | Duration |
|------|-------------|-------------|----------|
| 8:30 AM | ⚡ Math Sprint (5 questions, inline keyboard) | Tap through questions. Wrong answers queue up. | 2-3 min |
| 2:00 PM | 🔍 Spot the Flaw quiz poll | Find the flaw, tap answer (auto-detected) | 1 min |
| 10:00 PM | 🌙 Trap axiom (framed by your result) | Read, feel the framing | 20 sec |
| 10:05 PM | ⚰️ Graveyard recall (if any missed) | Tap ✅ Got It or ❌ Still Foggy | 10 sec |
| Sunday 8:30 PM | 📊 Weekly report + sprint stats | Read blind spots | 1 min |

### When You Get a New Class Recording (~15 minutes)

```bash
source venv/bin/activate
python scripts/transcribe.py audio/class_name.mp3       # ~5 min
python scripts/process_transcript.py transcripts/class_name.txt  # ~10 min (interactive)
```

---

## Cron Schedule

All times shown in IST (UTC+5:30).

| Workflow | Cron (UTC) | IST | Script |
|----------|-----------|-----|--------|
| Math Sprint | `0 3 * * *` | 8:30 AM daily | `deliver_sprint.py` |
| Daily Problem | `30 8 * * *` | 2:00 PM daily | `deliver_problem.py` |
| Nightly Axiom | `30 16 * * *` | 10:00 PM daily | `deliver_axiom.py` |
| Graveyard Nudge | `35 16 * * *` | 10:05 PM daily | `graveyard_check.py` |
| Weekly Report | `0 15 * * 0` | 8:30 PM Sunday | `weekly_report.py` |

---

## Design Decisions

### Why everything is real-time now (no more handle_reply.py)
The original design used `handle_reply.py` at 6 PM to batch-process poll answers and text replies. This required temporarily deleting the webhook (race condition) and waiting hours for feedback. Now the Edge Function handles poll answers and graveyard button taps instantly — zero delay, zero webhook cycling.

### Why graveyard moved from 8 AM to 10:05 PM
Morning had cognitive overload: graveyard at 8 AM + sprint at 8:30 AM = two different systems simultaneously. 10:05 PM puts graveyard recall in the same pre-sleep window as the axiom → both benefit from sleep-dependent consolidation.

### Why the axiom is framed by caught/missed
Same axiom, different emotional encoding. "This one got you today" creates a prediction error signal (you expected to catch it, you didn't). Prediction errors drive deeper long-term encoding. "You spotted this one" reinforces correct pattern matching.

### Why yesterday's miss is guaranteed in today's sprint (not just weighted)
Statistical weighting across 7 days dilutes the signal. Guaranteed 2/5 questions from yesterday's missed category creates explicit, immediate repair: afternoon miss → morning drill. The connection is visceral.

### Why graveyard uses inline buttons (not text replies)
Inline buttons embed the problem ID in callback_data, triggering the Edge Function instantly. No cross-script state needed, no delayed processing, no "got it" text going to a black hole.

---

## Troubleshooting

### "Rate limited" / 429 errors from Gemini
Built-in retry with exponential backoff (10s → 20s → 40s → 80s → 160s). If persistent, wait 1 minute.

### Supabase connection issues
Ensure `supabase>=2.11.0` and `python-telegram-bot>=21.0` — older versions have httpx conflicts.

### Gemini model not found (404)
We use `gemini-2.5-flash`. To check available models:
```python
from google import genai
client = genai.Client(api_key="YOUR_KEY")
for m in client.models.list():
    if 'flash' in m.name.lower(): print(m.name)
```

### Sprint buttons not working
1. Verify Edge Function: `supabase functions list`
2. Check logs: Supabase Dashboard → Edge Functions → sprint-webhook → Logs
3. Re-register webhook: `python scripts/register_webhook.py`
4. Ensure `TELEGRAM_CHAT_ID` is set in Edge Function secrets

### Problem bank exhausted
Fixed. `deliver_problem.py` falls back to re-delivering caught problems as "📚 Revision Round."

### Graveyard buttons not responding
Re-register webhook with `python scripts/register_webhook.py` (must include `callback_query` in allowed_updates). Check Edge Function logs for errors.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `google-genai` | latest | Gemini AI API |
| `supabase` | ≥2.11.0 | Database client |
| `python-telegram-bot` | ≥21.0 | Telegram Bot API |
| `python-dotenv` | latest | Load .env files |
| `openai-whisper` | latest | Audio transcription (local only) |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Supabase (PostgreSQL) | Database for all 6 tables |
| Supabase Edge Functions (Deno) | Real-time sprint webhook handler |
| GitHub Actions | Scheduled daily/weekly script execution |
| Telegram Bot API | Message delivery + inline keyboards + quiz polls |
| Gemini 3 Flash Preview | Problem extraction, corruption, question framing |
