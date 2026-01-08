"""
First-run wizard for Whisper Tray.
Guides new users through initial setup: microphone, hotkey, model selection, and downloads.
Modern, sleek UI design for 2025.
"""
import os
import sys

# Disable HuggingFace progress bars BEFORE any imports - they can hang in windowed mode
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any, Optional, List
from pathlib import Path

import sounddevice as sd

# DEBUG: Log button sizes and download progress
DEBUG_BUTTONS = False  # Disabled - testing complete
DEBUG_LOG_FILE = None

def debug_log(msg):
    """Log to both console and file."""
    global DEBUG_LOG_FILE
    if not DEBUG_BUTTONS:
        return

    print(f"[DEBUG] {msg}")

    # Also write to file (in case no console)
    try:
        if DEBUG_LOG_FILE is None:
            import tempfile
            DEBUG_LOG_FILE = os.path.join(tempfile.gettempdir(), "whispertray_debug.log")
        with open(DEBUG_LOG_FILE, 'a') as f:
            f.write(f"[DEBUG] {msg}\n")
    except:
        pass

from config import (
    MODEL_INFO,
    LANGUAGES,
    load_config,
    save_config,
    get_default_model_path,
    get_config_dir,
    mark_first_run_complete,
    mark_model_downloaded,
    get_downloaded_models,
    is_portable_mode,
    get_app_root,
)
import installer

# Modern flat color scheme - clean Windows 11 style
COLORS = {
    "bg": "#1e1e2e",           # Dark background
    "surface": "#2a2a3e",      # Elevated surface (cards)
    "primary": "#7c3aed",      # Purple accent
    "primary_hover": "#8b5cf6",
    "text": "#f4f4f5",         # Primary text
    "text_secondary": "#a1a1aa", # Secondary text
    "success": "#22c55e",      # Green
    "border": "#3f3f5a",       # Subtle border
}


