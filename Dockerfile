# ai-tools: TTS (Piper), ffmpeg and the ai-tools CLI (README.md).
#
#   docker build -t ai-tools .            (or just run bin/ai-tools -- it builds on first use)
#   docker run --rm --entrypoint pytest ai-tools /opt/ai-tools/tests
#
# Voices are not in the image: they download on first use into /voices
# (bin/ai-tools mounts the named volume ai-tools-voices there).

FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    AI_TOOLS_VOICES=/voices

# Pinned: the voice's sound and the stories' hashes depend on the engine version.
# piper-tts is GPL-3.0-or-later (checked 2026-10-30, its METADATA).
RUN pip install --no-cache-dir piper-tts==1.8.0 pillow==10.4.0 pytest==8.3.3

COPY pyproject.toml /opt/ai-tools/
COPY src /opt/ai-tools/src
COPY tests /opt/ai-tools/tests
RUN pip install --no-cache-dir /opt/ai-tools

VOLUME /voices
ENTRYPOINT ["ai-tools"]
