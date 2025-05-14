from faster_whisper import WhisperModel
import os
import sys

model_size = "large-v3-turbo"

# Run on GPU with FP16
# model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
model = WhisperModel(model_size, device="cpu", compute_type="int8")

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
output_dir = "/app/output"
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

try:
    # Attempt the transcription
    segments, info = model.transcribe(input_path, beam_size=5, vad_filter=True)
    
    print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
    
    # Process segments and prepare text
    full_text = ""
    segment_list = list(segments)  # Convert generator to list to ensure successful iteration
    
    if not segment_list:
        print("Warning: No transcription segments were generated. The file may be empty or unsupported.")
        sys.exit(1)
    
    # Print segments to console
    for segment in segment_list:
        segment_text = segment.text.strip()
        full_text += segment_text + " "
        print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment_text))
    
    # Only write to file if we have successfully processed all segments
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Transcription of {audio_basename}\n")
        f.write(f"# Detected language: {info.language} (probability: {info.language_probability:.2f})\n\n")
        
        # Write the full combined text
        f.write(full_text.strip())
    
    print(f"\nTranscription saved to {output_file}")
    
except Exception as e:
    print(f"Error during transcription: {str(e)}")
    print("No output file was written due to the error.")
    sys.exit(1)