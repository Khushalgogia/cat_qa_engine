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
