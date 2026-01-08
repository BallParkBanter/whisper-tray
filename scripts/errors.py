"""
User-friendly error message handling for Whisper Tray.
Maps technical errors to helpful, actionable messages.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger("whisper_tray")


# Error type to user-friendly message mapping
ERROR_MESSAGES = {
    # Microphone errors
    "mic_not_found": (
        "Microphone not found",
        "Please check that your microphone is connected and try again.\n"
        "You can select a different microphone in Settings.",
    ),
    "mic_unavailable": (
        "Microphone unavailable",
        "Your selected microphone is not available.\n"
        "Please check Settings to select a different microphone.",
    ),
    "mic_permission": (
        "Microphone access denied",
        "Please grant microphone permission:\n"
        "Windows Settings > Privacy & Security > Microphone",
    ),
    "mic_in_use": (
        "Microphone in use",
        "Your microphone may be in use by another application.\n"
        "Try closing other apps that use the microphone.",
    ),
    # Audio errors
    "audio_silent": (
        "No audio detected",
        "The recording appears to be silent.\n"
        "Please check your microphone volume and try again.",
    ),
    "audio_too_quiet": (
        "Audio too quiet",
        "The recording was very quiet.\n"
        "Please speak louder or move closer to the microphone.",
    ),
    "audio_error": (
        "Audio recording error",
        "There was a problem recording audio.\n"
        "Please try again or check your audio settings.",
    ),
    # Model errors
    "model_download_failed": (
        "Model download failed",
        "Could not download the transcription model.\n"
        "Please check your internet connection and try again.",
    ),
    "model_load_failed": (
        "Model failed to load",
        "Could not load the transcription model.\n"
        "Try restarting the application or selecting a smaller model in Settings.",
    ),
    "model_not_found": (
        "Model not found",
        "The transcription model was not found.\n"
        "It will be downloaded automatically on first use.",
    ),
    # Transcription errors
    "transcription_failed": (
        "Transcription failed",
        "Could not transcribe the audio.\n"
        "Please try speaking more clearly or try again.",
    ),
    "transcription_empty": (
        "No speech detected",
        "Could not understand the audio.\n"
        "Please speak clearly and try again.",
    ),
    # Hotkey errors
    "hotkey_failed": (
        "Hotkey registration failed",
        "Could not register the hotkey.\n"
        "The hotkey may be in use by another application.\n"
        "Try changing the hotkey in Settings.",
    ),
    "hotkey_blocked": (
        "Hotkey not working",
        "The hotkey may not work in some applications.\n"
        "Try using the tray icon menu instead.",
    ),
    # System errors
    "gpu_unavailable": (
        "GPU not available",
        "GPU acceleration is not available.\n"
        "Using CPU instead (this is normal for most computers).",
    ),
    "out_of_memory": (
        "Out of memory",
        "Not enough memory to run the transcription model.\n"
        "Try selecting a smaller model in Settings.",
    ),
    "config_error": (
        "Settings error",
        "There was a problem with your settings.\n"
        "Default settings will be used.",
    ),
    # Clipboard errors
    "clipboard_error": (
        "Clipboard error",
        "Could not paste the transcription.\n"
        "Try enabling 'Use typing mode' in Settings.",
    ),
    # Generic errors
    "unknown": (
        "Something went wrong",
        "An unexpected error occurred.\n"
        "Please try again or restart the application.",
    ),
}


def get_friendly_error(error_type: str) -> Tuple[str, str]:
    """Get user-friendly error message.

    Args:
        error_type: The error type key (e.g., 'mic_not_found')

    Returns:
        Tuple of (short_message, detailed_message)
    """
    return ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown"])


def classify_error(exception: Exception) -> str:
    """Classify an exception into an error type.

    Args:
        exception: The exception to classify

    Returns:
        Error type string for use with get_friendly_error()
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()

    # PortAudio / sounddevice errors
    if "portaudio" in error_str or "portaudio" in error_type:
        if "device" in error_str and ("unavailable" in error_str or "not found" in error_str):
            return "mic_unavailable"
        if "no default" in error_str:
            return "mic_not_found"
        return "audio_error"

    # Permission errors
    if "permission" in error_str or "access denied" in error_str:
        if "microphone" in error_str or "audio" in error_str:
            return "mic_permission"
        return "unknown"

    # Memory errors
    if "memory" in error_str or isinstance(exception, MemoryError):
        return "out_of_memory"

    # CUDA / GPU errors
    if "cuda" in error_str or "gpu" in error_str:
        return "gpu_unavailable"

    # Network / download errors
    if any(word in error_str for word in ["download", "network", "connection", "timeout", "http"]):
        return "model_download_failed"

    # Model errors
    if "model" in error_str:
        if "not found" in error_str or "missing" in error_str:
            return "model_not_found"
        return "model_load_failed"

    # Hotkey errors
    if "hotkey" in error_str or "keyboard" in error_str:
        return "hotkey_failed"

    # Clipboard errors
    if "clipboard" in error_str or "paste" in error_str:
        return "clipboard_error"

    # Transcription errors
    if "transcri" in error_str or "whisper" in error_str:
        return "transcription_failed"

    return "unknown"


def handle_error(
    exception: Exception,
    context: str = "",
    notify_func=None,
) -> Tuple[str, str]:
    """Handle an error with logging and optional notification.

    Args:
        exception: The exception that occurred
        context: Additional context about where the error occurred
        notify_func: Optional function to call with error message

    Returns:
        Tuple of (short_message, detailed_message)
    """
    # Classify the error
    error_type = classify_error(exception)

    # Get friendly message
    short_msg, detailed_msg = get_friendly_error(error_type)

    # Log the error with technical details
    logger.error(
        f"Error ({error_type}): {short_msg} | Context: {context} | "
        f"Technical: {type(exception).__name__}: {exception}"
    )

    # Notify user if function provided
    if notify_func:
        notify_func(short_msg)

    return short_msg, detailed_msg


def is_silent_audio(audio_max: float, audio_mean: float) -> bool:
    """Check if audio appears to be silent.

    Args:
        audio_max: Maximum absolute value in audio
        audio_mean: Mean absolute value in audio

    Returns:
        True if audio appears silent
    """
    return audio_max < 0.01


def is_quiet_audio(audio_max: float, audio_mean: float) -> bool:
    """Check if audio appears too quiet.

    Args:
        audio_max: Maximum absolute value in audio
        audio_mean: Mean absolute value in audio

    Returns:
        True if audio is quiet but not silent
    """
    return 0.01 <= audio_max < 0.05


def get_audio_quality_message(audio_max: float, audio_mean: float) -> Optional[str]:
    """Get a message about audio quality issues.

    Args:
        audio_max: Maximum absolute value in audio
        audio_mean: Mean absolute value in audio

    Returns:
        Warning message if there's an issue, None otherwise
    """
    if is_silent_audio(audio_max, audio_mean):
        return "Recording appears silent. Check your microphone."
    if is_quiet_audio(audio_max, audio_mean):
        return "Recording is quiet. Consider speaking louder."
    return None
