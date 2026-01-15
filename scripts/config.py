"""
Configuration management for Whisper Tray.
Handles loading, saving, and default values for user settings.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    "model_size": "small",
    "language": "en",
    "hotkey": "ctrl+alt+space",
    "input_device": None,  # None = system default
    "send_enter": True,
    "keep_clipboard": False,
    "use_typing": False,
    "trailing_space": True,
    "show_status_window": False,
    "device": "cpu",
    "compute_type": "int8",
    "samplerate": 16000,
    "beam_size": 1,
    "pre_type_delay": 0.2,
    "type_delay": 0.0,
    "first_run_complete": False,
    "model_download_path": None,  # None = default HuggingFace cache
    "downloaded_models": [],  # List of model sizes that have been downloaded
    # New settings
    "save_transcription_log": True,  # Save all transcriptions to log files
    "auto_copy_to_clipboard": True,  # Always copy transcription to clipboard
    "show_toast_notifications": True,  # Show Windows toast notifications
    "show_transcription_window": False,  # Show real-time transcription window
    "history_length": 20,  # Number of transcriptions to keep in history
    "transcription_window_always_on_top": True,  # Keep transcription window on top
}

# Model descriptions for UI
MODEL_INFO = {
    "tiny": {
        "size": "~75 MB",
        "speed": "Fastest",
        "accuracy": "Basic",
        "recommended": False,
        "description": "Fastest transcription, basic accuracy. Good for quick notes.",
    },
    "base": {
        "size": "~145 MB",
        "speed": "Fast",
        "accuracy": "Good",
        "recommended": False,
        "description": "Fast with good accuracy. Suitable for clear speech.",
    },
    "small": {
        "size": "~465 MB",
        "speed": "Balanced",
        "accuracy": "Good",
        "recommended": True,
        "description": "Best balance of speed and accuracy. Recommended for most users.",
    },
    "medium": {
        "size": "~1.5 GB",
        "speed": "Slower",
        "accuracy": "Better",
        "recommended": False,
        "description": "Higher accuracy but slower. Good for complex vocabulary.",
    },
    "large-v2": {
        "size": "~3.0 GB",
        "speed": "Slow",
        "accuracy": "Excellent",
        "recommended": False,
        "description": "High accuracy. Requires more memory and time.",
    },
    "large-v3": {
        "size": "~3.0 GB",
        "speed": "Slow",
        "accuracy": "Best",
        "recommended": False,
        "description": "Latest and most accurate model. Best for critical transcriptions.",
    },
    "turbo": {
        "size": "~1.6 GB",
        "speed": "Fast",
        "accuracy": "Excellent",
        "recommended": False,
        "description": "Optimized large-v3. 8x faster with near-best accuracy. Great choice!",
    },
}

# Supported languages
LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}


def get_app_root() -> Path:
    """Get the application root directory.

    Returns the parent directory of the scripts folder where this config.py file lives.
    """
    return Path(__file__).parent.parent


def is_portable_mode() -> bool:
    """Check if the application is running in portable mode.

    Portable mode is detected in these cases:
    1. A 'config/' folder exists next to the EXE (self-installing wizard creates this)
    2. A 'portable.txt' marker file exists in app root (legacy method)

    Returns:
        True if running in portable mode, False otherwise
    """
    import sys
    app_root = get_app_root()

    # Method 1: Check for config folder next to EXE (new self-installing method)
    # When running as frozen exe, check exe's parent directory
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "config").exists():
            return True

    # Method 2: Check for config folder in app root
    if (app_root / "config").exists():
        return True

    # Method 3: Legacy - check for portable.txt marker
    portable_marker = app_root / "portable.txt"
    return portable_marker.exists()


def get_config_dir() -> Path:
    """Get the configuration directory path.

    In portable mode: <exe_folder>/config/ (or <app_root>/config/)
    In standard mode on Windows: %APPDATA%\\WhisperTray
    In standard mode on Linux/Mac: ~/.config/whisper-tray (fallback)
    """
    import sys

    if is_portable_mode():
        # When running as frozen exe, config is next to the exe
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            config_dir = exe_dir / "config"
            if config_dir.exists():
                return config_dir
        # Fallback to app_root/config (development or legacy)
        return get_app_root() / "config"

    if os.name == "nt":  # Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "WhisperTray"
    # Fallback for non-Windows or if APPDATA not set
    return Path.home() / ".config" / "whisper-tray"


def get_config_path() -> Path:
    """Get the full path to the config file."""
    return get_config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from file, returning defaults for missing keys.

    Returns:
        Dictionary with all config values (defaults merged with saved values)
    """
    config = DEFAULT_CONFIG.copy()
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            # Merge saved values over defaults
            for key, value in saved_config.items():
                if key in config:
                    config[key] = value
        except (json.JSONDecodeError, IOError) as e:
            # If config is corrupted, use defaults
            print(f"Warning: Could not load config: {e}")

    return config


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file.

    Args:
        config: Dictionary of configuration values

    Returns:
        True if save succeeded, False otherwise
    """
    config_path = get_config_path()

    try:
        # Create directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving config: {e}")
        return False


def get_default_config() -> Dict[str, Any]:
    """Get a fresh copy of default configuration."""
    return DEFAULT_CONFIG.copy()


def merge_config_with_args(config: Dict[str, Any], args) -> Dict[str, Any]:
    """Merge config file values with command-line arguments.

    CLI arguments take precedence over config file values.
    Only non-None CLI values override config.

    Args:
        config: Configuration dictionary from file
        args: argparse.Namespace from command line

    Returns:
        Merged configuration dictionary
    """
    merged = config.copy()

    # Map CLI arg names to config keys (handle naming differences)
    arg_to_config = {
        "model_size": "model_size",
        "language": "language",
        "hotkey": "hotkey",
        "input_device": "input_device",
        "send_enter": "send_enter",
        "keep_clipboard": "keep_clipboard",
        "use_typing": "use_typing",
        "no_trailing_space": "trailing_space",  # Inverted
        "show_status_window": "show_status_window",
        "device": "device",
        "compute_type": "compute_type",
        "samplerate": "samplerate",
        "beam_size": "beam_size",
        "pre_type_delay": "pre_type_delay",
        "type_delay": "type_delay",
    }

    for arg_name, config_key in arg_to_config.items():
        if hasattr(args, arg_name):
            arg_value = getattr(args, arg_name)
            # Special handling for inverted flags
            if arg_name == "no_trailing_space":
                # CLI: --no-trailing-space sets no_trailing_space=True
                # Config: trailing_space=True means add space
                if arg_value:  # If --no-trailing-space was passed
                    merged[config_key] = False
            elif arg_value is not None:
                # For boolean flags that are action="store_true",
                # they default to False when not provided
                # We only override if explicitly set via CLI
                merged[config_key] = arg_value

    return merged


def is_first_run() -> bool:
    """Check if this is the first time running the app."""
    config = load_config()
    return not config.get("first_run_complete", False)


def mark_first_run_complete() -> None:
    """Mark that the first-run wizard has been completed."""
    config = load_config()
    config["first_run_complete"] = True
    save_config(config)


def get_default_model_path() -> Path:
    """Get the default model cache path.

    In portable mode: <exe_folder>/models/ (or <app_root>/models/)
    In standard mode: HuggingFace default cache location
    """
    import sys

    if is_portable_mode():
        # When running as frozen exe, models are next to the exe
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            models_dir = exe_dir / "models"
            return models_dir
        # Fallback to app_root/models (development or legacy)
        return get_app_root() / "models"

    if os.name == "nt":  # Windows
        # HuggingFace default on Windows
        cache_home = os.environ.get("HF_HOME")
        if cache_home:
            return Path(cache_home)
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "huggingface" / "hub"
        return Path.home() / ".cache" / "huggingface" / "hub"
    # Linux/Mac
    return Path.home() / ".cache" / "huggingface" / "hub"


def get_model_download_path() -> Optional[Path]:
    """Get the configured model download path, or None for default."""
    config = load_config()
    custom_path = config.get("model_download_path")
    if custom_path:
        return Path(custom_path)
    return None


def set_model_download_path(path: Optional[str]) -> None:
    """Set a custom model download path."""
    config = load_config()
    config["model_download_path"] = path
    save_config(config)


def get_downloaded_models() -> list:
    """Get list of models that have been downloaded."""
    config = load_config()
    return config.get("downloaded_models", [])


def mark_model_downloaded(model_size: str) -> None:
    """Mark a model as downloaded."""
    config = load_config()
    downloaded = config.get("downloaded_models", [])
    if model_size not in downloaded:
        downloaded.append(model_size)
        config["downloaded_models"] = downloaded
        save_config(config)


def get_transcription_log_dir() -> Path:
    """Get the transcription log directory path."""
    return get_config_dir() / "transcriptions"


def get_transcription_log_path() -> Path:
    """Get today's transcription log file path.

    Creates directory structure: transcriptions/YYYY/MM/YYYY-MM-DD.txt
    """
    from datetime import datetime
    now = datetime.now()

    log_dir = get_transcription_log_dir()
    year_dir = log_dir / str(now.year)
    month_dir = year_dir / f"{now.month:02d}"

    # Create directories if needed
    month_dir.mkdir(parents=True, exist_ok=True)

    # Daily log file
    filename = f"{now.strftime('%Y-%m-%d')}.txt"
    return month_dir / filename


def save_transcription_to_log(text: str) -> bool:
    """Save a transcription to the daily log file.

    Args:
        text: The transcription text to save

    Returns:
        True if saved successfully, False otherwise
    """
    from datetime import datetime

    try:
        log_path = get_transcription_log_path()
        timestamp = datetime.now().strftime("%H:%M:%S")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text.strip()}\n")

        return True
    except Exception as e:
        print(f"Error saving transcription log: {e}")
        return False


def get_transcriptions_for_date(date_str: str) -> list:
    """Get all transcriptions for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of (timestamp, text) tuples
    """
    from datetime import datetime

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        log_dir = get_transcription_log_dir()
        log_path = log_dir / str(date.year) / f"{date.month:02d}" / f"{date_str}.txt"

        if not log_path.exists():
            return []

        transcriptions = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and line.startswith("["):
                    # Parse [HH:MM:SS] text format
                    try:
                        timestamp = line[1:9]
                        text = line[11:]  # Skip "] "
                        transcriptions.append((timestamp, text))
                    except (IndexError, ValueError):
                        continue

        return transcriptions
    except Exception:
        return []


def get_todays_transcriptions() -> list:
    """Get all transcriptions from today."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    return get_transcriptions_for_date(today)
