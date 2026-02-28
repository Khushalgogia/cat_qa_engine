## Your Exact Workflow — The 4 Commands You'll Repeat

**Every time you get a new class recording:**

```bash
cd /Users/khushal/Documents/Python/notifications/cat_qa_engine
source venv/bin/activate
python scripts/transcribe.py audio/YOUR_FILE.mp3
python scripts/process_transcript.py transcripts/YOUR_FILE.txt
git add . && git commit -m "add class N" && git push
```

**For old backlog classes (batch all audio at once):**

```bash
bash scripts/batch_transcribe.sh    # transcribes ALL audio files, unattended

# Then process ONE transcript per day:
python scripts/process_transcript.py transcripts/class_03.txt
```

> **Note:** Everything else is automated. You never run delivery, reply handling, axiom, graveyard, or report scripts manually.

---

## What If Database Push Fails? (Auto-Retry + Recovery)

You don't need to worry about internet issues anymore. Here's what happens now:

1. **Auto-retry:** When you say `y` to push a problem, the script tries **5 times** automatically (waiting longer each time) before giving up.
2. **Recovery file:** If all 5 tries fail, your approved problem is **saved locally** to a file called `recovery_records.json` (in the same folder as the transcript). Your work is never lost.
3. **Push later:** Once internet/Supabase is back, just run:

```bash
python scripts/push_recovery.py transcripts/recovery_records.json
```

This pushes all saved records to the database. Once done, the recovery file deletes itself.

> **TL;DR:** If the push fails, the script retries automatically. If it still fails, your work is saved locally. You push it later with one command. You never lose your review work.