FROM ubuntu:22.04

# Set non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# prepare for cuda installation
RUN apt-get update
RUN apt-get -y install wget

# This is required for installing CUDA drivers and toolkit
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
RUN dpkg -i cuda-keyring_1.1-1_all.deb
RUN apt-get update
RUN apt-get -y install cuda-drivers cuda-toolkit-12-9
RUN apt-get install -y cudnn9-cuda-12

# Install system dependencies
RUN apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    git \
    zlib1g

# clean up
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

# Install PyTorch with CUDA 12 support
RUN pip3 install torch torchvision torchaudio

# for model download optimization
RUN pip3 install hf_xet

# Install faster-whisper
RUN pip3 install faster-whisper

# Create working directory
WORKDIR /app

# Set the entry point command 
CMD ["/bin/bash"]