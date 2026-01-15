"""
Settings GUI for Whisper Tray.
Provides a tabbed interface for configuring all application settings.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Dict, Any, Optional, List
import webbrowser

import sounddevice as sd

from pathlib import Path
import shutil

# Version info
VERSION = "2.0.15"
GITHUB_URL = "https://github.com/BallParkBanter/whisper-tray"

from config import (
    MODEL_INFO,
    LANGUAGES,
    load_config,
    save_config,
    is_portable_mode,
    get_app_root,
    get_downloaded_models,
    mark_model_downloaded,
)

# Modern flat color scheme - matches wizard theme
COLORS = {
    "bg": "#1e1e2e",           # Dark background
    "surface": "#2a2a3e",      # Elevated surface (cards)
    "primary": "#7c3aed",      # Purple accent (for buttons/tabs)
    "primary_hover": "#8b5cf6",
    "text": "#f4f4f5",         # Primary text
    "text_secondary": "#a1a1aa", # Secondary text
    "success": "#22c55e",      # Green
    "border": "#3f3f5a",       # Subtle border
    "status_text": "#c4b5fd",  # Lighter purple for status text
}


def get_huggingface_cache_path() -> Path:
    """Get the actual HuggingFace cache path where models are stored."""
    # HuggingFace uses these env vars in order of priority
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    if os.environ.get("HUGGINGFACE_HUB_CACHE"):
        return Path(os.environ["HUGGINGFACE_HUB_CACHE"])
    # Default location
    return Path.home() / ".cache" / "huggingface" / "hub"


class SettingsWindow:
    """Settings window with tabbed interface."""

    def __init__(
        self,
        parent: Optional[tk.Tk],
        current_config: Dict[str, Any],
        on_save_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """Initialize the settings window.

        Args:
            parent: Parent tkinter window (can be None for standalone)
            current_config: Current configuration dictionary
            on_save_callback: Function to call when settings are saved
        """
        self.current_config = current_config.copy()
        self.on_save_callback = on_save_callback
        self.result = None  # Will be set to config dict if saved

        # Create window
        if parent:
            self.window = tk.Toplevel(parent)
        else:
            self.window = tk.Tk()

        self.window.title("Whisper Tray Settings")
        self.window.geometry("550x780")  # Increased height for buttons visibility
        self.window.resizable(False, False)
        self.window.configure(bg=COLORS["bg"])

        # Apply modern dark theme
        self._setup_modern_theme()

        # Apply dark title bar after window is created
        self.window.after(100, self._set_dark_title_bar)
        self.window.after(500, self._set_dark_title_bar)  # Fallback

        # Center on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 550) // 2
        y = (self.window.winfo_screenheight() - 780) // 2
        self.window.geometry(f"+{x}+{y}")

        # Variables for form fields
        self._init_variables()

        # Create UI
        self._create_widgets()

        # Make modal
        self.window.transient(parent)
        self.window.grab_set()

    def _setup_modern_theme(self):
        """Configure modern flat dark theme for ttk widgets."""
        style = ttk.Style()
        style.theme_use("clam")

        # Base configuration
        style.configure(".",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["surface"],
            font=("Segoe UI", 10))

        # Frame styling
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])

        # Label styling
        style.configure("TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10))
        style.configure("Title.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 14, "bold"))
        style.configure("Subtitle.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
            font=("Segoe UI", 9))

        # Button styling - primary purple button
        style.configure("TButton",
            background=COLORS["primary"],
            foreground="white",
            font=("Segoe UI", 10),
            padding=(12, 6))
        style.map("TButton",
            background=[("active", COLORS["primary_hover"]), ("disabled", COLORS["border"])],
            foreground=[("disabled", COLORS["text_secondary"])])

        # Secondary button - subtle surface color
        style.configure("Secondary.TButton",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9),
            padding=(8, 4))
        style.map("Secondary.TButton",
            background=[("active", COLORS["border"])])

        # Entry styling
        style.configure("TEntry",
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            padding=8)

        # Combobox styling
        style.configure("TCombobox",
            fieldbackground=COLORS["surface"],
            background=COLORS["surface"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            padding=8)
        style.map("TCombobox",
            fieldbackground=[("readonly", COLORS["surface"])],
            selectbackground=[("readonly", COLORS["primary"])],
            selectforeground=[("readonly", "white")])

        # Checkbutton styling
        style.configure("TCheckbutton",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10),
            indicatorbackground=COLORS["surface"],
            indicatorforeground=COLORS["success"])
        style.map("TCheckbutton",
            background=[("active", COLORS["bg"])],
            indicatorbackground=[("selected", COLORS["success"]), ("pressed", COLORS["success"])],
            indicatorforeground=[("selected", "white"), ("pressed", "white")])

        # Radiobutton styling
        style.configure("TRadiobutton",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10))
        style.map("TRadiobutton",
            background=[("active", COLORS["bg"])],
            indicatorcolor=[("selected", COLORS["primary"])])

        # Notebook (tabs) styling
        style.configure("TNotebook",
            background=COLORS["bg"],
            borderwidth=0)
        style.configure("TNotebook.Tab",
            background=COLORS["surface"],
            foreground=COLORS["text_secondary"],
            padding=(15, 10),
            font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
            background=[("selected", COLORS["primary"]), ("!selected", COLORS["surface"])],
            foreground=[("selected", "white"), ("!selected", COLORS["text_secondary"])],
            padding=[("selected", (15, 10)), ("!selected", (15, 10))])

        # Separator
        style.configure("TSeparator", background=COLORS["border"])

        # LabelFrame
        style.configure("TLabelframe",
            background=COLORS["surface"],
            foreground=COLORS["text"])
        style.configure("TLabelframe.Label",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9, "bold"))

    def _set_dark_title_bar(self):
        """Enable dark title bar on Windows 10/11 with multiple fallback methods."""
        try:
            import ctypes

            # Method 1: Get window handle via GetParent
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())

            # Try multiple DWMWA values (20 for newer Windows, 19 for older builds)
            dwmwa_values = [20, 19]  # DWMWA_USE_IMMERSIVE_DARK_MODE

            for dwmwa in dwmwa_values:
                try:
                    value = ctypes.c_int(1)
                    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, dwmwa,
                        ctypes.byref(value), ctypes.sizeof(value)
                    )
                    if result == 0:  # S_OK
                        return  # Success!
                except Exception:
                    continue

            # Method 2: Try with different window handle approach
            hwnd2 = ctypes.windll.user32.FindWindowW(None, "Whisper Tray Settings")
            if hwnd2:
                for dwmwa in dwmwa_values:
                    try:
                        value = ctypes.c_int(1)
                        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                            hwnd2, dwmwa,
                            ctypes.byref(value), ctypes.sizeof(value)
                        )
                        if result == 0:
                            return
                    except Exception:
                        continue

        except Exception:
            pass  # Silently fail on older Windows or non-Windows

    def _init_variables(self):
        """Initialize tkinter variables for form fields."""
        self.var_model_size = tk.StringVar(value=self.current_config.get("model_size", "small"))
        self.var_language = tk.StringVar(value=self.current_config.get("language", "en"))
        self.var_hotkey = tk.StringVar(value=self.current_config.get("hotkey", "ctrl+alt+space"))
        self.var_input_device = tk.StringVar()
        self.var_send_enter = tk.BooleanVar(value=self.current_config.get("send_enter", True))
        self.var_keep_clipboard = tk.BooleanVar(value=self.current_config.get("keep_clipboard", False))
        self.var_use_typing = tk.BooleanVar(value=self.current_config.get("use_typing", False))
        self.var_show_status = tk.BooleanVar(value=self.current_config.get("show_status_window", False))
        self.var_model_path = tk.StringVar(value=self.current_config.get("model_download_path") or "")

        # New output settings
        self.var_save_log = tk.BooleanVar(value=self.current_config.get("save_transcription_log", True))
        self.var_auto_copy = tk.BooleanVar(value=self.current_config.get("auto_copy_to_clipboard", True))
        self.var_show_toast = tk.BooleanVar(value=self.current_config.get("show_toast_notifications", True))
        self.var_show_transcription_window = tk.BooleanVar(value=self.current_config.get("show_transcription_window", False))
        self.var_transcription_window_on_top = tk.BooleanVar(value=self.current_config.get("transcription_window_always_on_top", True))
        self.var_history_length = tk.IntVar(value=self.current_config.get("history_length", 20))

        # Get available audio devices
        self.audio_devices = self._get_audio_devices()
        current_device = self.current_config.get("input_device")
        if current_device is not None and current_device < len(self.audio_devices):
            self.var_input_device.set(self.audio_devices[current_device])
        elif self.audio_devices:
            self.var_input_device.set(self.audio_devices[0])

    def _get_audio_devices(self) -> List[str]:
        """Get list of available audio input devices."""
        devices = []
        try:
            all_devices = sd.query_devices()
            for idx, device in enumerate(all_devices):
                if device["max_input_channels"] > 0:
                    devices.append(f"{idx}: {device['name']}")
        except Exception:
            devices = ["0: Default Microphone"]
        return devices

    def _create_widgets(self):
        """Create all UI widgets."""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        general_tab = ttk.Frame(self.notebook)
        audio_tab = ttk.Frame(self.notebook)
        behavior_tab = ttk.Frame(self.notebook)
        output_tab = ttk.Frame(self.notebook)
        storage_tab = ttk.Frame(self.notebook)
        about_tab = ttk.Frame(self.notebook)

        self.notebook.add(general_tab, text="General")
        self.notebook.add(audio_tab, text="Audio")
        self.notebook.add(behavior_tab, text="Behavior")
        self.notebook.add(output_tab, text="Output")
        self.notebook.add(storage_tab, text="Models")
        self.notebook.add(about_tab, text="About")

        self._create_general_tab(general_tab)
        self._create_audio_tab(audio_tab)
        self._create_behavior_tab(behavior_tab)
        self._create_output_tab(output_tab)
        self._create_storage_tab(storage_tab)
        self._create_about_tab(about_tab)

        # Buttons frame
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT)

    def _create_general_tab(self, parent):
        """Create the General settings tab."""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Model Size
        ttk.Label(frame, text="Transcription Model:", font=("", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )

        model_frame = ttk.Frame(frame)
        model_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        # Get list of downloaded models
        downloaded_models = get_downloaded_models()

        # Store radio buttons for potential refresh
        self.model_radiobuttons = []

        for i, (model_name, info) in enumerate(MODEL_INFO.items()):
            is_downloaded = model_name in downloaded_models
            text = f"{model_name.capitalize()} - {info['speed']}, {info['accuracy']} ({info['size']})"
            if info.get("recommended"):
                text += " *"
            if not is_downloaded:
                text += " [not downloaded]"

            rb = ttk.Radiobutton(
                model_frame,
                text=text,
                variable=self.var_model_size,
                value=model_name,
                state="normal" if is_downloaded else "disabled",
            )
            rb.grid(row=i, column=0, sticky=tk.W)
            self.model_radiobuttons.append((rb, model_name))

        # Legend row
        legend_frame = ttk.Frame(frame)
        legend_frame.grid(row=2, column=0, sticky=tk.W)
        ttk.Label(legend_frame, text="* Recommended", font=("", 8)).pack(side=tk.LEFT)
        ttk.Label(legend_frame, text="  |  ", font=("", 8)).pack(side=tk.LEFT)
        go_to_models = ttk.Label(
            legend_frame,
            text="Download more models →",
            font=("", 8, "underline"),
            foreground=COLORS["primary"],
            cursor="hand2",
        )
        go_to_models.pack(side=tk.LEFT)
        go_to_models.bind("<Button-1>", lambda e: self.notebook.select(4))  # Models tab is index 4

        # Language
        ttk.Label(frame, text="Language:", font=("", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W, pady=(15, 5)
        )

        lang_combo = ttk.Combobox(
            frame,
            textvariable=self.var_language,
            values=[f"{code} - {name}" for code, name in LANGUAGES.items()],
            state="readonly",
            width=30,
        )
        lang_combo.grid(row=4, column=0, sticky=tk.W)
        # Set current value
        current_lang = self.current_config.get("language", "en")
        if current_lang in LANGUAGES:
            lang_combo.set(f"{current_lang} - {LANGUAGES[current_lang]}")

        # Hotkey
        ttk.Label(frame, text="Hotkey:", font=("", 9, "bold")).grid(
            row=5, column=0, sticky=tk.W, pady=(15, 5)
        )

        hotkey_frame = ttk.Frame(frame)
        hotkey_frame.grid(row=6, column=0, sticky=tk.W)

        self.hotkey_entry = ttk.Entry(hotkey_frame, textvariable=self.var_hotkey, width=25)
        self.hotkey_entry.pack(side=tk.LEFT)

        ttk.Button(hotkey_frame, text="Capture", command=self._capture_hotkey).pack(
            side=tk.LEFT, padx=(10, 0)
        )

    def _create_audio_tab(self, parent):
        """Create the Audio settings tab."""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Microphone Selection
        ttk.Label(frame, text="Microphone:", font=("", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5), columnspan=2
        )

        device_combo = ttk.Combobox(
            frame,
            textvariable=self.var_input_device,
            values=self.audio_devices,
            state="readonly",
            width=38,  # Reduced from 45 to fit Refresh button
        )
        device_combo.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))

        # Refresh button
        ttk.Button(frame, text="Refresh", command=self._refresh_devices, style="Secondary.TButton").grid(
            row=1, column=1, padx=(5, 0), sticky=tk.W
        )

        # Test Recording
        ttk.Label(frame, text="Test Recording:", font=("", 9, "bold")).grid(
            row=2, column=0, sticky=tk.W, pady=(10, 5)
        )

        test_frame = ttk.Frame(frame)
        test_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W)

        self.test_btn = ttk.Button(test_frame, text="Record 3 Seconds", command=self._test_recording)
        self.test_btn.pack(side=tk.LEFT)

        self.test_status = ttk.Label(test_frame, text="")
        self.test_status.pack(side=tk.LEFT, padx=(10, 0))

        # Help text
        ttk.Label(
            frame,
            text="Tip: Click 'Record 3 Seconds' to test your microphone.\nIt will record and play back what it heard.",
            font=("", 8),
            foreground="gray",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(20, 0))

    def _create_behavior_tab(self, parent):
        """Create the Behavior settings tab."""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Checkboxes
        ttk.Checkbutton(
            frame,
            text="Press Enter after transcription",
            variable=self.var_send_enter,
        ).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(
            frame,
            text="Keep clipboard contents (don't overwrite)",
            variable=self.var_keep_clipboard,
        ).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(
            frame,
            text="Use typing mode (for terminals - slower but more compatible)",
            variable=self.var_use_typing,
        ).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(
            frame,
            text="Show status window (always-on-top indicator)",
            variable=self.var_show_status,
        ).pack(anchor=tk.W, pady=5)

        # Explanations
        ttk.Label(
            frame,
            text="\nBehavior Options Explained:",
            font=("", 9, "bold"),
        ).pack(anchor=tk.W, pady=(20, 5))

        explanations = [
            "- Enter: Automatically press Enter after pasting transcription",
            "- Clipboard: Preserves your clipboard instead of using it for paste",
            "- Typing mode: Types character-by-character (works in terminals)",
            "- Status window: Shows recording/transcribing status on screen",
        ]
        for exp in explanations:
            ttk.Label(frame, text=exp, font=("", 8), foreground="gray").pack(anchor=tk.W)

    def _create_output_tab(self, parent):
        """Create the Output settings tab."""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Notifications section
        ttk.Label(frame, text="Notifications:", font=("", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))

        ttk.Checkbutton(
            frame,
            text="Show toast notifications",
            variable=self.var_show_toast,
        ).pack(anchor=tk.W, pady=2)

        # Transcription Window section - DISABLED for future release
        # ttk.Label(frame, text="Transcription Window:", font=("", 9, "bold")).pack(anchor=tk.W, pady=(15, 5))
        #
        # ttk.Checkbutton(
        #     frame,
        #     text="Show real-time transcription window",
        #     variable=self.var_show_transcription_window,
        # ).pack(anchor=tk.W, pady=2)
        #
        # ttk.Checkbutton(
        #     frame,
        #     text="Keep transcription window always on top",
        #     variable=self.var_transcription_window_on_top,
        # ).pack(anchor=tk.W, padx=(20, 0), pady=2)

        # Logging section
        ttk.Label(frame, text="Transcription Logging:", font=("", 9, "bold")).pack(anchor=tk.W, pady=(15, 5))

        ttk.Checkbutton(
            frame,
            text="Save transcriptions to daily log files",
            variable=self.var_save_log,
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            frame,
            text="Always copy transcription to clipboard",
            variable=self.var_auto_copy,
        ).pack(anchor=tk.W, pady=2)

        # History section
        ttk.Label(frame, text="History:", font=("", 9, "bold")).pack(anchor=tk.W, pady=(15, 5))

        history_frame = ttk.Frame(frame)
        history_frame.pack(anchor=tk.W, pady=2)

        ttk.Label(history_frame, text="Number of items to keep in history:").pack(side=tk.LEFT)

        history_spinbox = ttk.Spinbox(
            history_frame,
            from_=5,
            to=50,
            width=5,
            textvariable=self.var_history_length,
        )
        history_spinbox.pack(side=tk.LEFT, padx=(10, 0))

        # Info text
        ttk.Label(
            frame,
            text="\nNote: Log files are organized by date in the\nWhisperTray config folder (year/month/day.txt).",
            font=("", 8),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(15, 0))

    def _create_storage_tab(self, parent):
        """Create the Storage settings tab with Model Manager."""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Storage Locations section
        ttk.Label(frame, text="Storage Locations", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # Model location (read-only - shows actual HuggingFace cache)
        model_cache = get_huggingface_cache_path()
        ttk.Label(frame, text="Models:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text=str(model_cache),
            style="Subtitle.TLabel",
            wraplength=500,
        ).pack(anchor=tk.W, padx=(10, 0))

        # Config/logs location
        from config import get_config_dir, get_transcription_log_dir
        config_dir = get_config_dir()
        ttk.Label(frame, text="Settings & Logs:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        ttk.Label(
            frame,
            text=str(config_dir),
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, padx=(10, 0))

        # Show portable mode indicator if applicable
        if is_portable_mode():
            ttk.Label(
                frame,
                text="📁 Running in Portable Mode",
                foreground=COLORS["success"],
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor=tk.W, pady=(10, 0))

        # Separator
        ttk.Separator(frame).pack(fill=tk.X, pady=15)

        # Model Manager section
        ttk.Label(frame, text="Model Manager", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            frame,
            text="Download or delete models. ✓ = downloaded, * = recommended",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(0, 5))

        # Status frame with border for visibility
        status_frame = tk.Frame(frame, bg=COLORS["surface"], padx=10, pady=8)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # Status label for downloads - prominent placement ABOVE model list
        self.storage_status = tk.Label(
            status_frame,
            text="Select a model to download",
            font=("Segoe UI", 10),
            fg=COLORS["text_secondary"],
            bg=COLORS["surface"]
        )
        self.storage_status.pack(anchor=tk.W)

        # Model list frame (no expand to prevent pushing content)
        self.model_list_frame = ttk.Frame(frame)
        self.model_list_frame.pack(fill=tk.X)

        # Populate model list
        self._refresh_model_list()

    def _create_about_tab(self, parent):
        """Create the About tab with version info and links."""
        frame = ttk.Frame(parent, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # App name and version
        ttk.Label(
            frame,
            text="WhisperTray",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 5))

        ttk.Label(
            frame,
            text=f"Version {VERSION}",
            font=("Segoe UI", 11),
        ).pack(pady=(0, 20))

        # Description
        ttk.Label(
            frame,
            text="Local speech-to-text for Windows.\nPress a hotkey, talk, and your words appear.",
            font=("Segoe UI", 10),
            justify=tk.CENTER,
        ).pack(pady=(0, 20))

        # Why I built this
        why_frame = ttk.LabelFrame(frame, text="Why I Built This", padding=10)
        why_frame.pack(fill=tk.X, pady=(0, 20))

        why_text = (
            "I wanted fast voice-to-text for terminal-based AI coding tools "
            "(Claude Code, Codex, etc.) without needing a browser interface. "
            "I can talk way faster than I type, and I wanted something simple, "
            "lightweight, and reliable that just works."
        )
        ttk.Label(
            why_frame,
            text=why_text,
            wraplength=400,
            justify=tk.LEFT,
        ).pack()

        # Links
        links_frame = ttk.Frame(frame)
        links_frame.pack(pady=(0, 20))

        github_btn = ttk.Button(
            links_frame,
            text="GitHub Repository",
            command=lambda: webbrowser.open(GITHUB_URL),
        )
        github_btn.pack(side=tk.LEFT, padx=5)

        releases_btn = ttk.Button(
            links_frame,
            text="Download Latest",
            command=lambda: webbrowser.open(f"{GITHUB_URL}/releases/latest"),
        )
        releases_btn.pack(side=tk.LEFT, padx=5)

        # Credits
        ttk.Label(
            frame,
            text="Built with faster-whisper and OpenAI Whisper",
            font=("Segoe UI", 9),
            foreground="#888888",
        ).pack(pady=(10, 0))

        ttk.Label(
            frame,
            text="100% local - your voice never leaves your computer",
            font=("Segoe UI", 9),
            foreground="#888888",
        ).pack()

    def _refresh_model_list(self):
        """Refresh the model list with current download status."""
        # Clear existing widgets
        for widget in self.model_list_frame.winfo_children():
            widget.destroy()

        downloaded = get_downloaded_models()

        # Also update the radio buttons on General tab if they exist
        if hasattr(self, 'model_radiobuttons'):
            for rb, model_name in self.model_radiobuttons:
                is_downloaded = model_name in downloaded
                info = MODEL_INFO.get(model_name, {})
                text = f"{model_name.capitalize()} - {info['speed']}, {info['accuracy']} ({info['size']})"
                if info.get("recommended"):
                    text += " *"
                if not is_downloaded:
                    text += " [not downloaded]"
                rb.configure(text=text, state="normal" if is_downloaded else "disabled")

        for model_name, info in MODEL_INFO.items():
            row = ttk.Frame(self.model_list_frame)
            row.pack(fill=tk.X, pady=3)

            # Status indicator
            is_downloaded = model_name in downloaded
            status = "✓" if is_downloaded else "  "
            rec = " *" if info.get("recommended") else ""

            # Model info label
            label_text = f"{status} {model_name.capitalize()} ({info['size']}){rec}"
            ttk.Label(row, text=label_text, width=30).pack(side=tk.LEFT)

            # Action button - use Secondary style for less visual weight
            if is_downloaded:
                btn = ttk.Button(
                    row,
                    text="Delete",
                    style="Secondary.TButton",
                    width=10,
                    command=lambda m=model_name: self._delete_model(m),
                )
            else:
                btn = ttk.Button(
                    row,
                    text="Download",
                    width=10,
                    command=lambda m=model_name: self._download_model(m),
                )
            btn.pack(side=tk.RIGHT, padx=(5, 0))

    def _download_model(self, model_name: str):
        """Download a model with progress tracking."""
        # Immediate visual feedback - change button state
        for widget in self.model_list_frame.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and child.cget("text") == "Download":
                    child.configure(state="disabled")

        model_info = MODEL_INFO.get(model_name, {})
        size_str = model_info.get("size", "100 MB")

        # Parse expected size
        try:
            size_str_clean = size_str.replace("~", "").strip()
            if "GB" in size_str_clean:
                expected_mb = float(size_str_clean.replace("GB", "").strip()) * 1024
            else:
                expected_mb = float(size_str_clean.replace("MB", "").strip())
        except Exception:
            expected_mb = 100

        # Show immediate feedback - update status label
        status_text = f"⏳ Starting download of {model_name} (~{expected_mb:.0f} MB)..."
        self.storage_status.configure(text=status_text, fg=COLORS["primary"])
        self.window.update_idletasks()
        self.window.update()

        # Track download state
        self._download_active = True
        self._download_model_name = model_name
        self._download_expected_mb = expected_mb

        # Animated dots for progress
        self._dot_count = 0

        def update_progress():
            """Update status with animated dots and check for completion."""
            # Check if download finished
            if not self._download_active:
                # Download finished - show result
                if hasattr(self, '_download_success'):
                    if self._download_success:
                        self.storage_status.configure(
                            text=f"✓ {self._download_model_name} downloaded successfully!",
                            fg=COLORS["success"]
                        )
                    else:
                        error_msg = self._download_error[:50] + "..." if len(self._download_error) > 50 else self._download_error
                        self.storage_status.configure(
                            text=f"✗ Failed: {error_msg}",
                            fg="#ef4444"
                        )
                    self._refresh_model_list()
                return

            # Still downloading - show animated progress
            self._dot_count = (self._dot_count + 1) % 4
            dots = "." * self._dot_count + " " * (3 - self._dot_count)
            self.storage_status.configure(
                text=f"⏳ Downloading {self._download_model_name} (~{self._download_expected_mb:.0f} MB){dots}",
                fg=COLORS["status_text"]
            )
            # Schedule next update
            self.window.after(500, update_progress)

        def do_download():
            try:
                # Use faster_whisper directly (bundled in EXE) - same as wizard
                # Disable HuggingFace progress bars (can hang in windowed mode)
                os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
                os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

                # Import faster_whisper (bundled in the EXE)
                from faster_whisper import WhisperModel

                # Load model - this triggers download if not cached
                # Use CPU directly - CUDA detection can hang on non-CUDA systems
                model = WhisperModel(model_name, device="cpu", compute_type="int8")
                del model  # Release memory

                # Mark as downloaded
                mark_model_downloaded(model_name)
                self._download_active = False
                self._download_success = True
                self._download_error = ""

            except Exception as e:
                self._download_active = False
                self._download_success = False
                self._download_error = str(e)

        # Initialize completion flags
        self._download_success = False
        self._download_error = ""

        # Start progress updates and download thread
        self.window.after(500, update_progress)
        threading.Thread(target=do_download, daemon=True).start()

    def _delete_model(self, model_name: str):
        """Delete a downloaded model."""
        if not messagebox.askyesno(
            "Delete Model",
            f"Are you sure you want to delete the {model_name} model?\n\n"
            "You can re-download it later if needed.",
        ):
            return

        try:
            # Models are in HuggingFace cache
            hf_cache = get_huggingface_cache_path()

            # HuggingFace stores models as: models--Systran--faster-whisper-{model}
            model_dir = hf_cache / f"models--Systran--faster-whisper-{model_name}"

            deleted = False
            if model_dir.exists():
                shutil.rmtree(model_dir)
                deleted = True

            # Remove from downloaded list in config
            config = load_config()
            if "downloaded_models" in config and model_name in config["downloaded_models"]:
                config["downloaded_models"].remove(model_name)
                save_config(config)

            if deleted:
                self.storage_status.configure(text=f"✓ {model_name} deleted", fg=COLORS["success"])
            else:
                # Still remove from config even if files not found
                self.storage_status.configure(text=f"✓ {model_name} removed from list", fg=COLORS["success"])

            self._refresh_model_list()

        except Exception as e:
            self.storage_status.configure(text=f"✗ Failed to delete: {e}", fg="#ef4444")

    def _refresh_devices(self):
        """Refresh the list of audio devices."""
        self.audio_devices = self._get_audio_devices()
        # Update combobox
        for widget in self.window.winfo_children():
            self._update_device_combo(widget)

    def _update_device_combo(self, widget):
        """Recursively find and update device combobox."""
        if isinstance(widget, ttk.Combobox) and widget.cget("textvariable") == str(self.var_input_device):
            widget.configure(values=self.audio_devices)
        for child in widget.winfo_children():
            self._update_device_combo(child)

    def _capture_hotkey(self):
        """Open dialog to capture a new hotkey."""
        capture_window = tk.Toplevel(self.window)
        capture_window.title("Press Hotkey")
        capture_window.geometry("300x100")
        capture_window.transient(self.window)
        capture_window.grab_set()

        # Center
        capture_window.update_idletasks()
        x = self.window.winfo_x() + (self.window.winfo_width() - 300) // 2
        y = self.window.winfo_y() + (self.window.winfo_height() - 100) // 2
        capture_window.geometry(f"+{x}+{y}")

        ttk.Label(
            capture_window,
            text="Press your desired hotkey combination...",
            font=("", 10),
        ).pack(pady=20)

        self.captured_keys = set()

        def on_key_press(event):
            key = event.keysym.lower()
            if key in ("control_l", "control_r"):
                self.captured_keys.add("ctrl")
            elif key in ("alt_l", "alt_r"):
                self.captured_keys.add("alt")
            elif key in ("shift_l", "shift_r"):
                self.captured_keys.add("shift")
            else:
                self.captured_keys.add(key)

        def on_key_release(event):
            if len(self.captured_keys) >= 2:
                # Build hotkey string
                modifiers = []
                key = None
                for k in self.captured_keys:
                    if k in ("ctrl", "alt", "shift"):
                        modifiers.append(k)
                    else:
                        key = k
                if modifiers and key:
                    hotkey = "+".join(sorted(modifiers) + [key])
                    self.var_hotkey.set(hotkey)
                    capture_window.destroy()

        capture_window.bind("<KeyPress>", on_key_press)
        capture_window.bind("<KeyRelease>", on_key_release)
        capture_window.focus_set()

    def _test_recording(self):
        """Test microphone by recording and playing back."""
        self.test_btn.configure(state="disabled")
        self.test_status.configure(text="Recording...")

        def do_test():
            try:
                # Get selected device index
                device_str = self.var_input_device.get()
                device_idx = int(device_str.split(":")[0]) if device_str else None

                # Record 3 seconds
                samplerate = 16000
                duration = 3
                audio = sd.rec(
                    int(duration * samplerate),
                    samplerate=samplerate,
                    channels=1,
                    device=device_idx,
                )
                sd.wait()

                # Update status
                self.window.after(0, lambda: self.test_status.configure(text="Playing..."))

                # Play back
                sd.play(audio, samplerate=samplerate)
                sd.wait()

                self.window.after(0, lambda: self.test_status.configure(text="Done!"))
            except Exception as e:
                self.window.after(
                    0, lambda: self.test_status.configure(text=f"Error: {str(e)[:30]}")
                )
            finally:
                self.window.after(0, lambda: self.test_btn.configure(state="normal"))

        threading.Thread(target=do_test, daemon=True).start()

    # Model path browse/reset removed - faster-whisper always uses HuggingFace cache

    def _save(self):
        """Save settings and close window."""
        # Build config dict - start with FRESH config from disk
        # This preserves downloaded_models that were added during this session
        new_config = load_config()

        new_config["model_size"] = self.var_model_size.get()

        # Extract language code from combo value
        lang_value = self.var_language.get()
        if " - " in lang_value:
            new_config["language"] = lang_value.split(" - ")[0]
        else:
            new_config["language"] = lang_value

        new_config["hotkey"] = self.var_hotkey.get()

        # Extract device index
        device_str = self.var_input_device.get()
        if device_str:
            try:
                new_config["input_device"] = int(device_str.split(":")[0])
            except ValueError:
                new_config["input_device"] = None
        else:
            new_config["input_device"] = None

        new_config["send_enter"] = self.var_send_enter.get()
        new_config["keep_clipboard"] = self.var_keep_clipboard.get()
        new_config["use_typing"] = self.var_use_typing.get()
        new_config["show_status_window"] = self.var_show_status.get()

        # Output settings
        new_config["save_transcription_log"] = self.var_save_log.get()
        new_config["auto_copy_to_clipboard"] = self.var_auto_copy.get()
        new_config["show_toast_notifications"] = self.var_show_toast.get()
        new_config["show_transcription_window"] = self.var_show_transcription_window.get()
        new_config["transcription_window_always_on_top"] = self.var_transcription_window_on_top.get()
        new_config["history_length"] = self.var_history_length.get()

        # Model path removed - faster-whisper always uses HuggingFace cache

        # Save to file
        save_config(new_config)

        # Call callback if provided
        if self.on_save_callback:
            self.on_save_callback(new_config)

        self.result = new_config
        self.window.destroy()

    def _cancel(self):
        """Cancel and close window without saving."""
        self.result = None
        self.window.destroy()

    def run(self) -> Optional[Dict[str, Any]]:
        """Run the settings window and return result.

        Returns:
            Configuration dict if saved, None if cancelled
        """
        self.window.mainloop()
        return self.result


def show_settings(
    parent: Optional[tk.Tk] = None,
    current_config: Optional[Dict[str, Any]] = None,
    on_save: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Optional[Dict[str, Any]]:
    """Show the settings window.

    Args:
        parent: Parent window (optional)
        current_config: Current config (loads from file if not provided)
        on_save: Callback when settings are saved

    Returns:
        New config dict if saved, None if cancelled
    """
    if current_config is None:
        current_config = load_config()

    window = SettingsWindow(parent, current_config, on_save)
    return window.run()


if __name__ == "__main__":
    # Test the settings window standalone
    result = show_settings()
    if result:
        print("Settings saved:", result)
    else:
        print("Settings cancelled")
