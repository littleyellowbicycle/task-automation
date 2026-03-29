FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    pip3 install --no-cache-dir sglang[all]==0.4.1

ENV MODEL_NAME=Qwen/Qwen3-0.6B
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python3", "-m", "sglang.launch_server", \
     "--model-path", "${MODEL_NAME}", \
     "--host", "${HOST}", \
     "--port", "${PORT}", \
     "--dtype", "half", \
     "--max-total-tokens", "4096", \
     "--context-length", "2048"]
