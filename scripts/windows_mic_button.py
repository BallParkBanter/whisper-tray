#!/usr/bin/env python3
"""
Windows tray app that records speech, transcribes it with Whisper, and types the
result into the active window (e.g. a Codex terminal).
"""
import argparse
import contextlib
import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Optional

import logging
import numpy as np
# pyautogui imported lazily in WhisperTray.__init__ to avoid DPI issues during wizard
import pyperclip
import sounddevice as sd
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont
import pystray
import keyboard
try:
    from winotify import Notification as WinNotification
except Exception:  # pragma: no cover
    WinNotification = None

# Import our modules
from config import (
    load_config,
    save_config,
    is_first_run,
    merge_config_with_args,
    get_model_download_path,
    save_transcription_to_log,
    get_transcription_log_dir,
    get_todays_transcriptions,
    get_downloaded_models,
)
from errors import handle_error, get_audio_quality_message, classify_error, get_friendly_error
from transcription_window import get_transcription_window_manager


APP_ID = "WhisperDictation"
ICON_FILE = Path(__file__).with_name("whisper_icon.png")
logger = logging.getLogger("whisper_tray")


def set_app_id(app_id: str = APP_ID):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.info("Set AppUserModelID to %s", app_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("Unable to set AppUserModelID: %s", exc)


def configure_logging():
    log_path = Path(__file__).with_suffix(".log")
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.info("Logging initialized at %s", log_path)


def create_icon(color: str, radius: int = 12, label: str = "W", shape: str = "circle") -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if shape == "square":
        # FILLED red square for recording - VERY bold for tiny tray icon
        margin = 4
        draw.rectangle(
            (margin, margin, size - margin, size - margin),
            fill=color,
        )
    elif shape == "triangle":
        # FILLED amber triangle for transcribing - points right, very bold
        margin = 4
        draw.polygon(
            [(margin, margin), (size - margin, size // 2), (margin, size - margin)],
            fill=color,
        )
    else:
        # FILLED green circle for idle - solid, not outline
        margin = 4
        draw.ellipse(
            (margin, margin, size - margin, size - margin),
            fill=color,
        )

    return image


def ensure_icon_file() -> Optional[Path]:
    try:
        if ICON_FILE.exists():
            return ICON_FILE
        image = create_icon("#388e3c")
        ICON_FILE.parent.mkdir(parents=True, exist_ok=True)
        image.save(ICON_FILE, format="PNG")
        return ICON_FILE
    except Exception as exc:  # pragma: no cover
        logger.warning("Unable to create icon file: %s", exc)
        return None


class Recorder:
    def __init__(self, samplerate: int, device: Optional[int]):
        self.samplerate = samplerate
        self.device = device
        self._stream = None
        self._frames = []
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio callback warning: {status}", file=sys.stderr)
        with self._lock:
            self._frames.append(indata.copy())

    def start(self):
        if self._stream is not None:
            return
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            device=self.device,
        )
        self._stream.start()

    def stop(self):
        if self._stream is None:
            return None
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            if not self._frames:
                return None
            audio = np.concatenate(self._frames, axis=0).flatten()
        return audio


class TrayApp:
    def __init__(self, args, config=None):
        self.args = args
        self.config = config or {}

        # Set custom model path if configured
        custom_model_path = get_model_download_path()
        if custom_model_path:
            os.environ["HF_HOME"] = str(custom_model_path)

        self.model = WhisperModel(args.model_size, device=args.device, compute_type=args.compute_type)
        self.recorder = Recorder(args.samplerate, args.input_device)
        self.recording = False
        self.processing = False
        self.send_enter = args.send_enter
        self.trailing_space = not args.no_trailing_space
        self.keep_clipboard = args.keep_clipboard
        self.use_typing = args.use_typing
        self.start_popup = not args.no_start_popup
        self.show_status_window = args.show_status_window
        # Use mic_icon.png for toast notifications
        if getattr(sys, 'frozen', False):
            self.icon_path = Path(sys._MEIPASS) / "icons" / "mic_icon.png"
        else:
            self.icon_path = Path(__file__).parent.parent / "icons" / "mic_icon.png"
        if not self.icon_path.exists():
            self.icon_path = args.icon_path or ensure_icon_file()

        # New settings
        self.save_transcription_log = self.config.get("save_transcription_log", True)
        self.auto_copy_to_clipboard = self.config.get("auto_copy_to_clipboard", True)
        self.show_toast_notifications = self.config.get("show_toast_notifications", True)
        # Transcription window disabled - future release
        self.show_transcription_window = False  # self.config.get("show_transcription_window", False)
        self.history_length = self.config.get("history_length", 20)

        # Initialize transcription window manager (disabled for now)
        self.transcription_manager = get_transcription_window_manager()
        self.transcription_manager.set_enabled(False)  # Disabled - future release
        # self.transcription_manager.set_always_on_top(
        #     self.config.get("transcription_window_always_on_top", True)
        # )

        self.history = []  # Store transcriptions (up to history_length)

        # Status window for always-visible notifications
        self.status_window = None
        self.status_label = None
        if self.show_status_window:
            self._create_status_window()

        # Import pyautogui here (lazy load) to avoid DPI issues during first-run wizard
        import pyautogui
        pyautogui.PAUSE = self.args.type_delay
        pyautogui.FAILSAFE = False
        # Warm-up pyautogui to initialize Windows keyboard/mouse interface
        # Fixes bug where first transcription doesn't auto-paste
        try:
            pyautogui.position()  # Forces initialization of pyautogui internals
        except Exception:
            pass

        # Load idle icon from file, fallback to generated if not found
        # For PyInstaller bundled app, use sys._MEIPASS; otherwise use relative path
        if getattr(sys, 'frozen', False):
            # Running as bundled EXE
            icons_dir = Path(sys._MEIPASS) / "icons"
        else:
            # Running as script
            icons_dir = Path(__file__).parent.parent / "icons"
        idle_icon_path = icons_dir / "idle_icon.webp"
        if idle_icon_path.exists():
            try:
                self.icon_idle = Image.open(idle_icon_path).convert("RGBA")
                # Resize to appropriate icon size if needed
                if self.icon_idle.size != (64, 64):
                    self.icon_idle = self.icon_idle.resize((64, 64), Image.Resampling.LANCZOS)
            except:
                self.icon_idle = create_icon("#00ff00", shape="circle")
        else:
            self.icon_idle = create_icon("#00ff00", shape="circle")

        # Load recording icon from file, fallback to generated if not found
        recording_icon_path = icons_dir / "recording_icon.png"
        if recording_icon_path.exists():
            try:
                self.icon_recording = Image.open(recording_icon_path).convert("RGBA")
                # Resize to appropriate icon size if needed
                if self.icon_recording.size != (64, 64):
                    self.icon_recording = self.icon_recording.resize((64, 64), Image.Resampling.LANCZOS)
            except:
                self.icon_recording = create_icon("#ff0000", shape="square")
        else:
            self.icon_recording = create_icon("#ff0000", shape="square")

        # Load processing icon from file, fallback to generated if not found
        processing_icon_path = icons_dir / "processing_icon.webp"
        if processing_icon_path.exists():
            try:
                self.icon_processing = Image.open(processing_icon_path).convert("RGBA")
                # Resize to appropriate icon size if needed
                if self.icon_processing.size != (64, 64):
                    self.icon_processing = self.icon_processing.resize((64, 64), Image.Resampling.LANCZOS)
            except:
                self.icon_processing = create_icon("#ffff00", shape="triangle")
        else:
            self.icon_processing = create_icon("#ffff00", shape="triangle")

        self.icon = pystray.Icon(
            "Whisper Dictation",
            icon=self.icon_idle,
            title="Whisper Dictation",
            menu=self._build_menu(),
        )

        keyboard.add_hotkey(self.args.hotkey, self.toggle_recording)
        keyboard.add_hotkey('esc', self.cancel_recording)
        self.icon.visible = False

    def _create_status_window(self):
        """Create a small always-on-top status window."""
        self.status_window = tk.Tk()
        self.status_window.title("Whisper Status")
        self.status_window.attributes('-topmost', True)
        self.status_window.attributes('-alpha', 0.9)
        self.status_window.geometry("200x60+10+10")  # Top-left corner
        self.status_window.resizable(False, False)

        self.status_label = tk.Label(
            self.status_window,
            text="IDLE",
            font=("Arial", 16, "bold"),
            bg="#388e3c",
            fg="white",
            padx=10,
            pady=10
        )
        self.status_label.pack(fill=tk.BOTH, expand=True)

        # Don't let it take focus
        self.status_window.attributes('-toolwindow', True)

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._menu_label, self._menu_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._open_settings),
            pystray.MenuItem("History", pystray.Menu(self._build_history_menu)),
            pystray.MenuItem("Open Log Folder...", self._open_log_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Send Enter",
                self._toggle_send_enter,
                checked=lambda item: self.send_enter,
            ),
            pystray.MenuItem(
                "Keep clipboard contents",
                self._toggle_keep_clipboard,
                checked=lambda item: self.keep_clipboard,
            ),
            # Transcription Window disabled - future release
            # pystray.MenuItem(
            #     "Show Transcription Window",
            #     self._toggle_transcription_window,
            #     checked=lambda item: self.show_transcription_window,
            # ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.stop),
        )

    def _build_history_menu(self):
        """Build the history submenu dynamically."""
        logger.debug(f"Building history menu, {len(self.history)} items in history")
        if not self.history:
            return (pystray.MenuItem("(empty)", None, enabled=False),)

        items = []
        for i, text in enumerate(self.history[:self.history_length]):
            display = f"{text[:50]}..." if len(text) > 50 else text
            logger.debug(f"  History item {i}: {display}")
            # Use default=True for first item so it's highlighted
            items.append(pystray.MenuItem(
                display,
                lambda _, t=text: self._copy_to_clipboard(t)
            ))
        return tuple(items)

    def _open_log_folder(self, icon=None, item=None):
        """Open the transcription log folder in Windows Explorer."""
        import subprocess
        log_dir = get_transcription_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Windows explorer
            subprocess.run(["explorer", str(log_dir)], check=False)
        except Exception as e:
            logger.error(f"Failed to open log folder: {e}")
            self.notify("Could not open log folder")

    def _toggle_transcription_window(self, icon=None, item=None):
        """Toggle the transcription window feature."""
        self.show_transcription_window = not self.show_transcription_window
        self.transcription_manager.set_enabled(self.show_transcription_window)
        # Save to config
        self.config["show_transcription_window"] = self.show_transcription_window
        save_config(self.config)

    def _menu_label(self, _=None):
        if self.recording:
            return "Stop recording"
        return "Start recording"

    def _menu_toggle(self, icon, item):
        self.toggle_recording()

    def _toggle_send_enter(self, icon, item):
        self.send_enter = not self.send_enter

    def _toggle_keep_clipboard(self, icon, item):
        self.keep_clipboard = not self.keep_clipboard

    def _open_settings(self, icon=None, item=None):
        """Open the settings window."""
        def run_settings():
            from settings_gui import show_settings

            def on_save(new_config):
                # Update runtime settings
                self.send_enter = new_config.get("send_enter", self.send_enter)
                self.keep_clipboard = new_config.get("keep_clipboard", self.keep_clipboard)
                self.use_typing = new_config.get("use_typing", self.use_typing)
                self.trailing_space = new_config.get("trailing_space", self.trailing_space)

                # Check if hotkey changed
                new_hotkey = new_config.get("hotkey", self.args.hotkey)
                if new_hotkey != self.args.hotkey:
                    try:
                        keyboard.remove_hotkey(self.args.hotkey)
                        keyboard.add_hotkey(new_hotkey, self.toggle_recording)
                        self.args.hotkey = new_hotkey
                        self.notify(f"Hotkey changed to {new_hotkey}")
                    except Exception as e:
                        logger.error(f"Failed to update hotkey: {e}")
                        self.notify("Failed to change hotkey")

                # Check if model changed (requires restart)
                if new_config.get("model_size") != self.args.model_size:
                    from tkinter import messagebox
                    import subprocess
                    import time

                    # Force config save again to ensure it's on disk
                    from config import save_config, load_config
                    current = load_config()
                    current["model_size"] = new_config.get("model_size")
                    save_config(current)

                    restart = messagebox.askyesno(
                        "Restart Required",
                        f"Model changed to '{new_config.get('model_size')}'.\n\n"
                        "WhisperTray needs to restart for this change to take effect.\n\n"
                        "Restart now?"
                    )
                    if restart:
                        # Restart the application
                        import sys
                        import os

                        # Small delay to ensure config is flushed to disk
                        time.sleep(0.5)

                        if getattr(sys, 'frozen', False):
                            # Running as EXE - launch self and exit
                            subprocess.Popen([sys.executable])
                        else:
                            # Running as script
                            subprocess.Popen([sys.executable] + sys.argv)
                        os._exit(0)  # Exit immediately

                # Update config object
                self.config.update(new_config)

            show_settings(None, self.config, on_save)

        # Run in separate thread to not block tray
        threading.Thread(target=run_settings, daemon=True).start()

    def _copy_to_clipboard(self, text: str):
        """Copy text from history to clipboard."""
        pyperclip.copy(text)
        self.notify(f"Copied: {text[:30]}...")

    def cancel_recording(self):
        """Cancel recording without transcribing (Esc key)."""
        if not self.recording or self.processing:
            return
        self.recorder.stop()
        self.recording = False
        self.icon.icon = self.icon_idle
        self.icon.title = "Idle"
        self.notify("Recording cancelled")
        self.transcription_manager.on_recording_cancelled()

    def notify(self, message: str):
        logger.info(f"Notification: {message}")

        # Update tray icon tooltip with the message
        self.icon.title = f"Whisper: {message}"

        # Update status window if enabled
        if self.status_window and self.status_label:
            if "ready" in message.lower():
                bg_color = "#388e3c"
                text = "READY"
            elif "started" in message.lower():
                bg_color = "#d32f2f"
                text = "RECORDING"
            elif "transcrib" in message.lower():
                bg_color = "#f9a825"
                text = "TRANSCRIBING"
            elif "sent" in message.lower():
                bg_color = "#00ff00"
                text = "✓ READY TO PASTE"
            elif "cancelled" in message.lower():
                bg_color = "#666666"
                text = "CANCELLED"
            elif "error" in message.lower():
                bg_color = "#ff0000"
                text = "ERROR"
            else:
                bg_color = "#388e3c"
                text = "IDLE"

            self.status_label.config(text=text, bg=bg_color)
            self.status_window.update()

        # Only show toast notifications if enabled
        if not self.show_toast_notifications:
            return

        # Try winotify (Windows 10/11 toast notifications)
        if WinNotification:
            try:
                toast = WinNotification(
                    app_id="WhisperDictation",
                    title="Whisper Dictation",
                    msg=message,
                    icon=str(Path(self.icon_path).resolve()) if self.icon_path else None,
                    duration="short",
                )
                toast.show()
                logger.info("Toast notification sent via winotify")
            except Exception as exc:
                logger.error(f"winotify toast failed: {exc}", exc_info=True)

        # Fallback to pystray notification
        try:
            self.icon.notify(message, "Whisper Dictation")
            logger.info("Notification sent via pystray")
        except Exception as exc:
            logger.error(f"pystray notification failed: {exc}", exc_info=True)

    def toggle_recording(self):
        if self.processing:
            return
        if not self.recording:
            try:
                self.recorder.start()
            except Exception as exc:
                self.notify(f"Audio error: {exc}")
                self.transcription_manager.on_error(str(exc))
                return
            self.recording = True
            self.icon.icon = self.icon_recording
            self.icon.title = "Recording…"
            self.notify("Recording started")
            # Show transcription window with recording indicator
            self.transcription_manager.on_recording_start()
        else:
            audio = self.recorder.stop()
            self.recording = False
            self.icon.icon = self.icon_processing
            self.icon.title = "Transcribing…"
            # Update transcription window
            self.transcription_manager.on_transcribing()
            if audio is None:
                self.icon.icon = self.icon_idle
                self.icon.title = "Idle"
                self.notify("No audio captured")
                self.transcription_manager.on_error("No audio captured")
                return
            self.processing = True
            thread = threading.Thread(target=self._transcribe_async, args=(audio,), daemon=True)
            thread.start()

    def _transcribe_async(self, audio: np.ndarray):
        try:
            # Log audio stats for debugging
            audio_max = np.max(np.abs(audio))
            audio_mean = np.mean(np.abs(audio))
            logger.info(f"Audio stats: max={audio_max:.6f}, mean={audio_mean:.6f}, samples={len(audio)}")

            # Check audio quality and warn user
            quality_msg = get_audio_quality_message(audio_max, audio_mean)
            if quality_msg:
                logger.warning(quality_msg)
                self.notify(quality_msg)
                # Continue anyway - might still get some transcription

            segments, _ = self.model.transcribe(
                audio,
                language=self.args.language,
                beam_size=self.args.beam_size,
            )
            text = "".join(segment.text for segment in segments).strip()
            if self.trailing_space and text and not text.endswith(" "):
                text += " "
            if text:
                # Add to history (keep up to history_length)
                self.history.insert(0, text.strip())
                if len(self.history) > self.history_length:
                    self.history.pop()

                # Save to transcription log file
                if self.save_transcription_log:
                    save_transcription_to_log(text.strip())

                # Auto-copy to clipboard (always, as backup)
                if self.auto_copy_to_clipboard:
                    pyperclip.copy(text)

                # Update transcription window
                self.transcription_manager.on_transcription_complete(text.strip())

                # Force menu rebuild to update history
                self.icon.menu = self._build_menu()

                # Send text to active window
                self._send_text(text)
                self.notify("Transcription sent")
            else:
                short_msg, _ = get_friendly_error("transcription_empty")
                self.notify(short_msg)
                self.transcription_manager.on_error("No speech detected")
        except Exception as exc:
            short_msg, _ = handle_error(exc, "transcription", self.notify)
            self.transcription_manager.on_error(short_msg)
        finally:
            self.processing = False
            self.icon.icon = self.icon_idle
            self.icon.title = "Idle"

    def _send_text(self, text: str):
        import pyautogui  # Lazy import to avoid DPI issues during wizard
        time.sleep(self.args.pre_type_delay)

        if self.use_typing:
            # Type character-by-character using keyboard library (better terminal support)
            keyboard.write(text, delay=self.args.type_delay)
            if self.send_enter:
                keyboard.press_and_release('enter')
        else:
            # Use clipboard paste (faster but doesn't work in terminals)
            if not self.keep_clipboard:
                previous_clipboard = pyperclip.paste()
            else:
                previous_clipboard = None
            try:
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                if self.send_enter:
                    pyautogui.press("enter")
            finally:
                if previous_clipboard is not None:
                    time.sleep(0.05)
                    pyperclip.copy(previous_clipboard)

    def run(self):
        self.icon.icon = self.icon_idle
        self.icon.title = "Idle"
        self.icon.run(self._setup)

    def _setup(self, icon: pystray.Icon):
        logger.info("Tray icon setup complete; showing notification.")
        with contextlib.suppress(Exception):
            icon.visible = True
            self.notify(f"Whisper Dictation ready (hotkey {self.args.hotkey})")
        if self.start_popup:
            msg = f"Whisper Dictation is running.\nHotkey: {self.args.hotkey}\nUse the tray icon to start/stop or quit."
            with contextlib.suppress(Exception):
                ctypes.windll.user32.MessageBoxW(0, msg, "Whisper Dictation", 0x00000040)

    def stop(self, icon=None, item=None):
        """Stop the application and exit."""
        with contextlib.suppress(Exception):
            keyboard.remove_hotkey(self.args.hotkey)
        with contextlib.suppress(Exception):
            keyboard.remove_hotkey('esc')
        if self.recording:
            with contextlib.suppress(Exception):
                self.recorder.stop()
        with contextlib.suppress(Exception):
            self.icon.stop()
        # Actually exit the process
        import os
        os._exit(0)


