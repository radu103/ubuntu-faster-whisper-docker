from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect, url_for
import os
import subprocess
import time
import uuid
import threading
import json
import atexit
import sys
import secrets
from flask_session import Session
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

app = Flask(__name__, static_folder='static')

# Session configuration
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/app/code/sessions'  # Directory to store sessions
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
Session(app)

# Ensure sessions directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# User database - In a real app, this would be in a database
# Format: {username: hashed_password}
USERS = {}
USERS_FILE = '/app/code/users.json'

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

DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME')
DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD')

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

# Password hashing functions
def hash_password(password):
    # Generate a random salt
    salt = os.urandom(16)
    # Use PBKDF2 to derive a key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    # Hash the password
    key = kdf.derive(password.encode())
    # Return the salt and key as a base64-encoded string
    return base64.b64encode(salt + key).decode('utf-8')

def verify_password(stored_password, provided_password):
    try:
        # Decode the stored password
        decoded = base64.b64decode(stored_password.encode('utf-8'))
        salt = decoded[:16]
        stored_key = decoded[16:]
        
        # Hash the provided password with the same salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        # Attempt to verify the password
        kdf.verify(provided_password.encode(), stored_key)
        return True
    except Exception:
        return False

# Load users from file
def load_users():
    global USERS
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                USERS = json.load(f)
            print(f"Loaded {len(USERS)} users from file")
        except Exception as e:
            print(f"Error loading users file: {str(e)}")
            # If no users exist, create a default admin user
            if not USERS:
                create_default_admin()
    else:
        create_default_admin()

# Create default admin user
def create_default_admin():
    global USERS
    USERS[DEFAULT_ADMIN_USERNAME] = hash_password(DEFAULT_ADMIN_PASSWORD)
    save_users()
    print(f"Created default admin user: {DEFAULT_ADMIN_USERNAME}")

# Save users to file
def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(USERS, f)
    except Exception as e:
        print(f"Error saving users file: {str(e)}")

# Load users at startup
load_users()

# Authentication middleware
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and verify_password(USERS[username], password):
            session['username'] = username
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect('/')
        else:
            error = 'Invalid credentials'
            # Check if the request is from an API client or the static HTML page
            if 'application/json' in request.headers.get('Accept', ''):
                return jsonify({"error": error}), 401
            # If request came from the static login page, redirect back with error
            if request.referrer and 'login' in request.referrer:
                return redirect(f"/login?error={error}")
    
    # Default to template rendering
    return send_from_directory('static', 'login.html')

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
    print(f"Starting transcription for job {job_id} with file {filepath}")
    try:
        # Update job status to processing
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Get just the file name, not the full path
        filename = os.path.basename(filepath)
        
        # Run the voice2text.py script with the audio file
        result = subprocess.run(
            ['python3', '/app/code/voice2text.py', filepath],
            capture_output=True,
            text=True
        )
        
        # Check if the transcription was successful
        if result.returncode == 0:
            # Get output filename
            audio_name = os.path.splitext(filename)[0]

            date = time.strftime('%Y-%m-%d')

            # Create the output directory for the date if it doesn't exist
            output_folder = os.path.join(OUTPUT_FOLDER, date)
            os.makedirs(output_folder, exist_ok=True)

            # Save the file
            output_file = os.path.join(output_folder, f"{audio_name}_transcription.txt")
            
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            jobs[job_id]['output_folder'] = output_folder
            jobs[job_id]['output_file'] = output_file
            
            # Save jobs to file
            save_jobs()
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error'] = f"{result.returncode} {result.stdout} {result.stderr}"
            
            # Save jobs to file
            save_jobs()

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)

        # Save jobs to file
        save_jobs()

@app.route('/upload', methods=['POST'])
@login_required
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
        date = time.strftime('%Y-%m-%d')
        
        # Sanitize the filename by replacing spaces and commas with underscores
        sanitized_filename = original_filename.replace(" ", "_").replace(" ", "_").replace(" ", "_").replace(" ", "_").replace(" ", "_")
        sanitized_filename = sanitized_filename.replace(",", "_").replace(",", "_").replace(",", "_").replace(",", "_").replace(",", "_")
        sanitized_filename = sanitized_filename.replace("-", "_").replace("-", "_").replace("-", "_").replace("-", "_").replace("-", "_")
        
        # Extract just the basename and append timestamp
        filename_base = os.path.basename(sanitized_filename)
        save_filename = f"{timestamp}_{filename_base}"
        
        # Create the upload directory for the date if it doesn't exist
        folder = os.path.join(UPLOAD_FOLDER, date)
        os.makedirs(folder, exist_ok=True)

        # Save the file
        filepath = os.path.join(UPLOAD_FOLDER, date, save_filename)
        file.save(filepath)

        print(f"File saved to {filepath}")

        # Initialize job status
        jobs[job_id] = {
            'id': job_id,
            'status': 'queued',
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'upload_folder': folder,
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
@login_required
def get_job_status(job_id):
    if job_id in jobs:
        return jsonify(jobs[job_id])
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/jobs', methods=['GET'])
@login_required
def list_jobs():
    return jsonify(list(jobs.values()))

@app.route('/download/<job_id>', methods=['GET'])
@login_required
def download_file(job_id):
    if job_id in jobs and jobs[job_id].get('status') == 'completed':
        output_file = jobs[job_id]['output_file']
        return send_from_directory(os.path.dirname(output_file), 
                                 os.path.basename(output_file))
    else:
        return jsonify({'error': 'File not available for download'}), 404

@app.route('/', methods=['GET'])
@login_required
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['GET'])
def static_login():
    return send_from_directory('static', 'login.html')

# api runs on port 10301
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10301, debug=False)
