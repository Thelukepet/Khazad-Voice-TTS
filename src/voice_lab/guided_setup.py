"""Guided setup flow for the Voice Lab.

Chains the screenshot pipeline test into a full end-to-end preview:
the screenshot is tested, the voice the engine would actually use for
the matched quest's NPC is resolved, and a snippet of the matched text
is generated with the user's real TTS backend - so the user hears
exactly what the narrator would say in game, before configuring
anything.
"""

from typing import Any, Dict, Optional, Tuple

import numpy as np

# Shared, lazily created resources (loading takes seconds)
_DB = None
_BACKENDS: Dict[str, Any] = {}


def _get_db():
    global _DB
    if _DB is None:
        from src.db_sqlite import NPCDatabaseSQLite

        _DB = NPCDatabaseSQLite()
    return _DB


def _get_backend(device: str):
    """Cached TTS backend for the given device choice."""
    key = device or "cpu"
    if key not in _BACKENDS:
        from src.tts import get_tts_backend

        _BACKENDS[key] = get_tts_backend(device_choice=key)
    return _BACKENDS[key]


def detect_gpu() -> bool:
    """Best-effort NVIDIA GPU detection (same logic as the wizard)."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def resolve_voice(npc_name: str, device: str) -> Dict[str, Any]:
    """Resolve the voice the engine would use for a quest's NPC.

    Mirrors NarratorEngine._resolve_voice: NPC name -> database lookup
    (gender/race) -> backend voice pick.

    Returns
    -------
    dict
        ``voice_id``, ``category``, ``gender``, ``race``, ``npc_name``,
        ``matched_name``.
    """
    db = _get_db()
    gender, race, matched = db.lookup(npc_name) if npc_name else (None, None, npc_name)
    tts = _get_backend(device)
    voice_id, category = tts.pick_voice(gender, race)
    return {
        "voice_id": voice_id,
        "category": category,
        "gender": gender or "unknown",
        "race": race or "unknown",
        "npc_name": npc_name or "",
        "matched_name": matched or npc_name or "",
    }


def generate_snippet(
    narrated_text: str, device: str, voice_id: str, max_sentences: int = 2
) -> Tuple[int, np.ndarray]:
    """Generate a short spoken preview of the matched quest text.

    Takes the first few sentences so the preview stays quick, and uses
    the same backend and voice the narrator would use live.

    Returns
    -------
    tuple
        (sample_rate, waveform) for Gradio's Audio component.
    """
    import nltk

    sentences = nltk.sent_tokenize(narrated_text)
    snippet = " ".join(sentences[:max_sentences]) if sentences else narrated_text
    if len(snippet) > 400:
        snippet = snippet[:400]

    tts = _get_backend(device)
    wav = tts.generate(snippet, voice_id)
    if wav is None or len(wav) == 0:
        raise RuntimeError("The TTS backend produced no audio.")
    return tts.samplerate, np.asarray(wav).squeeze()
