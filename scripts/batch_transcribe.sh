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
