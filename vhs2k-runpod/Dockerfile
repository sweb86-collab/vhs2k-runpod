FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    ffmpeg wget ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /workspace/requirements.txt
RUN pip3 install --no-cache-dir -r /workspace/requirements.txt

# Real-ESRGAN ncnn Vulkan binary
# Provide a direct download URL at build time via --build-arg
ARG REALESRGAN_URL=
RUN mkdir -p /opt/realesrgan \
    && if [ -n "$REALESRGAN_URL" ]; then \
        wget -O /opt/realesrgan/realesrgan.zip "$REALESRGAN_URL" \
        && unzip /opt/realesrgan/realesrgan.zip -d /opt/realesrgan \
        && rm /opt/realesrgan/realesrgan.zip \
        && BIN_PATH="$(find /opt/realesrgan -type f -name realesrgan-ncnn-vulkan | head -n 1)" \
        && if [ -z "$BIN_PATH" ]; then echo "realesrgan-ncnn-vulkan not found"; exit 1; fi \
        && chmod +x "$BIN_PATH" \
        && ln -sf "$BIN_PATH" /usr/local/bin/realesrgan-ncnn-vulkan; \
    else \
        echo "REALESRGAN_URL is empty; cannot install realesrgan-ncnn-vulkan" \
        && exit 1; \
    fi

ENV PATH="/opt/realesrgan:${PATH}"
RUN command -v realesrgan-ncnn-vulkan && realesrgan-ncnn-vulkan -h >/dev/null 2>&1

# App
COPY handler.py pipeline.py config.py main.py /workspace/
COPY .env.example /workspace/.env.example

WORKDIR /workspace
CMD ["python3", "main.py"]
