# Imports

# > Standard Library
import configparser
import os
import sys
from pathlib import Path


# Singleton Metaclass
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class ConfigManager(metaclass=SingletonMeta):
    """Central configuration manager for Khazad Voice TTS.

    Paths are split into two categories:

    * ``base_dir`` – the project root (where pyproject.toml lives).
      Holds **embedded resources** that ship with the app (templates,
      reference audio, npc_data.csv).
    * ``user_data_dir`` – ``~/.khazad-voice-tts/``.
      Holds **generated data** produced at runtime (config, calibration
      layouts, NPC memory, downloaded models, screenshots).
    """

    # --- Cross-platform user data directory ---
    USER_DATA_DIR = Path.home() / ".khazad-voice-tts"

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.base_dir = self._find_project_root()

        # Ensure user data directory exists
        self.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.config_path = self.USER_DATA_DIR / "config.ini"
        self.config.read(self.config_path)

        self._cached_device = None
        self._cached_tesseract_cmd = None

        # Load defaults into memory first
        self._load_memory_defaults()

        # Check if the file exists
        if not self.config_path.exists():
            # If completely new user, write the defaults to disk
            with open(self.config_path, "w") as configfile:
                self.config.write(configfile)
        else:
            # If it does exist, read it.
            # This overwrites memory defaults with user's custom settings,
            self.config.read(self.config_path)

    @staticmethod
    def _find_project_root() -> Path:
        """Walk up from this file until we find the project root (has pyproject.toml)."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        # Fallback if pyproject.toml was removed or we're in a weird environment
        return Path(__file__).resolve().parent.parent.parent

    def _detect_script_log_path(self) -> str:
        """Resolve the LOTRO Script.log path for the current platform.

        On Windows, the Documents folder can be relocated (e.g. to ``D:\\Documents``).
        This method reads the actual location from the Windows registry and falls
        back to ~/Documents on other platforms.
        """
        lotro_rel = os.path.join("The Lord of the Rings Online", "Script.log")

        if sys.platform != "win32":
            return os.path.join(os.path.expanduser("~"), "Documents", lotro_rel)

        # Try to read the real Documents folder from the Windows registry.
        doc_dirs: list[str] = []
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                docs_raw, _ = winreg.QueryValueEx(key, "Personal")
                docs = os.path.expandvars(docs_raw)
                doc_dirs.append(docs)

                # If the resolved path exists, check for Script.log inside it.
                candidate = os.path.join(docs, lotro_rel)
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass

        # Fallback to the registry-resolved Documents dir (even if Script.log
        # doesn't exist there yet) or finally to ~/Documents.
        if doc_dirs:
            return os.path.join(doc_dirs[0], lotro_rel)

        return os.path.join(os.path.expanduser("~"), "Documents", lotro_rel)

    def _load_memory_defaults(self):
        """
        Generates the default configuration file if it doesn't exist.
        """

        # Paths – embedded resources (ship with the app)
        self.config["Paths"] = {
            "data_dir": str(self.base_dir / "data"),
            "ref_audio_dir": str(self.base_dir / "data" / "reference_audio"),
            "templates_dir": str(self.base_dir / "templates"),
            "npc_data_path": str(self.base_dir / "data" / "npc_data.csv"),
            # Generated data (user-specific, in home directory)
            "user_data_dir": str(self.USER_DATA_DIR),
            "screenshots_dir": str(self.USER_DATA_DIR / "screenshots"),
        }

        # Detection settings
        self.config["Detection"] = {
            "base_resolution_x": "2560",
            "base_resolution_y": "1440",
            "template_threshold": "0.7",
            "static_template_threshold": "0.7",
        }

        # Text box offsets ?
        self.config["TextBoxOffsets"] = {
            "corner_offset_x": "5",
            "corner_offset_y": "5",
            "padding_icon_y": "5",
            "padding_intersect_x": "5",
            "min_box_dim": "50",
        }

        # Layout offsets for retail mode
        self.config["DefaultRetailMode"] = {
            "plugin_script_log_path": self._detect_script_log_path(),
            "layout_corner_offset_x": "11",
            "layout_corner_offset_y": "10",
            "layout_padding_intersect_x": "-10",
            "layout_padding_icon_y": "17",
        }

        # Layout offsets for echoes mode
        self.config["DefaultRetailOffsets"] = {
            "body_left_margin": "11",
            "body_top_margin": "10",
            "body_right_padding": "0",
            "body_bottom_padding": "0",
        }

        # TTS settings
        self.config["TTSSettings"] = {
            "sample_rate": "24000",
            "default_volume": "0.4",
            "omnivoice_volume": "0.5",
            "tts_speed": "1.1",
            "tts_wave_steps": "16",
            "quest_window_mode": "auto",
            "quest_window_box_x": "555",
            "quest_window_box_y": "380",
            "quest_window_width": "425",
            "quest_window_height": "539",
            "quest_trigger_mode": "manual",
            "quest_trigger_key": "middle_mouse",
            "npc_name_max_age": "60",
        }

        # OCR settings
        self.config["OCRSettings"] = {
            "tesseract_cmd": "auto"  # Default to auto-discovery
        }

        # LOG settings
        self.config["LogSettings"] = {
            "log_level": "INFO",
            "debug_template_scores": "False",
        }

        # Wiki settings
        self.config["WikiSettings"] = {
            "enable_wiki": "False",
            "wiki_base_url": "https://lotro-wiki.com",
            "missing_text_indicator": "There is currently no text in this page",
        }

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Helper to safely grab integers from the config."""
        return self.config.getint(section, key, fallback=fallback)

    def get_str(self, section: str, key: str, fallback: str = "") -> str:
        """Helper to safely grab strings from the config."""
        return self.config.get(section, key, fallback=fallback)

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """Helper to safely grab booleans from the config."""
        return self.config.getboolean(section, key, fallback=fallback)

    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Helper to safely grab floats from the config."""
        return self.config.getfloat(section, key, fallback=fallback)

    @property
    def device(self) -> str:
        """
        Get the device to use for TTS.
        """
        if self._cached_device is not None:
            return self._cached_device

        user_pref = self.config.get("System", "device", fallback="auto").lower()

        if user_pref == "auto":
            try:
                import torch

                self._cached_device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._cached_device = "cpu"
        else:
            self._cached_device = user_pref

        return self._cached_device

    @device.setter
    def device(self, new_device: str):
        """
        Set the device to use for TTS.
        """
        valid_devices = ["auto", "cuda", "cpu"]
        if new_device.lower() not in valid_devices:
            raise ValueError(f"Device must be one of {valid_devices}")

        if not self.config.has_section("System"):
            self.config.add_section("System")

        self.config.set("System", "device", new_device.lower())
        self._cached_device = None

        with open(self.config_path, "w") as configfile:
            self.config.write(configfile)

    @property
    def tesseract_cmd(self) -> str:
        """
        Getter for the Tesseract executable path.
        If set to 'auto' in the config, it attempts to find it dynamically.
        """
        if self._cached_tesseract_cmd is not None:
            return self._cached_tesseract_cmd

        user_pref = self.config.get("OCRSettings", "tesseract_cmd", fallback="auto")

        if user_pref.lower() == "auto":
            if sys.platform == "linux":
                self._cached_tesseract_cmd = r"tesseract"
            else:
                # Windows search logic
                possible_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    os.path.expanduser(
                        r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
                    ),
                ]

                # Default fallback
                self._cached_tesseract_cmd = (
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                )

                for p in possible_paths:
                    if os.path.exists(p):
                        self._cached_tesseract_cmd = p
                        break
        else:
            # The user manually provided a path in the INI file
            self._cached_tesseract_cmd = user_pref

        return self._cached_tesseract_cmd

    @tesseract_cmd.setter
    def tesseract_cmd(self, new_cmd: str):
        """Allows updating the path dynamically from a GUI"""
        if not self.config.has_section("OCRSettings"):
            self.config.add_section("OCRSettings")

        self.config.set("OCRSettings", "tesseract_cmd", new_cmd)
        self._cached_tesseract_cmd = None  # Reset cache so it loads the new path

        with open(self.config_path, "w") as configfile:
            self.config.write(configfile)


if __name__ == "__main__":
    config = ConfigManager()
