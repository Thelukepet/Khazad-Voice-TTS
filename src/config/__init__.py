# # src/config/__init__.py
# #
# # Backward-compatible module-level exports.
# # All values are now read from ConfigManager (INI file) instead of
# # being hardcoded as Python constants.

# from pathlib import Path

# from .ConfigManager import ConfigManager

# _cfg = ConfigManager()

# # ---------------------------------------------------------------------------
# # Paths
# # ---------------------------------------------------------------------------
# BASE_DIR = _cfg.base_dir
# DATA_DIR = Path(_cfg.get_str("Paths", "data_dir"))
# SAMPLES_DIR = Path(_cfg.get_str("Paths", "samples_dir"))
# REF_AUDIO_DIR = Path(_cfg.get_str("Paths", "ref_audio_dir"))
# NPC_DATA_PATH = Path(_cfg.get_str("Paths", "npc_data_path"))
# TEMPLATES_DIR = Path(_cfg.get_str("Paths", "templates_dir"))

# # ---------------------------------------------------------------------------
# # Wiki Settings
# # ---------------------------------------------------------------------------
# WIKI_BASE_URL = _cfg.get_str(
#     "WikiSettings", "wiki_base_url", fallback="https://lotro-wiki.com"
# )
# MISSING_TEXT_INDICATOR = _cfg.get_str(
#     "WikiSettings",
#     "missing_text_indicator",
#     fallback="There is currently no text in this page",
# )

# # ---------------------------------------------------------------------------
# # Detection Settings
# # ---------------------------------------------------------------------------
# TEMPLATE_THRESHOLD = _cfg.get_float("Detection", "template_threshold", fallback=0.7)
# STATIC_TEMPLATE_THRESHOLD = _cfg.get_float(
#     "Detection", "static_template_threshold", fallback=0.7
# )
# BASE_RESOLUTION = (
#     _cfg.get_int("Detection", "base_resolution_x", fallback=2560),
#     _cfg.get_int("Detection", "base_resolution_y", fallback=1440),
# )

# # ---------------------------------------------------------------------------
# # Debug
# # ---------------------------------------------------------------------------
# DEBUG_TEMPLATE_SCORES = _cfg.get_bool(
#     "LogSettings", "debug_template_scores", fallback=False
# )

# # ---------------------------------------------------------------------------
# # Text Box Offsets
# # ---------------------------------------------------------------------------
# CORNER_OFFSET_X = _cfg.get_int("TextBoxOffsets", "corner_offset_x", fallback=5)
# CORNER_OFFSET_Y = _cfg.get_int("TextBoxOffsets", "corner_offset_y", fallback=5)
# PADDING_ICON_Y = _cfg.get_int("TextBoxOffsets", "padding_icon_y", fallback=5)
# PADDING_INTERSECT_X = _cfg.get_int("TextBoxOffsets", "padding_intersect_x", fallback=5)
# MIN_BOX_DIM = _cfg.get_int("TextBoxOffsets", "min_box_dim", fallback=50)

# # ---------------------------------------------------------------------------
# # Default Retail Layout Offsets
# # ---------------------------------------------------------------------------
# DEFAULT_RETAIL_OFFSETS = {
#     "CORNER_OFFSET_X": _cfg.get_int(
#         "DefaultRetailMode", "layout_corner_offset_x", fallback=11
#     ),
#     "CORNER_OFFSET_Y": _cfg.get_int(
#         "DefaultRetailMode", "layout_corner_offset_y", fallback=10
#     ),
#     "PADDING_INTERSECT_X": _cfg.get_int(
#         "DefaultRetailMode", "layout_padding_intersect_x", fallback=-10
#     ),
#     "PADDING_ICON_Y": _cfg.get_int(
#         "DefaultRetailMode", "layout_padding_icon_y", fallback=17
#     ),
# }

# # ---------------------------------------------------------------------------
# # Default Echoes Layout Offsets
# # ---------------------------------------------------------------------------
# DEFAULT_ECHOES_OFFSETS = {
#     "body_left_margin": _cfg.get_int(
#         "DefaultRetailOffsets", "body_left_margin", fallback=11
#     ),
#     "body_top_margin": _cfg.get_int(
#         "DefaultRetailOffsets", "body_top_margin", fallback=10
#     ),
#     "body_right_padding": _cfg.get_int(
#         "DefaultRetailOffsets", "body_right_padding", fallback=0
#     ),
#     "body_bottom_padding": _cfg.get_int(
#         "DefaultRetailOffsets", "body_bottom_padding", fallback=0
#     ),
# }

# # ---------------------------------------------------------------------------
# # Retail Mode Paths
# # ---------------------------------------------------------------------------
# SCRIPT_LOG = _cfg.get_str(
#     "DefaultRetailMode",
#     "plugin_script_log_path",
#     fallback="",
# )

# # ---------------------------------------------------------------------------
# # Device (lazy via ConfigManager property)
# # ---------------------------------------------------------------------------
# DEVICE = _cfg.device

# # ---------------------------------------------------------------------------
# # Audio Settings
# # ---------------------------------------------------------------------------
# SAMPLE_RATE = _cfg.get_int("TTSSettings", "sample_rate", fallback=24000)
# DEFAULT_VOLUME = _cfg.get_float("TTSSettings", "default_volume", fallback=0.4)
# LUX_VOLUME = _cfg.get_float("TTSSettings", "lux_volume", fallback=0.5)  # Renamed to omnivoice_volume

# # ---------------------------------------------------------------------------
# # TTS Settings
# # ---------------------------------------------------------------------------
# TTS_SPEED = _cfg.get_float("TTSSettings", "tts_speed", fallback=1.1)
# TTS_WAVE_STEPS = _cfg.get_int("TTSSettings", "tts_wave_steps", fallback=16)

# # ---------------------------------------------------------------------------
# # OCR Settings
# # ---------------------------------------------------------------------------
# TESSERACT_CMD = _cfg.tesseract_cmd

# # ---------------------------------------------------------------------------
# # Logging
# # ---------------------------------------------------------------------------
# LOG_LEVEL = _cfg.get_str("LogSettings", "log_level", fallback="INFO")

# # ---------------------------------------------------------------------------
# # Features
# # ---------------------------------------------------------------------------
# ENABLE_WIKI = _cfg.get_bool("WikiSettings", "enable_wiki", fallback=False)

# # ---------------------------------------------------------------------------
# # Quest Window Detection
# # ---------------------------------------------------------------------------
# QUEST_WINDOW_MODE = _cfg.get_str("TTSSettings", "quest_window_mode", fallback="auto")
# QUEST_WINDOW_BOX = [
#     _cfg.get_int("TTSSettings", "quest_window_box_x", fallback=555),
#     _cfg.get_int("TTSSettings", "quest_window_box_y", fallback=380),
#     _cfg.get_int("TTSSettings", "quest_window_width", fallback=425),
#     _cfg.get_int("TTSSettings", "quest_window_height", fallback=539),
# ]

# # ---------------------------------------------------------------------------
# # Trigger Settings
# # ---------------------------------------------------------------------------
# QUEST_TRIGGER_MODE = _cfg.get_str(
#     "TTSSettings", "quest_trigger_mode", fallback="manual"
# )
# QUEST_TRIGGER_KEY = _cfg.get_str(
#     "TTSSettings", "quest_trigger_key", fallback="middle_mouse"
# )

# # ---------------------------------------------------------------------------
# # NPC Name Max Age
# # ---------------------------------------------------------------------------
# NPC_NAME_MAX_AGE = _cfg.get_int("TTSSettings", "npc_name_max_age", fallback=60)