def list_input_devices():
    try:
        devices = sd.query_devices()
    except Exception as exc:
        raise RuntimeError("Could not query audio devices. Ensure PortAudio is installed.") from exc
    entries = []
    for idx, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            entries.append(f"{idx}: {device['name']} (samplerate {int(device['default_samplerate'])})")
    return entries


def parse_args():
    parser = argparse.ArgumentParser(description="Tray dictation button that types Whisper transcriptions into the active window.")
    parser.add_argument("--model-size", default="small", help="Whisper model to load (tiny, base, small, medium, large-v2, etc).")
    parser.add_argument("--device", default="cpu", help="Inference device to use (cpu, cuda).")
    parser.add_argument("--compute-type", default="int8", help="Quantization to use with faster-whisper.")
    parser.add_argument("--samplerate", type=int, default=16000, help="Recording samplerate.")
    parser.add_argument("--language", default="en", help="Language hint for Whisper.")
    parser.add_argument("--beam-size", type=int, default=1, help="Beam size for decoding.")
    parser.add_argument("--hotkey", default="ctrl+alt+space", help="Global hotkey to toggle recording.")
    parser.add_argument("--send-enter", action="store_true", help="Press Enter after typing the transcription.")
    parser.add_argument("--no-trailing-space", action="store_true", help="Do not append an extra space at the end of the text.")
    parser.add_argument("--use-typing", action="store_true", help="Type text character-by-character instead of using clipboard paste (works in terminals).")
    parser.add_argument("--keep-clipboard", action="store_true", help="Leave the clipboard untouched (transcription temporarily replaces it otherwise).")
    parser.add_argument("--show-status-window", action="store_true", help="Show an always-on-top status window for visual feedback.")
    parser.add_argument("--pre-type-delay", type=float, default=0.2, help="Delay (seconds) before typing to allow window focus.")
    parser.add_argument("--type-delay", type=float, default=0.0, help="Delay between keystrokes sent by pyautogui.")
    parser.add_argument("--no-start-popup", action="store_true", help="Suppress the startup confirmation popup window.")
    parser.add_argument("--list-devices", action="store_true", help="List available audio input devices and exit.")
    parser.add_argument("--input-device", type=int, help="Sounddevice input device index to use.")
    parser.add_argument("--icon-path", help="Override path to tray/toast icon (.ico).")
    args = parser.parse_args()
    return args


