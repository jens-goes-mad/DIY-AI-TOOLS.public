"""Piper (https://github.com/OHF-Voice/piper1-gpl, GPL-3.0-or-later) as the
TTS engine. The only module that imports it."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path


def describe(voice: str) -> dict:
    """The engine and voice as they go into every story's hash -- without
    loading the model, so a run where nothing changed never loads it."""
    return {"engine": "piper", "engineVersion": importlib.metadata.version("piper-tts"), "voice": voice}


class PiperEngine:
    def __init__(self, voice: str, voices_dir: Path, tempo: float = 1.0, variation: float | None = None,
                 expression: float | None = None):
        """`tempo`: speaking rate relative to the voice's own (0.9 = 10% slower).
        `variation`: Piper's noise_w -- how much sound lengths vary at random
        (the voice's own value if None; en_GB-cori-high 0.8, lower = steadier).
        `expression`: Piper's noise_scale -- how much intonation varies (the
        voice's own if None; cori 0.667, lower = calmer, less theatrical)."""
        from piper import PiperVoice  # imported here: the pure modules and tests don't need piper
        from piper.config import SynthesisConfig

        model = ensure_voice(voice, voices_dir)
        self._voice = PiperVoice.load(model)
        self.sample_rate = self._voice.config.sample_rate
        # length_scale stretches phoneme durations: the voice's own value
        # (1 for en_GB-cori-high) divided by the tempo.
        self._config = SynthesisConfig(length_scale=self._voice.config.length_scale / tempo,
                                       noise_w_scale=variation, noise_scale=expression)

    def synthesize(self, sentence: str) -> bytes:
        """One sentence as 16-bit mono PCM at self.sample_rate."""
        return b"".join(chunk.audio_int16_bytes for chunk in self._voice.synthesize(sentence, syn_config=self._config))


def ensure_voice(voice: str, voices_dir: Path) -> Path:
    """The voice's model in `voices_dir`, downloaded on first use."""
    voices_dir = Path(voices_dir)
    model = voices_dir / f"{voice}.onnx"
    if not (model.exists() and model.with_name(model.name + ".json").exists()):
        voices_dir.mkdir(parents=True, exist_ok=True)
        print(f"downloading voice {voice} into {voices_dir}", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(voices_dir), voice],
                       check=True)
    if not model.exists():
        raise SystemExit(f"voice {voice}: no {model} after downloading -- is the name right?")
    return model
