2. Your Exact Workflow — The 4 Commands You'll Repeat
Every time you get a new class recording:

bash
cd /Users/khushal/Documents/Python/notifications/cat_qa_engine
source venv/bin/activate
python scripts/transcribe.py audio/YOUR_FILE.mp3
python scripts/process_transcript.py transcripts/YOUR_FILE.txt
git add . && git commit -m "add class N" && git push
For old backlog classes (batch all audio at once):

bash
bash scripts/batch_transcribe.sh    # transcribes ALL audio files, unattended
# Then process ONE transcript per day:
python scripts/process_transcript.py transcripts/class_03.txt
Everything else is automated. You never run delivery, reply handling, axiom, graveyard, or report scripts manually.