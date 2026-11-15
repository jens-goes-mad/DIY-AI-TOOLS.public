# ai-tools: TTS (Kokoro), ffmpeg and the ai-tools CLI (README.md).
#
#   docker build -t ai-tools .            (or just run bin/ai-tools -- it builds on first use)
#   docker run --rm --entrypoint pytest ai-tools /opt/ai-tools/tests
#
# The Kokoro model and voices are not in the image: they download on first
# use into the Hugging Face cache under /voices (bin/ai-tools mounts the
# named volume ai-tools-voices there).

FROM debian:bookworm-slim

# espeak-ng: Kokoro's (misaki's) fallback for words it has no pronunciation for.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg python3 python3-venv ca-certificates espeak-ng \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/voices/huggingface

# Pinned: the voice's sound and the stories' hashes depend on the engine version.
# One pip run with PyTorch's CPU index first, so nothing pulls in the CUDA build
# (several GB, useless without a GPU -- Docker on macOS has none).
# kokoro and misaki: Apache-2.0 (checked 2026-11-15, their package metadata).
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
        torch==2.15.0+cpu kokoro==0.9.4 "misaki[en]==0.9.4" soundfile pillow==10.4.0 pytest==8.3.3 \
 && pip install --no-cache-dir \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

COPY pyproject.toml /opt/ai-tools/
COPY src /opt/ai-tools/src
COPY tests /opt/ai-tools/tests
RUN pip install --no-cache-dir /opt/ai-tools

VOLUME /voices
ENTRYPOINT ["ai-tools"]
