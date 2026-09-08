FROM python:3.11-slim

# ffmpeg is needed by faster-whisper/av for audio decoding paths
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY run.py .

ENV STT_HOST=0.0.0.0
ENV STT_PORT=8000
EXPOSE 8000

# For GPU deployment, base this image on nvidia/cuda instead and set STT_DEVICE=cuda / COMPUTE_TYPE=float16
CMD ["python", "run.py"]
