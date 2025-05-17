from faster_whisper import WhisperModel
import os
import sys
import time
import math

os.environ["OMP_NUM_THREADS"] = os.environ.get("CPU_PHYSICAL_REAL_CORES", "8")

# Get model settings from environment variables or use defaults
model_size = os.environ.get("WHISPER_MODEL", "large-v3-turbo")
beam_size = int(os.environ.get("WHISPER_BEAM", "5"))
lang = os.environ.get("WHISPER_LANG", None)  # None means auto-detect

print(f"Using model: {model_size}, beam size: {beam_size}, language: {lang or 'auto-detect'}")

model = WhisperModel(model_size, device="cpu", compute_type="auto")

# Get audio filename from args or fail if not provided
if len(sys.argv) <= 1:
    print("Error: Audio file path is required as an argument")
    print("Usage: python voice2text.py <audio_file_path>")
    sys.exit(1)
audio_file = sys.argv[1]

# Get path components
audio_basename = os.path.basename(audio_file)
audio_name = os.path.splitext(audio_basename)[0]
# Replace spaces with underscores in the audio name
audio_name = audio_name.replace(" ", "_")

# Output file path
date = time.strftime('%Y-%m-%d')
output_dir = os.path.join('/app/output', date)
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, f"{audio_name}_transcription.txt")

# Delete existing transcription file if it exists
if os.path.exists(output_file):
    try:
        os.remove(output_file)
        print(f"Deleted existing transcription file: {output_file}")
    except Exception as e:
        print(f"Warning: Could not delete existing file: {str(e)}")

# Use full path if running in the container
if audio_file.startswith("/app/audio/"):
    input_path = audio_file
else:
    input_path = f"/app/audio/{audio_file}"

print(f"Transcribing {input_path}...")

# Start timer
start_time = time.time()

try:
    # Attempt the transcription with provided language and beam size
    segments, info = model.transcribe(input_path, beam_size=beam_size, language=lang, vad_filter=True)
    
    # Check if language probability is NaN (not a number) when auto-detecting
    if lang is None and (math.isnan(info.language_probability) or info.language_probability < 0.8):
        print("Error: Language detection failed. Probability is %.2f for language '%s'" % (info.language_probability, info.language))
        sys.exit(1)
        
    if lang is None:
        print("Detected language '%s' with probability %.2f" % (info.language, info.language_probability))
    else:
        print(f"Using specified language: {lang}")
    
    # Process segments and prepare text
    full_text = ""
    segment_list = list(segments)  # Convert generator to list to ensure successful iteration
    
    if not segment_list:
        print("Warning: No transcription segments were generated. The file may be empty or unsupported.")
        sys.exit(1)
    
    # Print segments to console
    for segment in segment_list:
        segment_text = segment.text.strip()
        seg_text = "[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment_text)
        print(seg_text)
        full_text += seg_text + "\n"
    
    # Only write to file if we have successfully processed all segments
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Transcription of {audio_basename}\n")
        f.write(f"# Detected language: {info.language} (probability: {info.language_probability:.2f})\n\n")
        
        # Calculate and display elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        print(f"\n\nTotal processing time: {minutes} minutes and {seconds} seconds")

        full_text += "\n\n" + f"Total processing time: {minutes} minutes and {seconds} seconds"

        # Write the full combined text
        f.write(full_text.strip())
        print(f"\nTranscription saved to {output_file}")
    
except Exception as e:
    print(f"Error during transcription: {str(e)}")
    print("No output file was written due to the error.")
    sys.exit(1)