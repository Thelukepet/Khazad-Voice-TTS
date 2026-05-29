"""
Configuration package for Khazad Voice TTS.

Exports a ``get_config()`` helper for obtaining the singleton
``ConfigManager`` instance without calling the constructor directly.
"""

from .ConfigManager import ConfigManager

_instance: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Return the singleton :class:`ConfigManager` instance.

    Prefer this over calling ``ConfigManager()`` directly — the intent
    is explicit and readers don't need to know about the ``SingletonMeta``
    metaclass to understand that the same object is returned each time.
    """
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance
