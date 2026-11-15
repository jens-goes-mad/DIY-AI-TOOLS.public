"""Kokoro-82M (https://github.com/hexgrad/kokoro, Apache-2.0 code and weights)
as the TTS engine. The only module that imports it.

Voices are named <language><gender>_<name>: `af_heart` = American English,
female. The first letter picks Kokoro's language pipeline ('a' American,
'b' British English). The model and voices are downloaded on first use into
the Hugging Face cache (HF_HOME -- the Docker volume ai-tools-voices).

Pronunciation: Kokoro reads `[word](/phonemes/)` inline -- the lexicon's
values may use it (misaki's phoneme set, not espeak's IPA).
"""

import importlib.metadata

SAMPLE_RATE = 24_000
REPO = "hexgrad/Kokoro-82M"


def describe(voice: str) -> dict:
    """The engine and voice as they go into every story's hash -- without
    loading the model, so a run where nothing changed never loads it."""
    return {"engine": "kokoro", "engineVersion": importlib.metadata.version("kokoro"), "voice": voice}


class KokoroEngine:
    sample_rate = SAMPLE_RATE

    def __init__(self, voice: str, tempo: float = 1.0):
        """`tempo`: Kokoro's speed, 1.0 = the voice's own (0.9 = 10% slower)."""
        from kokoro import KPipeline  # imported here: the pure modules and tests don't need it

        lang = voice[:1]
        if lang not in ("a", "b"):
            raise SystemExit(f"voice {voice}: only English voices (a… American, b… British) are set up")
        self._pipeline = KPipeline(lang_code=lang, repo_id=REPO)
        self._voice = voice
        self._speed = tempo

    def synthesize(self, sentence: str) -> bytes:
        """One sentence as 16-bit mono PCM at SAMPLE_RATE."""
        import numpy as np

        chunks = [result.audio.numpy() for result in self._pipeline(sentence, voice=self._voice, speed=self._speed)
                  if result.audio is not None]
        if not chunks:
            return b""
        audio = np.concatenate(chunks)
        return (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
