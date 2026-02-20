# CAT QA Engine — Complete Documentation

> Everything you need to clone, set up, run, and maintain this system. Start here.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [First-Time Setup](#first-time-setup)
4. [Processing Your Backlog](#processing-your-backlog)
5. [Daily Operations](#daily-operations)
6. [When You Get a New Class](#when-you-get-a-new-class)
7. [What Happens Automatically](#what-happens-automatically)
8. [How Each Script Works](#how-each-script-works)
9. [All Prompts Used](#all-prompts-used)
10. [Database Schema](#database-schema)
11. [Design Decisions](#design-decisions)
12. [Troubleshooting](#troubleshooting)
13. [Dependencies](#dependencies)

---

## System Overview

Two systems, fully automated, zero overlap:

| System | When | What | Interaction |
|--------|------|------|-------------|
| **Math Sprint** | 8:30 AM | 5-question speed drill (reciprocals, squares, cubes, primes, tables) | Tap inline buttons |
| **Spot the Flaw** | 2 PM → 10 PM | Corrupted solution → quiz → axiom → graveyard recall | Tap poll + text replies |
| **Weekly Report** | Sunday 8:30 PM | Combined error fingerprint + sprint stats | Read only |

**What makes it work:**
- Wrong sprint answers cost you debt questions (punishment works)
- Yesterday's missed flaw category guarantees sprint questions the next morning (immediate repair)
- Axiom at 10 PM is framed by whether you caught or missed ("this one got you" vs "you spotted this")
- Graveyard fires at 10:05 PM — same pre-sleep consolidation window as the axiom
- When the problem bank runs out → revision rounds re-deliver caught problems

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   YOUR MAC (Local)                    │
│                                                       │
│  audio/*.mp3/m4a  ──→  transcribe.py (Whisper)        │
│                            │                          │
│  transcripts/*.txt  ──→  process_transcript.py        │
│                          (3 Gemini calls per problem)  │
│                            │                          │
│  generate_questions.py  ──┤  (one-time, 109 questions) │
│                            ▼                          │
│                      Supabase Database                │
└──────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   GITHUB ACTIONS       SUPABASE EDGE      TELEGRAM
   (6 scheduled          FUNCTION          (your phone)
    workflows)        (sprint-webhook)
```

---

## First-Time Setup

### 1. Clone and install

```bash
git clone https://github.com/Khushalgogia/cat_qa_engine.git
cd cat_qa_engine
python3 -m venv venv
source venv/bin/activate
pip install google-genai supabase==2.3.5 gotrue==1.3.0 python-telegram-bot==20.7 python-dotenv httpx==0.25.2
pip install openai-whisper
brew install ffmpeg
```

### 2. Create Supabase project

1. [supabase.com](https://supabase.com) → New Project → Name: `cat-qa-engine`
2. Copy **Project URL** and **Service Role Key** from Settings → API
3. Copy **Project Ref** (the `xxxxxx` part in `https://xxxxxx.supabase.co`)
4. Run ALL SQL from [README.md → Step 1](README.md#step-1-create-supabase-project) in SQL Editor
5. Run this additional SQL for the `is_revision` column:
```sql
ALTER TABLE daily_log ADD COLUMN IF NOT EXISTS is_revision boolean DEFAULT false;
```

### 3. Create Telegram bot

1. @BotFather → `/newbot` → Copy **Bot Token**
2. @userinfobot → Send any message → Copy your **Chat ID**

### 4. Get Gemini API key

1. [aistudio.google.com](https://aistudio.google.com) → Get API Key

### 5. Create `.env`

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_service_role_key
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
GEMINI_API_KEY=your_gemini_key
```

### 6. Deploy Edge Function (one-time)

```bash
brew install supabase/tap/supabase
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase secrets set TELEGRAM_TOKEN=your_bot_token
supabase functions deploy sprint-webhook --no-verify-jwt
```

### 7. Populate sprint questions (one-time)

```bash
source venv/bin/activate
python scripts/generate_questions.py
# Review sample → type 'y' → 109 questions inserted
```

### 8. Register webhook (one-time)

```bash
python scripts/register_webhook.py
```

### 9. Push to GitHub and add secrets

```bash
git push -u origin main
```

Go to GitHub → Settings → Secrets → Actions → Add these:

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | Your project URL |
| `SUPABASE_KEY` | Service role key |
| `TELEGRAM_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID |
| `GEMINI_API_KEY` | Gemini key |

**Setup is done. Everything below is daily operations.**

---

## Processing Your Backlog

If you have multiple unprocessed class recordings:

### Step 1: Batch transcribe (one afternoon, unattended)

```bash
source venv/bin/activate
bash scripts/batch_transcribe.sh
```

This transcribes ALL audio files in `audio/` that don't already have transcripts. Walk away — it runs unattended (~8 minutes per hour of audio).

### Step 2: Process one transcript per day

**Do NOT process all at once.** Process one per day, in chronological order:

```bash
# Day 1: Your first class
python scripts/process_transcript.py transcripts/numbersystem_dec19.txt

# Day 2: Your second class
python scripts/process_transcript.py transcripts/qa_dec20.txt

# Day 3: Third class... and so on
```

Each class generates 3-6 problems. Over 14 days you'll have ~50 problems = 7-8 weeks of daily content.

### Why this order matters

`deliver_problem.py` delivers problems **ordered by `source_file`** (alphabetical = chronological if named `class_01_...`, `class_02_...`). So problems from earlier classes are delivered before later ones — matching the order you actually learned the concepts.

**Naming convention:** Name your audio files or transcripts so they sort correctly:
```
numbersystem_dec19.txt    ← delivered first (n < q alphabetically)
qa_dec20.txt              ← delivered second
```

---

## Daily Operations

### Your complete daily routine (~5 minutes)

| Time | What Arrives | Your Action | Duration |
|------|-------------|-------------|----------|
| 8:30 AM | ⚡ Math Sprint (5 questions) | Tap inline buttons. Wrong answers add debt. | 2-3 min |
| 2:00 PM | 🔍 Spot the Flaw quiz poll | Find the flaw, tap your answer | 1 min |
| 6:00 PM | ⏰ Reminder (if you haven't replied) | Reply "caught" or "missed" | 10 sec |
| 10:00 PM | 🌙 Trap axiom (framed by your result) | Read it, feel the framing | 20 sec |
| 10:05 PM | ⚰️ Graveyard recall (if any missed) | Reply "got it" or "nope" | 30 sec |
| Sunday 8:30 PM | 📊 Weekly report | Read your blind spots | 1 min |

### The only scripts you ever run manually

| When | What to run | Why |
|------|-------------|-----|
| After getting a new class recording | `python scripts/transcribe.py audio/filename.mp3` | Transcribe audio → text |
| After transcribing | `python scripts/process_transcript.py transcripts/filename.txt` | Extract + corrupt problems (interactive, you approve each one) |
| First-time only | `python scripts/generate_questions.py` | Populate 109 sprint questions |
| First-time only | `python scripts/register_webhook.py` | Register Telegram webhook |
| First-time only | `bash scripts/batch_transcribe.sh` | Batch transcribe all audio |

Everything else runs automatically via GitHub Actions.

---

## When You Get a New Class

This is your standard workflow going forward:

```bash
# 1. Drop the audio file in audio/
# (name it descriptively: class_15_algebra.mp3)

# 2. Activate environment
source venv/bin/activate

# 3. Transcribe (~5-10 min, unattended)
python scripts/transcribe.py audio/class_15_algebra.mp3

# 4. Process (~10 min, interactive — you review each corruption)
python scripts/process_transcript.py transcripts/class_15_algebra.txt
# For each problem: read the corruption → type 'y' if it's good, 'n' to skip

# 5. Commit and push (so GitHub Actions picks up new code)
git add . && git commit -m "add class 15 problems" && git push
```

**That's it.** The 3-6 new problems enter the database as `unseen`. Tomorrow's 2 PM delivery automatically picks them up (ordered by `source_file`). The sprint system is separate and doesn't need updating.

---

## What Happens Automatically

### GitHub Actions Schedule (all times IST)

| Time | Workflow | Script | What it does |
|------|----------|--------|-------------|
| **8:30 AM** | `math_sprint.yml` | `deliver_sprint.py` | Sends 5-question sprint with inline keyboard |
| **2:00 PM** | `daily_problem.yml` | `deliver_problem.py` | Sends one Spot the Flaw quiz poll |
| **6:00 PM** | `handle_reply.yml` | `handle_reply.py` | Detects your answer, sends reminder if missing |
| **10:00 PM** | `nightly_axiom.yml` | `deliver_axiom.py` | Sends axiom framed by caught/missed |
| **10:05 PM** | `graveyard_nudge.yml` | `graveyard_check.py` | Resurfaces one missed problem for recall |
| **Sun 8:30 PM** | `weekly_report.yml` | `weekly_report.py` | Sends combined fingerprint + sprint stats |

### Sprint button taps (real-time, always-on)

Handled by the **Supabase Edge Function** (`sprint-webhook`). When you tap an inline button:
1. Edge Function receives the tap via Telegram webhook
2. Checks answer → correct or debt queue
3. Edits the message in-place with the next question
4. Logs every answer in `sprint_logs`

---

## How Each Script Works

### `deliver_sprint.py` — Morning Sprint

**Question selection priority:**
1. **Yesterday-miss guarantee**: If you missed yesterday's 2 PM flaw → **2 of 5** sprint questions come from that error category's mapped sprint category. Guaranteed, not weighted.
2. **Weak spot weighting**: If no yesterday miss, reads all-time missed flaw categories
3. **Fill to 5** with random, least-attempted questions

**Debt queue**: Wrong answers append the question to the end. You clear all debt before the sprint ends.

**Session cleanup**: Deletes sprint sessions older than 7 days.

### `deliver_problem.py` — Daily Flaw Quiz

1. Picks one `unseen` problem, **ordered by `source_file`** (chronological)
2. Sends problem statement + quiz poll to Telegram
3. **Revision fallback**: If no unseen problems remain → re-delivers oldest `caught` problem as "📚 Revision Round"
4. Tags revision deliveries with `is_revision=true` in `daily_log`

### `handle_reply.py` — Reply Detection

The most complex script. Three concerns:

1. **Webhook cycle**: Temporarily deletes webhook → calls `getUpdates` → restores webhook in `finally` block
2. **Graveyard replies first**: Checks `graveyard_pending_id`. If set and "got it"/"nope" found → processes graveyard, clears the key
3. **Flaw replies**: Checks poll answer + text reply. Sends reminder if nothing found

### `deliver_axiom.py` — Nightly Axiom with Emotional Framing

Checks `daily_log.caught` and frames:
- **Caught**: "🌙 You spotted this one today. Lock it in."
- **Missed**: "🌙 This one got you today. Make sure it never does again."

### `graveyard_check.py` — Pre-Sleep Recall

1. Finds oldest `missed` problem
2. Sends for mental recall (not re-solving)
3. Writes to `graveyard_pending_id` so `handle_reply.py` knows which problem the reply belongs to
4. "got it" → status `reviewed` (exits graveyard permanently)
5. "nope" → stays `missed`, cycles back

### `weekly_report.py` — Combined Report

- Aggregates flaw detection by error category (excludes revision rounds)
- Sprint stats: total answers, correct count, debt repaid, slowest category

---

## All Prompts Used

### Prompt 1: Extract Problems

```
You are analyzing a transcript of a CAT exam quantitative aptitude class.
Find every moment where a problem was fully solved by the teacher.
Extract: problem statement + numbered solution steps.
Return JSON array.
```

### Prompt 2: Sanitize Steps

```
Clean up language so each step is one precise mathematical action.
Do not change numbers, logic, or operations.
```

### Prompt 3: Introduce Flaw

```
Introduce exactly one conceptual error from this list:
- Algebraic Sign Error, Ignoring Negative Root, Integer Constraint Missed
- Ratio Misapplied, Calculation Shortcut Trap, Misread Constraint
- At-Least vs Exactly Confusion, Division by Variable Without Checking Zero
- Proportionality Assumed Equal

The error must be subtle. Steps after corruption follow logically from the wrong value.
Return: corrupted_steps, flaw_step_number, error_category, explanation, trap_axiom.
```

### Prompt 4: Sprint Question Wrapping

```
Rewrite each raw math fact as a short product analytics scenario.
Keep under 2 sentences. Keep answer options exactly as given.
```

---

## Database Schema

| Table | System | Purpose |
|-------|--------|---------|
| `qa_flaw_deck` | Flaw | Problems with corrupted solutions. Status: `unseen` → `delivered` → `caught`/`missed`/`reviewed` |
| `daily_log` | Flaw | One row per delivery. `is_revision` flag prevents double-counting |
| `settings` | Both | Keys: `todays_problem_id`, `todays_axiom`, `graveyard_pending_id` |
| `math_sprints` | Sprint | 109 flashcard questions |
| `sprint_sessions` | Sprint | Active sessions with question queue and debt counter |
| `sprint_logs` | Sprint | Per-answer log for analytics |

---

## Design Decisions

| Decision | Reasoning |
|----------|-----------|
| **handle_reply at 6 PM** (not 2:40 PM) | 4-hour reply window. Meetings won't cause phantom problems. |
| **Graveyard at 10:05 PM** (not 8 AM) | Same pre-sleep consolidation window as axiom. No morning cognitive overload. |
| **Axiom framed by caught/missed** | "This one got you" creates prediction error → deeper encoding. |
| **Yesterday-miss guaranteed** (not weighted) | Guaranteed 2/5 creates explicit, immediate repair. |
| **source_file ordering** | Problems delivered in class chronological order. |
| **Webhook cycle in handle_reply** | Telegram forbids getUpdates + webhook simultaneously. |
| **graveyard_pending_id** (separate key) | Prevents graveyard replies being misrouted to flaw path. |
| **Revision fallback** | Prevents dead delivery slot when bank exhausted. |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Gemini 503 / high demand | Model is `gemini-2.5-flash`. Retry after 1 min. Built-in exponential backoff. |
| Supabase "proxy" error | Pinned `gotrue==1.3.0` and `httpx==0.25.2` |
| Sprint buttons not working | `supabase functions list` → check deployment. Re-register: `python scripts/register_webhook.py` |
| "can't use getUpdates while webhook active" | Fixed. `handle_reply.py` cycles webhook: delete → poll → restore. |
| Problem bank empty | Fixed. Falls back to revision rounds automatically. |
| Graveyard replies disappearing | Fixed. Uses `graveyard_pending_id` (separate from `todays_problem_id`). |
| Stale poll answers from yesterday | Fixed. Timestamp filter: only processes answers from last 8 hours. |

---

## Dependencies

### Python packages

| Package | Version | Purpose |
|---------|---------|---------|
| `google-genai` | latest | Gemini AI API |
| `supabase` | 2.3.5 | Database client |
| `gotrue` | 1.3.0 | Auth (pinned) |
| `python-telegram-bot` | 20.7 | Telegram Bot API |
| `python-dotenv` | latest | .env loader |
| `httpx` | 0.25.2 | HTTP (pinned) |
| `openai-whisper` | latest | Audio transcription |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Supabase PostgreSQL | All 6 tables |
| Supabase Edge Function | Real-time sprint button handler |
| GitHub Actions | 6 scheduled workflows |
| Telegram Bot API | All delivery + interaction |
| Gemini 2.5 Flash | Problem extraction, corruption, question framing |
