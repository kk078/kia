# mypy: ignore-errors
"""Audio transcription for KIA via local faster-whisper.

Provider-free speech-to-text: the audio never leaves the machine. The model is
loaded lazily and cached per size. Install the optional dep first:

    pip install faster-whisper

Model size is settings.whisper_model (tiny/base/small/medium/large-v3); larger =
more accurate but slower and heavier to download.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from brain_core.config import settings

_MODEL_CACHE: dict[str, object] = {}


def _get_model(size: str):
    """Load (and cache) a faster-whisper model. Raises ImportError if the dep is missing."""
    if size in _MODEL_CACHE:
        return _MODEL_CACHE[size]
    from faster_whisper import WhisperModel  # lazy: optional dependency

    # CPU + int8 is the safe default; it runs anywhere without a GPU.
    model = WhisperModel(size, device="auto", compute_type="int8")
    _MODEL_CACHE[size] = model
    return model


def _transcribe_sync(audio_bytes: bytes, suffix: str, size: str) -> str:
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        model = _get_model(size)
        segments, _info = model.transcribe(tmp_path)
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


async def transcribe_audio(audio_bytes: bytes, suffix: str = ".wav") -> str:
    """Transcribe audio bytes to text. Runs the blocking model off the event loop."""
    size = settings.whisper_model
    return await asyncio.to_thread(_transcribe_sync, audio_bytes, suffix, size)
