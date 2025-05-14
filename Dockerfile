FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update 
RUN apt-get install -y \
    sudo \
    python3 \
    python3-distutils \
    python3-pip \
    ffmpeg

# clean up
RUN apt-get clean

# Upgrade pip
RUN pip install --upgrade pip

# Install openai-whisper + hf_xet
RUN pip install -U openai-whisper hf_xet

# clean up
RUN pip cache purge

# Set working directory
WORKDIR /app

# default command
CMD ["whisper"]