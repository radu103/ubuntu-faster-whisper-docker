from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import subprocess
import time
import uuid
import threading
import json
import atexit

app = Flask(__name__, static_folder='static')

# Configure upload and output directories
UPLOAD_FOLDER = '/app/audio'
OUTPUT_FOLDER = '/app/output'
JOBS_FILE = '/app/code/static/jobs.json'

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Dictionary to store job status
jobs = {}

# Load existing jobs if the file exists
def load_jobs():
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading jobs file: {str(e)}")
    return {}

# Save jobs to a file
def save_jobs():
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Error saving jobs file: {str(e)}")

# Load existing jobs at startup
jobs = load_jobs()

# Register save_jobs to run when the application exits
atexit.register(save_jobs)

def run_transcription(job_id, filepath):
    """Run the transcription as a background process"""
    try:
        # Update job status to processing
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Get just the file name, not the full path
        filename = os.path.basename(filepath)
        
        # Run the voice2text.py script with the audio file
        result = subprocess.run(
            ['python3', '/app/code/voice2text.py', filename],
            capture_output=True,
            text=True
        )
        
        # Check if the transcription was successful
        if result.returncode == 0:
            # Get output filename
            audio_name = os.path.splitext(filename)[0]
            audio_name = audio_name.replace(" ", "_")
            output_file = f"/app/output/{audio_name}_transcription.txt"
            
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    transcription_text = f.read()
                
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                jobs[job_id]['output_file'] = output_file
                jobs[job_id]['transcription'] = transcription_text[:1000] + '...' if len(transcription_text) > 1000 else transcription_text
                # Save jobs to file
                save_jobs()
            else:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['error'] = 'Output file not found'
                # Save jobs to file
                save_jobs()
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error'] = result.stderr
            # Save jobs to file
            save_jobs()
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
        # Save jobs to file
        save_jobs()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
          # Get original filename
        original_filename = file.filename
        # Create a timestamp prefix in format YYYYMMDD_HHMMSS
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        # Extract just the basename and append timestamp
        filename_base = os.path.basename(original_filename)
        save_filename = f"{timestamp}_{filename_base}"
        
        # Save the file
        filepath = os.path.join(UPLOAD_FOLDER, save_filename)
        file.save(filepath)
          # Initialize job status
        jobs[job_id] = {
            'id': job_id,
            'status': 'queued',
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'input_file': filepath,
            'saved_filename': save_filename,
            'original_filename': original_filename
        }
          # Start transcription in a background thread
        thread = threading.Thread(target=run_transcription, args=(job_id, filepath))
        thread.daemon = True
        thread.start()
        
        # Save jobs to file
        save_jobs()
        
        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': f'File {original_filename} uploaded and transcription queued'
        })

@app.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    if job_id in jobs:
        return jsonify(jobs[job_id])
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/jobs', methods=['GET'])
def list_jobs():
    return jsonify(list(jobs.values()))

@app.route('/download/<job_id>', methods=['GET'])
def download_file(job_id):
    if job_id in jobs and jobs[job_id].get('status') == 'completed':
        output_file = jobs[job_id]['output_file']
        return send_from_directory(os.path.dirname(output_file), 
                                 os.path.basename(output_file))
    else:
        return jsonify({'error': 'File not available for download'}), 404

@app.route('/', methods=['GET'])
def index():
    return send_from_directory('static', 'index.html')

# api runs on port 10301
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10301, debug=False)
