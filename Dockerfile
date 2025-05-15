FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies and clean up in a single layer
RUN apt-get update && \
    apt-get install -y \
    sudo \
    wget \
    curl \
    python3 \
    python3-distutils \
    python3-pip \
    ffmpeg && \ 
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install all Python dependencies and clean up in a single layer
RUN pip install -U \
    faster-whisper \
    hf_xet \
    flask \
    flask-cors \
    requests \
    numpy \
    tqdm \
    torch \
    torchvision \
    torchaudio \
    pydub \
    jsonschema \
    librosa && \ 
    pip cache purge

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/audio /app/output /app/code/static

# Copy the code into the container
COPY ./code /app/code

# expose ports
EXPOSE 10301

# default command to run the API server
CMD ["python3", "/app/code/api_server.py"]