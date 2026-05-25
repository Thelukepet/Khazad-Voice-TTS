"""
Khazad-Voice TTS - Main package.

Exports core modules and models.

Heavy submodules (audio, engine, ocr, wiki, …) are lazily imported
via __getattr__ so that tests and lightweight consumers don't need
every runtime dependency (numpy, torch, kokoro, …) installed.
"""

import importlib as _importlib

from .models import NPC, QuestText, QuestTextLine, TextSourceType, VoiceSelection

__all__ = [
    # Models
    "NPC",
    "QuestText",
    "QuestTextLine",
    "VoiceSelection",
    "TextSourceType",
    # Modules
    "models",
    "utils",
    "db_sqlite",
    "ocr",
    "wiki",
    "audio",
    "engine",
    "config",
]

# Map of lazy-importable submodules.
_SUBMODULES = {
    "audio": ".audio",
    "config": ".config",
    "db_sqlite": ".db_sqlite",
    "engine": ".engine",
    "models": ".models",
    "ocr": ".ocr",
    "utils": ".utils",
    "wiki": ".wiki",
}


def __getattr__(name):
    """Lazy import of submodules to avoid pulling in heavy dependencies eagerly."""
    if name in _SUBMODULES:
        mod = _importlib.import_module(_SUBMODULES[name], __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