def check_models_available():
    """Check if any models are downloaded, offer to download if not."""
    downloaded = get_downloaded_models()
    if downloaded:
        return True  # At least one model available

    # No models downloaded - show dialog
    import ctypes
    result = ctypes.windll.user32.MessageBoxW(
        0,
        "No transcription models are downloaded.\n\n"
        "Would you like to open Settings to download a model?\n\n"
        "Click 'Yes' to open Settings, or 'No' to exit.",
        "Whisper Tray - No Models",
        0x00000024  # MB_YESNO | MB_ICONQUESTION
    )

    if result == 6:  # IDYES
        # Open settings to Storage tab
        try:
            import tkinter as tk
            from settings_gui import SettingsWindow
            config = load_config()
            root = tk.Tk()
            root.withdraw()
            settings = SettingsWindow(root, config)
            settings.window.mainloop()
            # Check again after settings closed
            return bool(get_downloaded_models())
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")
            return False
    else:
        return False  # User chose not to download


# Module-level mutex handle - must stay alive for single-instance check to work
_instance_mutex = None

def check_single_instance():
    """Ensure only one instance of WhisperTray is running."""
    global _instance_mutex
    import ctypes
    # Create a named mutex - if it already exists, another instance is running
    mutex_name = "WhisperTray_SingleInstance_Mutex"
    _instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()

    # ERROR_ALREADY_EXISTS = 183
    if last_error == 183:
        ctypes.windll.user32.MessageBoxW(
            0,
            "WhisperTray is already running.\n\nCheck your system tray (click ^ to see hidden icons).",
            "WhisperTray",
            0x00000040  # MB_ICONINFORMATION
        )
        return False
    return True


