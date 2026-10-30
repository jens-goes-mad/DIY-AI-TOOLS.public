"""Joining synthesized sentences into one narration, and encoding it."""

import subprocess
import wave
from pathlib import Path

SAMPLE_WIDTH = 2  # 16-bit mono PCM, what the TTS engines deliver


def silence(ms: float, sample_rate: int) -> bytes:
    return b"\x00" * (round(sample_rate * ms / 1000) * SAMPLE_WIDTH)


def assemble(sentences: list[list[bytes | float]], sample_rate: int,
             sentence_pause_ms: float) -> tuple[bytes, list[tuple[float, float] | None]]:
    """One narration from sentences, each a list of speech (16-bit mono PCM
    bytes) and pauses (ms, a float) in order; `sentence_pause_ms` of silence
    between sentences. Returns the audio and per sentence the (start_ms,
    end_ms) of its speech -- the subtitle times -- or None for a sentence
    that is only pauses."""
    out = bytearray()
    spans = []
    for n, items in enumerate(sentences):
        if n:
            out += silence(sentence_pause_ms, sample_rate)
        first = last = None
        for item in items:
            if isinstance(item, bytes):
                if first is None:
                    first = len(out)
                out += item
                last = len(out)
            else:
                out += silence(item, sample_rate)
        spans.append(None if first is None else (to_ms(first, sample_rate), to_ms(last, sample_rate)))
    return bytes(out), spans


def to_ms(byte_count: int, sample_rate: int) -> float:
    return byte_count / SAMPLE_WIDTH / sample_rate * 1000


def write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    """LAME through ffmpeg; the LAME header records the encoder delay, so
    decoders (ffmpeg too) start at the first real sample -- the mp3 lines up
    with the wav's timing."""
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav_path),
         "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)],
        check=True,
    )
