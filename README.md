# CAT QA Engine 🎯

A spaced-repetition flaw-detection system for CAT quantitative aptitude prep. Transcribes class recordings, extracts math problems, introduces subtle errors using Gemini AI, and delivers daily "Spot the Flaw" challenges via Telegram.

## Architecture

```
Audio → Whisper (local) → Transcript → Gemini (3-call pipeline) → Supabase
                                                                      ↓
GitHub Actions (cron) → deliver_problem.py → Telegram Quiz Poll (2 PM)
                      → handle_reply.py → caught/missed tracking (2:40 PM)
                      → deliver_axiom.py → Trap Axiom reveal (10 PM)
                      → graveyard_check.py → Missed problem nudge (Mon/Wed/Fri 8 AM)
                      → weekly_report.py → Error fingerprint report (Sunday 8:30 PM)
```

## Daily Workflow

| Time | What Happens | Your Action |
|------|-------------|-------------|
| 2:00 PM | Quiz poll arrives on Telegram | Find the flaw, tap your answer |
| 2:40 PM | Reply handler runs | Type "caught" or "missed" to the bot |
| 10:00 PM | Trap axiom arrives | Read it. Sleep on it. |

## Setup

### Prerequisites
- Python 3.11+
- ffmpeg (`brew install ffmpeg`)
- Supabase project with tables created
- Telegram bot token

### Install
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install openai-whisper  # local only
```

### Environment Variables
Copy `.env.example` or create `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
GEMINI_API_KEY=your_gemini_key
```

### GitHub Secrets
Add all 5 env vars as repository secrets under Settings → Secrets → Actions.

## Scripts

| Script | Runs Where | Purpose |
|--------|-----------|---------|
| `transcribe.py` | Local | Audio → text via Whisper |
| `process_transcript.py` | Local | Extract problems → corrupt with Gemini → save to Supabase |
| `deliver_problem.py` | GitHub Actions | Send daily quiz poll to Telegram |
| `deliver_axiom.py` | GitHub Actions | Send nightly trap axiom |
| `handle_reply.py` | GitHub Actions | Read caught/missed reply, update DB |
| `graveyard_check.py` | GitHub Actions | Resurface missed problems |
| `weekly_report.py` | GitHub Actions | Error fingerprint summary |

## Processing a New Class

```bash
# Step 1: Transcribe
python scripts/transcribe.py audio/class_01_percentages.mp3

# Step 2: Process (interactive — you review each problem)
python scripts/process_transcript.py transcripts/class_01_percentages.txt
```

## Supabase Tables

- **qa_flaw_deck** — Problem bank with corrupted solutions
- **daily_log** — Delivery + caught/missed tracking
- **settings** — Key-value store for today's problem & axiom
