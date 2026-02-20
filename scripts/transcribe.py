import whisper
import sys
import os

def transcribe(audio_path):
    print(f"Loading Whisper model...")
    model = whisper.load_model("base")  # use "small" for better accuracy
    
    print(f"Transcribing {audio_path}... this may take a few minutes.")
    result = model.transcribe(audio_path)
    
    output_path = audio_path.replace("/audio/", "/transcripts/").rsplit(".", 1)[0] + ".txt"
    
    with open(output_path, "w") as f:
        f.write(result["text"])
    
    print(f"Done. Transcript saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    transcribe(sys.argv[1])