class FirstRunWizard:
    """First-run setup wizard with multiple steps."""

    def __init__(self):
        """Initialize the wizard."""
        debug_log("="*50)
        debug_log("FirstRunWizard __init__ starting")
        debug_log(f"Python: {sys.version}")
        debug_log(f"Frozen: {getattr(sys, 'frozen', False)}")
        if hasattr(sys, '_MEIPASS'):
            debug_log(f"_MEIPASS: {sys._MEIPASS}")

        self.config = load_config()
        self.result = None
        self.current_step = 0
        self.steps = [
            ("Welcome", self._create_welcome_step),
            ("Install Type", self._create_install_type_step),
            ("Microphone", self._create_mic_step),
            ("Hotkey", self._create_hotkey_step),
            ("Download Models", self._create_download_step),
            ("Select Model", self._create_model_step),
            ("Complete", self._create_complete_step),
        ]

        # Create main window
        self.window = tk.Tk()
        self.window.title("Whisper Dictation Setup")
        self.window.geometry("620x600")
        self.window.resizable(False, False)
        self.window.configure(bg=COLORS["bg"])

        # Log Tk info
        debug_log(f"Tk scaling: {self.window.tk.call('tk', 'scaling')}")
        debug_log(f"Screen: {self.window.winfo_screenwidth()}x{self.window.winfo_screenheight()}")

        # Apply modern theme
        self._setup_modern_theme()

        # Center on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 620) // 2
        y = (self.window.winfo_screenheight() - 650) // 2
        self.window.geometry(f"+{x}+{y}")

        # Initialize variables
        self._init_variables()

        # Create UI structure
        self._create_layout()

        # Show first step
        self._show_step(0)

        # Enable dark title bar after window is displayed (needs delay for window handle)
        self.window.after(100, self._set_dark_title_bar)
        # Also try again after a longer delay as fallback
        self.window.after(500, self._set_dark_title_bar)

        # DEBUG: Log button sizes after rendering
        self.window.after(200, self._debug_log_buttons)
        self.window.after(1000, self._debug_log_buttons)

    def _debug_log_buttons(self):
        """Log all button sizes for debugging."""
        debug_log("--- Button sizes ---")
        for btn in [self.back_btn, self.next_btn, self.skip_btn]:
            try:
                btn.update_idletasks()
                name = getattr(btn, '_debug_name', 'unknown')
                debug_log(f"  {name}: width={btn.winfo_width()}, height={btn.winfo_height()}")
            except:
                pass

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
            font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
            font=("Segoe UI", 10))
        style.configure("Card.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"])
        style.configure("Dim.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
            font=("Segoe UI", 9))

        # Button styling - primary purple button
        style.configure("TButton",
            background=COLORS["primary"],
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(20, 10))
        style.map("TButton",
            background=[("active", COLORS["primary_hover"]), ("disabled", COLORS["border"])],
            foreground=[("disabled", COLORS["text_secondary"])])

        # Secondary button - subtle surface color
        style.configure("Secondary.TButton",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10),
            padding=(15, 8))
        style.map("Secondary.TButton",
            background=[("active", COLORS["border"])])

        # Entry styling
        style.configure("TEntry",
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            padding=10)

        # Combobox styling
        style.configure("TCombobox",
            fieldbackground=COLORS["surface"],
            background=COLORS["surface"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            padding=10)
        style.map("TCombobox",
            fieldbackground=[("readonly", COLORS["surface"])],
            selectbackground=[("readonly", COLORS["primary"])],
            selectforeground=[("readonly", "white")])

        # Radiobutton styling
        style.configure("TRadiobutton",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10))
        style.map("TRadiobutton",
            background=[("active", COLORS["bg"])],
            indicatorcolor=[("selected", COLORS["primary"])])

        # Radiobutton on card background
        style.configure("Card.TRadiobutton",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI", 11, "bold"))
        style.map("Card.TRadiobutton",
            background=[("active", COLORS["surface"])],
            indicatorcolor=[("selected", COLORS["primary"])])

        # Checkbutton styling - green when selected
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

        # Progress bar
        style.configure("TProgressbar",
            background=COLORS["primary"],
            troughcolor=COLORS["surface"],
            thickness=6)

        # Separator
        style.configure("TSeparator", background=COLORS["border"])

        # LabelFrame
        style.configure("TLabelframe",
            background=COLORS["surface"],
            foreground=COLORS["text"])
        style.configure("TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["primary"],
            font=("Segoe UI", 10, "bold"))

    def _set_dark_title_bar(self):
        """Enable dark title bar on Windows 10/11 with multiple fallback methods."""
        try:
            import ctypes
            from ctypes import wintypes

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
            hwnd2 = ctypes.windll.user32.FindWindowW(None, "Whisper Dictation Setup")
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

    def _create_styled_button(self, parent, text, command, style="primary", **pack_kwargs):
        """Create a button using Label widget - proven to work on all DPI settings.

        Uses tk.Label styled as a button with click/hover bindings.
        This approach works reliably across all Windows DPI configurations
        because Labels don't have the same rendering issues as tk.Button/ttk.Button.
        """
        debug_log(f"Creating button '{text}' parent={type(parent).__name__} style={style}")

        colors = {
            "primary": {"bg": COLORS["primary"], "fg": "white", "hover": COLORS["primary_hover"], "pressed": "#5b21b6"},
            "secondary": {"bg": COLORS["surface"], "fg": COLORS["text"], "hover": COLORS["border"], "pressed": "#1e1e2e"},
        }
        c = colors.get(style, colors["primary"])
        font = ("Segoe UI", 10, "bold" if style == "primary" else "normal")

        # Use Label styled as button - this works on ALL DPI settings
        btn = tk.Label(
            parent,
            text=text,
            bg=c["bg"],
            fg=c["fg"],
            font=font,
            padx=20 if style == "primary" else 15,
            pady=10 if style == "primary" else 8,
            relief="raised",
            bd=2,
            cursor="hand2",
        )
        btn._debug_name = text

        # Store state for enable/disable functionality
        btn._command = command
        btn._enabled = True
        btn._colors = c

        # Bind click events with visual press/release feedback
        def on_press(e):
            if btn._enabled:
                btn.configure(bg=c["pressed"], relief="sunken")
        def on_release(e):
            if btn._enabled:
                btn.configure(bg=c["hover"], relief="raised")
                if btn._command:
                    btn._command()
        btn.bind("<ButtonPress-1>", on_press)
        btn.bind("<ButtonRelease-1>", on_release)

        # Bind hover events
        def on_enter(e):
            if btn._enabled:
                e.widget.configure(bg=c["hover"])
        def on_leave(e):
            if btn._enabled:
                e.widget.configure(bg=c["bg"])
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        # Add configure method to handle state changes (for compatibility)
        original_configure = btn.configure
        def custom_configure(**kwargs):
            if "state" in kwargs:
                state = kwargs.pop("state")
                btn._enabled = (state != "disabled")
                if not btn._enabled:
                    btn.config(fg=COLORS["text_secondary"], cursor="arrow")
                else:
                    btn.config(fg=c["fg"], cursor="hand2")
            if "text" in kwargs:
                btn.config(text=kwargs.pop("text"))
            if "command" in kwargs:
                btn._command = kwargs.pop("command")
            if kwargs:
                original_configure(**kwargs)
        btn.configure = custom_configure

        if pack_kwargs:
            btn.pack(**pack_kwargs)

        return btn

    def _init_variables(self):
        """Initialize tkinter variables."""
        self.var_input_device = tk.StringVar()
        self.var_hotkey = tk.StringVar(value=self.config.get("hotkey", "ctrl+alt+space"))
        self.var_model_size = tk.StringVar(value=self.config.get("model_size", "small"))
        # Pre-fill model path with default if not set in config
        config_path = self.config.get("model_download_path")
        if config_path:
            self.var_model_path = tk.StringVar(value=config_path)
        else:
            # Use appropriate default based on mode
            if is_portable_mode():
                default_path = get_app_root() / "models"
            else:
                default_path = get_default_model_path()
            self.var_model_path = tk.StringVar(value=str(default_path))
        # Install type: "standard" or "portable"
        self.var_install_type = tk.StringVar(value="portable" if is_portable_mode() else "standard")
        # Run at Windows startup (for standard install)
        self.var_run_at_startup = tk.BooleanVar(value=True)
        # Portable install path
        self.var_portable_path = tk.StringVar(value="")

        # Model download checkboxes
        self.var_download_models = {}
        for model_name in MODEL_INFO.keys():
            # Pre-select recommended model
            default = MODEL_INFO[model_name].get("recommended", False)
            self.var_download_models[model_name] = tk.BooleanVar(value=default)

        # Get audio devices (Windows default is always first in list)
        self.audio_devices = self._get_audio_devices()
        if self.audio_devices:
            current_device = self.config.get("input_device")
            if current_device is not None:
                # Try to find the configured device by index
                for dev in self.audio_devices:
                    if dev.startswith(f"{current_device}:"):
                        self.var_input_device.set(dev)
                        break
                else:
                    # Configured device not found, use first (Windows default)
                    self.var_input_device.set(self.audio_devices[0])
            else:
                # No config, use first device (Windows default)
                self.var_input_device.set(self.audio_devices[0])

    def _get_audio_devices(self) -> List[str]:
        """Get list of available audio input devices with best default first."""
        devices = []
        default_device_str = None
        first_mic_str = None  # Fallback: first device with "Microphone" in name
        try:
            all_devices = sd.query_devices()
            # Get Windows default input device
            try:
                default_input = sd.default.device[0]  # (input, output) tuple
                if default_input is not None and default_input < 0:
                    default_input = None  # -1 means no default set
            except Exception:
                default_input = None

            for idx, device in enumerate(all_devices):
                if device["max_input_channels"] > 0:
                    name = device['name']
                    # Skip loopback devices
                    if "Stereo Mix" in name:
                        devices.append(f"{idx}: {name}")
                        continue

                    # Mark the Windows default device
                    if default_input is not None and idx == default_input:
                        default_device_str = f"{idx}: {name} ★ Windows Default"
                    else:
                        device_str = f"{idx}: {name}"
                        devices.append(device_str)
                        # Track first real microphone as fallback
                        if first_mic_str is None and "Microphone" in name:
                            first_mic_str = device_str

            # Put the best default FIRST in the list
            if default_device_str:
                # Windows default exists - put it first
                devices.insert(0, default_device_str)
            elif first_mic_str:
                # No Windows default, but found a microphone - move it first
                devices.remove(first_mic_str)
                devices.insert(0, first_mic_str + " ★ Recommended")
        except Exception:
            devices = ["0: Default Microphone"]
        return devices

    def _create_layout(self):
        """Create the main layout structure."""
        # Header with step indicator
        self.header_frame = ttk.Frame(self.window)
        self.header_frame.pack(fill=tk.X, padx=30, pady=(25, 15))

        self.step_label = ttk.Label(
            self.header_frame,
            text="Step 1 of 6",
            style="Subtitle.TLabel",
        )
        self.step_label.pack(side=tk.RIGHT)

        self.title_label = ttk.Label(
            self.header_frame,
            text="Welcome",
            style="Title.TLabel",
        )
        self.title_label.pack(side=tk.LEFT)

        # Step progress indicator (dots)
        self.progress_dots_frame = ttk.Frame(self.window)
        self.progress_dots_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
        self._create_progress_dots()

        # Content area
        self.content_frame = ttk.Frame(self.window)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # Button frame - use tk.Frame for better compatibility with tk.Button on high-DPI
        self.button_frame = tk.Frame(self.window, bg=COLORS["bg"])
        self.button_frame.pack(fill=tk.X, padx=30, pady=(10, 25))

        # Navigation buttons with fallback rendering
        self.back_btn = self._create_styled_button(
            self.button_frame, "← Back", self._prev_step, style="secondary",
            side=tk.LEFT
        )

        self.next_btn = self._create_styled_button(
            self.button_frame, "Next →", self._next_step, style="primary",
            side=tk.RIGHT
        )

        self.skip_btn = self._create_styled_button(
            self.button_frame, "Skip Setup", self._skip, style="secondary",
            side=tk.RIGHT, padx=(0, 15)
        )

    def _create_progress_dots(self):
        """Create step progress indicator dots."""
        for widget in self.progress_dots_frame.winfo_children():
            widget.destroy()

        for i in range(len(self.steps)):
            if i == self.current_step:
                color = COLORS["primary"]
                size = 12
            elif i < self.current_step:
                color = COLORS["success"]
                size = 10
            else:
                color = COLORS["border"]
                size = 10

            dot = tk.Canvas(
                self.progress_dots_frame,
                width=size + 4,
                height=size + 4,
                bg=COLORS["bg"],
                highlightthickness=0
            )
            dot.create_oval(2, 2, size + 2, size + 2, fill=color, outline="")
            dot.pack(side=tk.LEFT, padx=3)

    def _show_step(self, step_index: int):
        """Show a specific wizard step."""
        self.current_step = step_index

        # Update header
        step_name, step_creator = self.steps[step_index]
        self.title_label.configure(text=step_name)
        self.step_label.configure(text=f"Step {step_index + 1} of {len(self.steps)}")

        # Update progress dots
        self._create_progress_dots()

        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Create step content
        step_creator(self.content_frame)

        # Update buttons
        self.back_btn.configure(state="normal" if step_index > 0 else "disabled")

        if step_index == len(self.steps) - 1:
            self.next_btn.configure(text="Finish")
            self.skip_btn.pack_forget()
        elif step_index == 4:  # Download step (index 4)
            self.next_btn.configure(text="Download & Continue")
            self.skip_btn.pack(side=tk.RIGHT, padx=(0, 10))
        else:
            self.next_btn.configure(text="Next →")
            self.skip_btn.pack(side=tk.RIGHT, padx=(0, 10))

    def _next_step(self):
        """Go to next step."""
        # Handle download step specially
        if self.current_step == 4:  # Download step (index 4)
            self._start_downloads()
            return

        if self.current_step < len(self.steps) - 1:
            self._show_step(self.current_step + 1)
        else:
            self._finish()

    def _prev_step(self):
        """Go to previous step."""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _skip(self):
        """Skip the wizard with defaults."""
        if messagebox.askyesno(
            "Skip Setup",
            "Are you sure you want to skip setup?\n\nYou can configure settings later from the tray menu.",
        ):
            self._save_config()
            mark_first_run_complete()
            self.result = self.config
            self.window.destroy()

    def _finish(self):
        """Complete the wizard and perform installation if needed."""
        install_type = self.var_install_type.get()

        # Check if installation is needed (not already in proper location)
        if not installer.is_running_from_install_location():
            try:
                if install_type == "standard":
                    # Standard install: copy to AppData, create shortcuts
                    exe_path = installer.install_standard()
                    installer.create_start_menu_shortcut(exe_path)

                    if self.var_run_at_startup.get():
                        installer.add_to_startup(exe_path, True)

                    self.installed_exe_path = exe_path
                    self.installation_message = (
                        f"Installed to: {exe_path.parent}\n\n"
                        "Start Menu shortcut created.\n"
                        "You can safely delete the file in Downloads."
                    )

                elif install_type == "portable":
                    # Portable install: copy to chosen folder
                    portable_path = self.var_portable_path.get().strip()
                    if not portable_path:
                        messagebox.showerror(
                            "Error",
                            "Please select a folder for portable installation."
                        )
                        return

                    target_folder = Path(portable_path)
                    exe_path = installer.install_portable(target_folder)

                    # Set HF_HOME for portable models
                    models_dir = target_folder / "models"
                    os.environ["HF_HOME"] = str(models_dir)

                    self.installed_exe_path = exe_path
                    self.installation_message = (
                        f"Installed to: {target_folder}\n\n"
                        "All files are self-contained in this folder.\n"
                        "You can safely delete the file in Downloads."
                    )

            except PermissionError as e:
                messagebox.showerror(
                    "Permission Error",
                    f"Could not install to the selected location:\n{e}\n\n"
                    "Try running as administrator or choosing a different folder."
                )
                return
            except Exception as e:
                messagebox.showerror(
                    "Installation Error",
                    f"An error occurred during installation:\n{e}"
                )
                return
        else:
            # Already installed, no copy needed
            self.installed_exe_path = installer.get_exe_path()
            self.installation_message = None

        self._save_config()
        mark_first_run_complete()
        self.result = self.config
        self.window.destroy()

    def _save_config(self):
        """Save current configuration."""
        # Extract device index
        device_str = self.var_input_device.get()
        if device_str:
            try:
                self.config["input_device"] = int(device_str.split(":")[0])
            except ValueError:
                self.config["input_device"] = None

        self.config["hotkey"] = self.var_hotkey.get()
        self.config["model_size"] = self.var_model_size.get()

        model_path = self.var_model_path.get().strip()
        self.config["model_download_path"] = model_path if model_path else None

        # Store install type in config
        self.config["install_type"] = self.var_install_type.get()

        save_config(self.config)

    # ==================== Step Creators ====================

    def _create_welcome_step(self, parent):
        """Create the welcome step."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        # Big welcome message
        ttk.Label(
            frame,
            text="Welcome to Whisper Tray",
            style="Title.TLabel",
        ).pack(pady=(10, 5))

        ttk.Label(
            frame,
            text="Transform your voice into text with AI-powered transcription",
            style="Subtitle.TLabel",
        ).pack(pady=(0, 15))

        # Feature list - more compact
        features = [
            ("✓", "Runs 100% locally on your computer"),
            ("✓", "No internet required after setup"),
            ("✓", "Your audio never leaves your device"),
        ]
        for icon, text in features:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=icon, foreground=COLORS["success"], font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(row, text=text).pack(side=tk.LEFT)

        # What we'll do card - tighter padding
        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, pady=15)

        ttk.Label(card, text="Setup steps:", style="Card.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        steps = [
            "1. Select your microphone",
            "2. Set up your hotkey",
            "3. Download AI models",
            "4. Choose your default model",
        ]
        for step in steps:
            ttk.Label(card, text=step, style="Card.TLabel", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=1)

        # Show portable mode notice if applicable
        if is_portable_mode():
            tk.Label(
                frame,
                text="Portable Mode enabled",
                font=("Segoe UI", 9),
                bg=COLORS["bg"],
                fg=COLORS["success"],
            ).pack(pady=(10, 0))

        ttk.Label(
            frame,
            text="Click 'Next →' to begin",
            style="Dim.TLabel",
        ).pack(pady=(10, 0))

    def _create_install_type_step(self, parent):
        """Create the install type selection step."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        # Check if already installed or running from proper location
        already_installed = installer.is_running_from_install_location()
        running_from = installer.get_running_from_path()

        if already_installed:
            # Already installed - just show info and let them continue
            ttk.Label(
                frame,
                text="Already Installed",
                style="Title.TLabel",
            ).pack(pady=(10, 5))

            ttk.Label(
                frame,
                text="WhisperTray is already set up in this location.",
                style="Subtitle.TLabel",
            ).pack(pady=(0, 15))

            if installer.is_portable_install():
                self.var_install_type.set("portable")
                ttk.Label(
                    frame,
                    text="Running in Portable mode",
                    font=("Segoe UI", 10),
                    foreground=COLORS["success"],
                ).pack(pady=10)
            else:
                self.var_install_type.set("standard")
                ttk.Label(
                    frame,
                    text="Running as Standard installation",
                    font=("Segoe UI", 10),
                    foreground=COLORS["success"],
                ).pack(pady=10)

            ttk.Label(
                frame,
                text="Click 'Next' to continue with setup.",
                style="Dim.TLabel",
            ).pack(pady=(20, 0))
            return

        # Not installed yet - show install options
        ttk.Label(
            frame,
            text="Install Type",
            style="Title.TLabel",
        ).pack(pady=(10, 5))

        ttk.Label(
            frame,
            text=f"Currently running from: {running_from}",
            style="Dim.TLabel",
        ).pack(pady=(0, 10))

        # Standard Install option
        standard_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        standard_card.pack(fill=tk.X, pady=6)

        standard_rb = ttk.Radiobutton(
            standard_card,
            text="Standard Install (Recommended)",
            variable=self.var_install_type,
            value="standard",
            style="Card.TRadiobutton",
            command=self._on_install_type_change,
        )
        standard_rb.pack(anchor=tk.W)

        tk.Label(
            standard_card,
            text="• Installs to your AppData folder\n• Creates Start Menu shortcut\n• Models shared with other AI apps",
            font=("Segoe UI", 9),
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))

        # Startup checkbox (inside standard card)
        self.startup_check = ttk.Checkbutton(
            standard_card,
            text="Run at Windows startup",
            variable=self.var_run_at_startup,
        )
        self.startup_check.pack(anchor=tk.W, padx=(20, 0), pady=(8, 0))

        # Portable Install option
        portable_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        portable_card.pack(fill=tk.X, pady=6)

        portable_rb = ttk.Radiobutton(
            portable_card,
            text="Portable Install",
            variable=self.var_install_type,
            value="portable",
            style="Card.TRadiobutton",
            command=self._on_install_type_change,
        )
        portable_rb.pack(anchor=tk.W)

        tk.Label(
            portable_card,
            text="• Everything in one self-contained folder\n• Perfect for USB drives or multiple computers\n• No Start Menu or registry entries",
            font=("Segoe UI", 9),
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))

        # Portable path selection
        self.portable_path_frame = tk.Frame(portable_card, bg=COLORS["surface"])
        self.portable_path_frame.pack(fill=tk.X, padx=(20, 0), pady=(8, 0))

        tk.Label(
            self.portable_path_frame,
            text="Install to:",
            font=("Segoe UI", 9),
            bg=COLORS["surface"],
            fg=COLORS["text"],
        ).pack(side=tk.LEFT)

        self.portable_path_entry = ttk.Entry(
            self.portable_path_frame,
            textvariable=self.var_portable_path,
            width=35,
        )
        self.portable_path_entry.pack(side=tk.LEFT, padx=(5, 5))

        browse_btn = self._create_styled_button(
            self.portable_path_frame,
            "Browse...",
            self._browse_portable_path,
            style="secondary",
        )
        browse_btn.pack(side=tk.LEFT)

        # Set initial visibility
        self._on_install_type_change()

        # Note about what happens
        ttk.Label(
            frame,
            text="After setup, you can safely delete the file in Downloads.",
            style="Dim.TLabel",
        ).pack(pady=(15, 0))

    def _on_install_type_change(self):
        """Handle install type radio button change."""
        is_portable = self.var_install_type.get() == "portable"

        # Show/hide startup checkbox based on install type
        if hasattr(self, 'startup_check'):
            if is_portable:
                self.startup_check.configure(state="disabled")
            else:
                self.startup_check.configure(state="normal")

        # Show/hide portable path entry
        if hasattr(self, 'portable_path_frame'):
            if is_portable:
                self.portable_path_frame.pack(fill=tk.X, padx=(20, 0), pady=(8, 0))
            else:
                self.portable_path_frame.pack_forget()

    def _browse_portable_path(self):
        """Browse for portable install location."""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Select folder for portable install",
            initialdir=str(Path.home()),
        )
        if folder:
            # Suggest creating a WhisperTray subfolder
            portable_folder = Path(folder) / "WhisperTray"
            self.var_portable_path.set(str(portable_folder))

    def _create_mic_step(self, parent):
        """Create the microphone selection step."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Select your microphone and test it.",
            font=("", 10),
        ).pack(anchor=tk.W, pady=(10, 15))

        # Device dropdown
        ttk.Label(frame, text="Microphone:", font=("", 9, "bold")).pack(anchor=tk.W)

        # Full-width dropdown for long mic names
        device_combo = ttk.Combobox(
            frame,
            textvariable=self.var_input_device,
            values=self.audio_devices,
            state="readonly",
            width=70,
        )
        device_combo.pack(fill=tk.X, pady=(5, 5))

        self._create_styled_button(frame, "Refresh Devices", self._refresh_devices,
            style="primary", anchor=tk.W, pady=(0, 15))

        # Test recording
        ttk.Label(frame, text="Test your microphone:", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(10, 5)
        )

        test_frame = tk.Frame(frame, bg=COLORS["bg"])  # Use tk.Frame for high-DPI compat
        test_frame.pack(fill=tk.X)

        self.test_btn = self._create_styled_button(test_frame, "Record 3 Seconds",
            self._test_mic, style="primary", side=tk.LEFT)

        self.test_status = ttk.Label(test_frame, text="", font=("", 9))
        self.test_status.pack(side=tk.LEFT, padx=(15, 0))

        # Tips
        ttk.Label(
            frame,
            text=(
                "\nTips:\n"
                "- If you don't see your microphone, click 'Refresh'\n"
                "- Make sure your microphone is plugged in and enabled\n"
                "- Test your mic before continuing"
            ),
            font=("", 8),
            foreground="gray",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(20, 0))

    def _create_hotkey_step(self, parent):
        """Create the hotkey configuration step."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Set your recording hotkey.",
            font=("", 10),
        ).pack(anchor=tk.W, pady=(10, 15))

        ttk.Label(
            frame,
            text="Press this key combination to start/stop recording:",
            font=("", 9),
        ).pack(anchor=tk.W)

        # Current hotkey display
        hotkey_frame = tk.Frame(frame, bg=COLORS["bg"])  # Use tk.Frame for high-DPI compat
        hotkey_frame.pack(fill=tk.X, pady=15)

        self.hotkey_display = ttk.Label(
            hotkey_frame,
            textvariable=self.var_hotkey,
            font=("Segoe UI", 16, "bold"),
            background=COLORS["surface"],
            foreground=COLORS["primary"],
            padding=15,
        )
        self.hotkey_display.pack(side=tk.LEFT)

        self._create_styled_button(hotkey_frame, "Change Hotkey", self._capture_hotkey,
            style="primary", side=tk.LEFT, padx=(20, 0))

        # How to use
        ttk.Label(
            frame,
            text=(
                "\nHow to use:\n"
                "- Press the hotkey once to START recording\n"
                "- Speak clearly into your microphone\n"
                "- Press the hotkey again to STOP and transcribe\n"
                "- Press ESC while recording to cancel"
            ),
            font=("", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(20, 0))

        ttk.Label(
            frame,
            text=(
                "\nNote: If the hotkey doesn't work in some apps,\n"
                "they may be running as Administrator."
            ),
            font=("", 8),
            foreground="gray",
        ).pack(anchor=tk.W)

    def _create_model_step(self, parent):
        """Create the model selection step - shows only downloaded models."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Choose your default transcription model.",
            font=("", 10),
        ).pack(anchor=tk.W, pady=(10, 10))

        # Get downloaded models
        downloaded = get_downloaded_models()

        if not downloaded:
            ttk.Label(
                frame,
                text="No models downloaded yet.\n\nGo back and download at least one model,\nor skip setup to use the default.",
                font=("", 10),
                foreground="red",
            ).pack(pady=20)
            return

        ttk.Label(
            frame,
            text="Select from your downloaded models:",
            font=("", 9),
        ).pack(anchor=tk.W, pady=(0, 10))

        # Model selection - only show downloaded models
        for model_name in downloaded:
            if model_name not in MODEL_INFO:
                continue
            info = MODEL_INFO[model_name]

            model_frame = ttk.Frame(frame)
            model_frame.pack(fill=tk.X, pady=3)

            # Radio button
            rb_text = f"{model_name.capitalize()}"
            if info.get("recommended"):
                rb_text += " (Recommended)"

            rb = ttk.Radiobutton(
                model_frame,
                text=rb_text,
                variable=self.var_model_size,
                value=model_name,
            )
            rb.pack(side=tk.LEFT)

            # Info label
            info_text = f"  {info['speed']} | {info['accuracy']} | {info['size']}"
            ttk.Label(model_frame, text=info_text, font=("", 8), foreground="gray").pack(
                side=tk.LEFT
            )

        # Make sure selection is valid
        if self.var_model_size.get() not in downloaded:
            self.var_model_size.set(downloaded[0])

        ttk.Label(
            frame,
            text="\nYou can download more models later from Settings.",
            font=("", 8),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(20, 0))

    def _create_download_step(self, parent):
        """Create the model download step with checkboxes."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        # Model path first
        ttk.Label(frame, text="Model download location:", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(2, 3)
        )

        path_frame = tk.Frame(frame, bg=COLORS["bg"])  # Use tk.Frame for high-DPI compat
        path_frame.pack(fill=tk.X)

        path_entry = ttk.Entry(path_frame, textvariable=self.var_model_path, width=40)
        path_entry.pack(side=tk.LEFT)

        self._create_styled_button(path_frame, "Browse...", self._browse_path,
            style="primary", side=tk.LEFT, padx=(5, 0))

        # Show appropriate default path based on mode
        if is_portable_mode():
            default_path = get_app_root() / "models"
        else:
            default_path = get_default_model_path()

        # Pre-fill with default path if not already set
        if not self.var_model_path.get():
            self.var_model_path.set(str(default_path))

        ttk.Label(
            frame,
            text=f"Default: {default_path}",
            font=("", 7),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Separator(frame).pack(fill=tk.X, pady=3)

        ttk.Label(
            frame,
            text="Select models to download:",
            font=("", 9),
        ).pack(anchor=tk.W, pady=(5, 3))

        # Model checkboxes - compact layout
        self.download_checkboxes = {}
        already_downloaded = get_downloaded_models()

        for model_name, info in MODEL_INFO.items():
            # Checkbox with size and status inline
            cb_text = f"{model_name.capitalize()} ({info['size']})"
            if info.get("recommended"):
                cb_text += " *"
            if model_name in already_downloaded:
                cb_text += " ✓"

            cb = ttk.Checkbutton(
                frame,
                text=cb_text,
                variable=self.var_download_models[model_name],
            )
            cb.pack(anchor=tk.W, pady=1)

            self.download_checkboxes[model_name] = cb

        ttk.Label(
            frame,
            text="* Recommended   ✓ Already downloaded",
            font=("", 7),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(3, 0))

        # Progress area
        ttk.Separator(frame).pack(fill=tk.X, pady=8)

        self.progress_frame = ttk.Frame(frame)
        self.progress_frame.pack(fill=tk.X)

        self.progress_label = ttk.Label(self.progress_frame, text="", font=("", 9))
        self.progress_label.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="indeterminate", length=400)

    def _create_complete_step(self, parent):
        """Create the completion step."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Setup Complete!",
            style="Title.TLabel",
        ).pack(pady=(10, 8))

        # Settings summary - full mic name
        mic_name = self.var_input_device.get()

        ttk.Label(frame, text=f"Mic: {mic_name}", font=("Segoe UI", 9), wraplength=550).pack(pady=(5, 2))
        ttk.Label(frame, text=f"Hotkey: {self.var_hotkey.get()}  |  Model: {self.var_model_size.get()}", font=("Segoe UI", 9)).pack(pady=2)

        ttk.Label(
            frame,
            text=f"Press {self.var_hotkey.get()} to start recording, press again to transcribe.",
            font=("Segoe UI", 10),
        ).pack(pady=8)

        # Storage info card
        storage_frame = ttk.Frame(frame, style="Card.TFrame", padding=10)
        storage_frame.pack(fill=tk.X, pady=8)

        tk.Label(
            storage_frame,
            text="Storage Locations:",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["surface"],
            fg=COLORS["text"],
        ).pack(anchor=tk.W)

        # Get actual paths
        import os
        hf_cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
        if not hf_cache:
            hf_cache = str(Path.home() / ".cache" / "huggingface" / "hub")

        config_dir = get_config_dir()

        tk.Label(
            storage_frame,
            text=f"Models: {hf_cache}",
            font=("Segoe UI", 8),
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            wraplength=550,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(3, 0))

        tk.Label(
            storage_frame,
            text=f"Settings & History: {config_dir}",
            font=("Segoe UI", 8),
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            wraplength=550,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 0))

        # Tray icon tip
        tip_frame = ttk.Frame(frame, style="Card.TFrame", padding=10)
        tip_frame.pack(fill=tk.X, pady=8)

        if is_portable_mode():
            tk.Label(
                tip_frame,
                text="Portable Mode - config stored in app folder",
                font=("Segoe UI", 9, "bold"),
                bg=COLORS["surface"],
                fg=COLORS["text"],
            ).pack(anchor=tk.W)
        else:
            tk.Label(
                tip_frame,
                text="Tip: Pin the Tray Icon",
                font=("Segoe UI", 9, "bold"),
                bg=COLORS["surface"],
                fg=COLORS["text"],
            ).pack(anchor=tk.W)
            tk.Label(
                tip_frame,
                text="Look for the green icon in system tray (bottom-right).\nClick ^ to find hidden icons, then drag to taskbar.",
                font=("Segoe UI", 8),
                bg=COLORS["surface"],
                fg=COLORS["text_secondary"],
            ).pack(anchor=tk.W, pady=(3, 0))

    # ==================== Helper Methods ====================

    def _refresh_devices(self):
        """Refresh audio device list."""
        self.audio_devices = self._get_audio_devices()
        # Refresh the current step
        self._show_step(self.current_step)

    def _test_mic(self):
        """Test microphone recording."""
        self.test_btn.configure(state="disabled")
        self.test_status.configure(text="Recording...", foreground="red")

        def do_test():
            try:
                device_str = self.var_input_device.get()
                device_idx = int(device_str.split(":")[0]) if device_str else None

                samplerate = 16000
                duration = 3
                audio = sd.rec(
                    int(duration * samplerate),
                    samplerate=samplerate,
                    channels=1,
                    device=device_idx,
                )
                sd.wait()

                self.window.after(
                    0, lambda: self.test_status.configure(text="Playing back...", foreground="blue")
                )

                sd.play(audio, samplerate=samplerate)
                sd.wait()

                self.window.after(
                    0, lambda: self.test_status.configure(text="Test complete!", foreground="green")
                )
            except Exception as e:
                self.window.after(
                    0,
                    lambda: self.test_status.configure(
                        text=f"Error: {str(e)[:40]}", foreground="red"
                    ),
                )
            finally:
                self.window.after(0, lambda: self.test_btn.configure(state="normal"))

        threading.Thread(target=do_test, daemon=True).start()

    def _capture_hotkey(self):
        """Capture a new hotkey."""
        capture_window = tk.Toplevel(self.window)
        capture_window.title("Press Hotkey")
        capture_window.geometry("350x120")
        capture_window.transient(self.window)
        capture_window.grab_set()
        capture_window.configure(bg=COLORS["bg"])

        x = self.window.winfo_x() + (self.window.winfo_width() - 350) // 2
        y = self.window.winfo_y() + (self.window.winfo_height() - 120) // 2
        capture_window.geometry(f"+{x}+{y}")

        # Match wizard styling
        ttk.Label(
            capture_window,
            text="Press your desired hotkey...",
            font=("Segoe UI", 12),
            background=COLORS["bg"],
            foreground=COLORS["text"],
        ).pack(pady=(35, 10))

        ttk.Label(
            capture_window,
            text="(e.g., Ctrl+Alt+Space)",
            font=("Segoe UI", 9),
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
        ).pack()

        captured_keys = set()

        def on_key_press(event):
            key = event.keysym.lower()
            if key in ("control_l", "control_r"):
                captured_keys.add("ctrl")
            elif key in ("alt_l", "alt_r"):
                captured_keys.add("alt")
            elif key in ("shift_l", "shift_r"):
                captured_keys.add("shift")
            else:
                captured_keys.add(key)

        def on_key_release(event):
            if len(captured_keys) >= 2:
                modifiers = []
                key = None
                for k in captured_keys:
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

    def _browse_path(self):
        """Browse for model download path."""
        path = filedialog.askdirectory(
            title="Select Model Download Location",
            initialdir=self.var_model_path.get() or str(get_default_model_path()),
        )
        if path:
            self.var_model_path.set(path)

    def _start_downloads(self):
        """Start downloading selected models."""
        # Get selected models
        models_to_download = [
            name for name, var in self.var_download_models.items() if var.get()
        ]

        if not models_to_download:
            # No models selected, skip to next step
            self._show_step(self.current_step + 1)
            return

        # Disable UI during download
        self.next_btn.configure(state="disabled")
        self.back_btn.configure(state="disabled")
        self.skip_btn.configure(state="disabled")

        for cb in self.download_checkboxes.values():
            cb.configure(state="disabled")

        # Show progress bar in indeterminate mode (animated)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
        self.progress_bar.start(10)

        # Track download state
        self.download_cancelled = False
        self.download_dots = 0

        def parse_size_mb(size_str):
            """Parse size string like '~244 MB' or '~1.5 GB' to MB."""
            try:
                size_str = size_str.replace("~", "").strip()
                if "GB" in size_str:
                    return float(size_str.replace("GB", "").strip()) * 1024
                elif "MB" in size_str:
                    return float(size_str.replace("MB", "").strip())
            except Exception:
                pass
            return 100  # Default fallback

        def update_dots():
            """Animate dots to show download is active."""
            if self.download_cancelled:
                return
            self.download_dots = (self.download_dots + 1) % 4
            dots = "." * self.download_dots
            current_text = self.progress_label.cget("text")
            # Update dots at end of message
            if current_text:
                base = current_text.rstrip(".")
                self.progress_label.configure(text=f"{base}{dots}")
            self.window.after(500, update_dots)

        def download_models():
            try:
                debug_log("download_models() started")
                custom_path = self.var_model_path.get().strip()
                debug_log(f"Custom path: {custom_path}")

                for i, model_name in enumerate(models_to_download):
                    debug_log(f"Starting download of {model_name} ({i+1}/{len(models_to_download)})")

                    # Get expected size for this model
                    model_info = MODEL_INFO.get(model_name, {})
                    expected_mb = parse_size_mb(model_info.get("size", "100 MB"))

                    self.window.after(
                        0,
                        lambda m=model_name, idx=i, exp=expected_mb, total=len(models_to_download): self.progress_label.configure(
                            text=f"Downloading {m} ({idx + 1}/{total}) ~{exp:.0f} MB"
                        ),
                    )

                    # Get custom path if set
                    download_dir_path = custom_path if custom_path else None

                    # Import and load model (triggers download)
                    try:
                        # Update status before starting
                        self.window.after(
                            0,
                            lambda m=model_name: self.progress_label.configure(
                                text=f"Loading {m} (this may take a while)..."
                            ),
                        )

                        # Set environment variables BEFORE importing faster_whisper
                        if download_dir_path:
                            debug_log(f"Setting HF_HOME to: {download_dir_path}")
                            os.environ["HF_HOME"] = download_dir_path
                            os.environ["HF_HUB_CACHE"] = download_dir_path
                            os.environ["HUGGINGFACE_HUB_CACHE"] = download_dir_path

                        # Disable tqdm progress bars - they can hang in windowed mode
                        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
                        # Disable symlink warnings
                        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

                        debug_log("Importing faster_whisper...")
                        from faster_whisper import WhisperModel
                        debug_log("faster_whisper imported successfully")

                        # Load model - this downloads if not cached
                        # Use CPU directly - CUDA detection can hang on non-CUDA systems
                        debug_log(f"Loading model {model_name} with CPU/int8...")
                        model = WhisperModel(model_name, device="cpu", compute_type="int8")
                        debug_log(f"Model {model_name} loaded successfully")
                        del model  # Release memory
                        debug_log(f"Model {model_name} released from memory")

                        mark_model_downloaded(model_name)

                        # Show model complete
                        self.window.after(
                            0,
                            lambda m=model_name: self.progress_label.configure(
                                text=f"✓ {m} downloaded!"
                            ),
                        )

                    except Exception as e:
                        self.window.after(
                            0,
                            lambda m=model_name, err=str(e): messagebox.showwarning(
                                "Download Warning",
                                f"Could not download {m}: {err}\n\nYou can try again later.",
                            ),
                        )

                # Done
                self.download_cancelled = True
                self.window.after(0, self._download_complete)

            except Exception as e:
                self.download_cancelled = True
                self.window.after(
                    0,
                    lambda: messagebox.showerror("Download Error", f"Error: {str(e)}"),
                )
                self.window.after(0, self._download_complete)

        # Start animated dots
        self.window.after(500, update_dots)
        threading.Thread(target=download_models, daemon=True).start()

    def _download_complete(self):
        """Handle download completion."""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.progress_label.configure(text="Downloads complete!")

        # Re-enable UI
        self.next_btn.configure(state="normal")
        self.back_btn.configure(state="normal")

        # Move to next step
        self._show_step(self.current_step + 1)

    def run(self) -> Optional[Dict[str, Any]]:
        """Run the wizard.

        Returns:
            Configuration dict if completed, None if cancelled.
        """
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.mainloop()
        return self.result

    def _on_close(self):
        """Handle window close."""
        if messagebox.askyesno(
            "Cancel Setup",
            "Are you sure you want to cancel setup?\n\nWhisper Dictation will not start.",
        ):
            self.result = None
            self.window.destroy()


def run_first_run_wizard() -> Optional[Dict[str, Any]]:
    """Run the first-run wizard.

    Returns:
        Configuration dict if completed, None if cancelled.
    """
    wizard = FirstRunWizard()
    return wizard.run()


if __name__ == "__main__":
    # Test the wizard standalone
    result = run_first_run_wizard()
    if result:
        print("Setup complete:", result)
    else:
        print("Setup cancelled")
