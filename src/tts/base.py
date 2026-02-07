# Imports

# > Standard Library
from abc import ABC, abstractmethod

# > Third-Party Dependencies
import numpy as np


class TTSBackend(ABC):
    """
    Abstract base class for Text-to-Speech backends.
    Ensures all TTS engines implement the required methods for the game engine.
    """

    @abstractmethod
    def pick_voice(self, gender: str, race: str) -> tuple[str, str]:
        """
        Selects a voice ID based on the NPC's gender and race.

        Parameters
        ----------
        gender : str
            The gender of the NPC (e.g., 'Male', 'Female').
        race : str
            The race of the NPC (e.g., 'Elf', 'Dwarf', 'Man').

        Returns
        -------
        tuple[str, str]
            A tuple containing:
            - voice_id (str): The internal ID used by the generator.
            - category (str): The category key for logging/memory (e.g., 'dwarf_male').
        """
        pass

    @abstractmethod
    def generate(self, text: str, voice_id: str) -> np.ndarray:
        """
        Generates audio for the given text.

        Parameters
        ----------
        text : str
            The sentence or paragraph to speak.
        voice_id : str
            The voice ID returned by `pick_voice`.

        Returns
        -------
        np.ndarray
            A 1D float32 numpy array representing the audio waveform.
            Returns an empty array if generation fails.
        """
        pass
