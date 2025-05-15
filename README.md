# Ubuntu Faster-Whisper Docker

A Docker container based on Ubuntu 22.04 LTS with [faster-whisper](https://github.com/guillaumekln/faster-whisper) installed. This container provides a ready-to-use environment for running OpenAI's Whisper automatic speech recognition (ASR) model with improved performance.

## Features

- Based on Ubuntu 22.04 LTS
- CUDA support for GPU acceleration
- Python 3 with PyTorch and faster-whisper pre-installed
- FFmpeg for audio processing

## Building and Running with Docker

### Building the Docker Image

```bash
docker build -t ubuntu-faster-whisper .
```

### Running the Container

#### Basic Usage

```bash
docker run -it --rm ubuntu-faster-whisper
```

#### With GPU Support

```bash
docker run -it --rm --gpus all ubuntu-faster-whisper
```

### Tagging and Pushing to a Docker Registry

After building your image, you may want to tag it and push it to a Docker registry for sharing or deployment:

#### Tag the Image

```bash
docker tag ubuntu-faster-whisper:latest radu103/ubuntu-faster-whisper:latest
```

#### Push to Docker Hub

```bash
# Login to Docker Hub first
docker login

# Push the image
docker push radu103/ubuntu-faster-whisper:latest
```

## Using Docker Compose

A docker-compose.yml file is included for easier management of the container.

### Starting the Container

```bash
docker-compose up -d
```

This will:
- Build the image if it doesn't exist
- Start the container in detached mode
- Mount the ./audio and ./output directories
- Enable GPU support if available

### Run the conversion

```bash
python3 /app/code/voice2text.py "/app/audio/Cu cine votează Victor Ponta pe 18 mai_ Credeam cu Simion, dar s-a trezit să mă facă cu ou și oțet.mp3"
```

### Stopping the Container

```bash
docker-compose down
```

## Using the REST API

The container includes a REST API server for uploading audio files and managing transcription jobs.

### Accessing the API

When the container is running, the API is available at:

```
http://localhost:10301
```

### API Endpoints

- **GET /** - Web interface with simple upload form
- **POST /upload** - Upload an audio file for transcription
- **GET /jobs/:job_id** - Get status of a specific job
- **GET /jobs** - List all jobs
- **GET /download/:job_id** - Download transcription result

### Storage Options

The system supports two storage backends for job persistence:

1. **File-based storage** (default) - Stores job information in a JSON file
2. **PostgreSQL database** - Stores job information in a PostgreSQL database

To enable PostgreSQL storage, uncomment the PostgreSQL environment variables in docker-compose.yml:

```yaml
- POSTGRES_HOST=postgres
- POSTGRES_PORT=5432
- POSTGRES_DB=whisper
- POSTGRES_USER=whisper
- POSTGRES_PASSWORD=whisperpassword
```

If using PostgreSQL, the container will automatically detect and connect to the database. If the PostgreSQL connection fails, the system will automatically fall back to file-based storage.

### Example: Upload a file with cURL

```bash
# Upload audio file for transcription
curl -X POST -F "file=@your_audio.mp3" http://localhost:10301/upload
```

### Example: Check job status

```bash
# Get job status
curl http://localhost:10301/jobs/YOUR_JOB_ID
```

### Example: Download transcription

```bash
# Download the transcription file
curl -O http://localhost:10301/download/YOUR_JOB_ID
```

### Cleaning Up Docker Resources

After building and using Docker images, you might want to clean up unused resources to save disk space:

```powershell
# Remove all stopped containers
docker container prune -f

# Remove unused images
docker image prune -f

# Remove all unused build cache
docker builder prune -f

# For a complete cleanup (use with caution - removes all unused containers, networks, images, and volumes)
docker system prune -f
```

## System Requirements

- Docker and Docker Compose installed
- For GPU support: NVIDIA GPU with CUDA support and nvidia-container-toolkit installed