def main():
    configure_logging()
    set_app_id()

    # Prevent multiple instances
    if not check_single_instance():
        return

    logger.info("Starting Whisper tray helper.")

    # Handle list-devices before loading config
    args = parse_args()
    if args.list_devices:
        for line in list_input_devices():
            print(line)
        return

    # Load configuration
    config = load_config()
    logger.info("Configuration loaded: %s", config)

    # Check for first run - show wizard
    show_settings_after_start = False
    if is_first_run():
        logger.info("First run detected, launching setup wizard.")
        try:
            from first_run import run_first_run_wizard
            wizard_result = run_first_run_wizard()
            if wizard_result is None:
                # User cancelled wizard
                logger.info("User cancelled first-run wizard.")
                return
            config = wizard_result
            show_settings_after_start = True  # Open settings after first run
            logger.info("First-run wizard completed.")
        except Exception as e:
            logger.error(f"First-run wizard failed: {e}")
            # Continue with defaults

    # Check if any models are downloaded
    if not check_models_available():
        logger.info("No models available, exiting.")
        return

    # Merge config with CLI args (CLI takes precedence)
    merged_config = merge_config_with_args(config, args)
    logger.info("Merged configuration: %s", merged_config)

    # Create args namespace from merged config for TrayApp
    class MergedArgs:
        pass

    merged_args = MergedArgs()
    merged_args.model_size = merged_config.get("model_size", "small")
    merged_args.device = merged_config.get("device", "cpu")
    merged_args.compute_type = merged_config.get("compute_type", "int8")
    merged_args.samplerate = merged_config.get("samplerate", 16000)
    merged_args.language = merged_config.get("language", "en")
    merged_args.beam_size = merged_config.get("beam_size", 1)
    merged_args.hotkey = merged_config.get("hotkey", "ctrl+alt+space")
    merged_args.send_enter = merged_config.get("send_enter", True)
    merged_args.no_trailing_space = not merged_config.get("trailing_space", True)
    merged_args.use_typing = merged_config.get("use_typing", False)
    merged_args.keep_clipboard = merged_config.get("keep_clipboard", False)
    merged_args.show_status_window = merged_config.get("show_status_window", False)
    merged_args.pre_type_delay = merged_config.get("pre_type_delay", 0.2)
    merged_args.type_delay = merged_config.get("type_delay", 0.0)
    merged_args.no_start_popup = args.no_start_popup  # Keep CLI value for this
    merged_args.input_device = merged_config.get("input_device")
    merged_args.icon_path = args.icon_path  # Keep CLI value

    logger.info("Arguments parsed: %s", merged_args.__dict__)

    try:
        app = TrayApp(merged_args, merged_config)
        logger.info("TrayApp instantiated, entering run loop.")

        # Open settings after first run so user can review all options
        if show_settings_after_start:
            logger.info("Opening settings after first run.")
            # Schedule settings to open shortly after tray starts
            import threading
            def open_settings_delayed():
                import time
                time.sleep(1)  # Brief delay to let tray initialize
                app._open_settings()
            threading.Thread(target=open_settings_delayed, daemon=True).start()

        app.run()
        logger.info("TrayApp exited run loop.")
    except Exception as e:
        error_type = classify_error(e)
        short_msg, detailed_msg = get_friendly_error(error_type)
        logger.error(f"Failed to start: {e}", exc_info=True)
        # Show error dialog
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"{short_msg}\n\n{detailed_msg}\n\nTechnical: {e}",
                "Whisper Dictation Error",
                0x00000010  # MB_ICONERROR
            )
        except Exception:
            print(f"Error: {short_msg}\n{detailed_msg}")


if __name__ == "__main__":
    # Required for PyInstaller when using multiprocessing or libraries that spawn processes
    # This prevents duplicate processes from running the full main() again
    import multiprocessing
    multiprocessing.freeze_support()
    main()
