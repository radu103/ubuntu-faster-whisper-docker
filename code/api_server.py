from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import subprocess
import time
import uuid
import threading
import json
import atexit
import sys

app = Flask(__name__, static_folder='static')

# Configure upload and output directories
UPLOAD_FOLDER = '/app/audio'
OUTPUT_FOLDER = '/app/output'
JOBS_FILE = '/app/code/static/jobs.json'

# PostgreSQL configuration from environment variables
PG_HOST = os.environ.get('POSTGRES_HOST')
PG_PORT = os.environ.get('POSTGRES_PORT', '5432')
PG_DB = os.environ.get('POSTGRES_DB')
PG_USER = os.environ.get('POSTGRES_USER')
PG_PASSWORD = os.environ.get('POSTGRES_PASSWORD')

# Flag to determine if PostgreSQL should be used
USE_POSTGRES = all([PG_HOST, PG_DB, PG_USER, PG_PASSWORD])

# If PostgreSQL is configured, import the necessary module
if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    print("PostgreSQL support enabled")

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Dictionary to store job status
jobs = {}

# Initialize PostgreSQL if needed
def init_postgres():
    if not USE_POSTGRES:
        return
    
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )
        
        with conn.cursor() as cur:
            # Create the jobs table if it doesn't exist
            cur.execute('''
                CREATE TABLE IF NOT EXISTS transcription_jobs (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL
                )
            ''')
            conn.commit()
        conn.close()
        print("PostgreSQL database initialized")
    except Exception as e:
        print(f"Error initializing PostgreSQL: {str(e)}")
        print("Falling back to file-based storage")

# Load existing jobs from PostgreSQL or file
def load_jobs():
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                database=PG_DB,
                user=PG_USER,
                password=PG_PASSWORD
            )
            
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute('SELECT id, data FROM transcription_jobs')
                job_data = {}
                for row in cur:
                    job_data[row[0]] = row[1]
                conn.close()
                print(f"Loaded {len(job_data)} jobs from PostgreSQL")
                return job_data
        except Exception as e:
            print(f"Error loading jobs from PostgreSQL: {str(e)}")
            print("Falling back to file-based storage")
    
    # Fall back to file-based storage
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r') as f:
                job_data = json.load(f)
                print(f"Loaded {len(job_data)} jobs from file")
                return job_data
        except Exception as e:
            print(f"Error loading jobs file: {str(e)}")
    
    return {}

# Save jobs to PostgreSQL or file
def save_jobs():
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                database=PG_DB,
                user=PG_USER,
                password=PG_PASSWORD
            )
            
            with conn.cursor() as cur:
                for job_id, job_data in jobs.items():
                    # Use UPSERT (INSERT ... ON CONFLICT UPDATE) to handle both new and updated jobs
                    cur.execute(
                        'INSERT INTO transcription_jobs (id, data) VALUES (%s, %s) '
                        'ON CONFLICT (id) DO UPDATE SET data = %s',
                        (job_id, json.dumps(job_data), json.dumps(job_data))
                    )
                conn.commit()
            conn.close()
            return
        except Exception as e:
            print(f"Error saving jobs to PostgreSQL: {str(e)}")
            print("Falling back to file-based storage")
    
    # Fall back to file-based storage
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Error saving jobs file: {str(e)}")

# Initialize PostgreSQL if it's configured
if USE_POSTGRES:
    init_postgres()

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
