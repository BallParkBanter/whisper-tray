"""
Real-time transcription window for Whisper Tray.
Shows transcriptions as they happen and accumulates until manually closed.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from typing import Optional, Callable
import threading


class TranscriptionWindow:
    """Floating window that shows transcriptions in real-time."""

    def __init__(self, always_on_top: bool = True, on_close: Optional[Callable] = None):
        """Initialize the transcription window.

        Args:
            always_on_top: Keep window above other windows
            on_close: Callback when window is closed
        """
        self.on_close_callback = on_close
        self.always_on_top = always_on_top
        self.window = None
        self.text_area = None
        self.status_label = None
        self.is_open = False
        self._lock = threading.Lock()

    def show(self):
        """Show the transcription window."""
        if self.is_open and self.window:
            # Already open, just bring to front
            try:
                self.window.lift()
                self.window.focus_force()
            except tk.TclError:
                pass
            return

        self._create_window()

    def _create_window(self):
        """Create the window UI."""
        self.window = tk.Tk()
        self.window.title("Whisper Transcription")
        self.window.geometry("500x350")
        self.window.minsize(400, 200)

        # Set always on top
        if self.always_on_top:
            self.window.attributes('-topmost', True)

        # Position in bottom-right corner
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = screen_width - 520
        y = screen_height - 450
        self.window.geometry(f"+{x}+{y}")

        # Status bar at top
        status_frame = ttk.Frame(self.window)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self.status_label = ttk.Label(
            status_frame,
            text="Ready",
            font=("", 9),
            foreground="gray"
        )
        self.status_label.pack(side=tk.LEFT)

        # Always on top toggle
        self.topmost_var = tk.BooleanVar(value=self.always_on_top)
        ttk.Checkbutton(
            status_frame,
            text="Always on top",
            variable=self.topmost_var,
            command=self._toggle_topmost
        ).pack(side=tk.RIGHT)

        # Scrolled text area for transcriptions
        self.text_area = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=10,
            pady=10
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.text_area.configure(state='disabled')  # Read-only

        # Configure tags for styling
        self.text_area.tag_configure("timestamp", foreground="#666666")
        self.text_area.tag_configure("recording", foreground="#d32f2f", font=("Consolas", 10, "bold"))
        self.text_area.tag_configure("transcribing", foreground="#f9a825", font=("Consolas", 10, "italic"))
        self.text_area.tag_configure("text", foreground="#000000")

        # Button frame at bottom
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Copy All", command=self._copy_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Close", command=self._close).pack(side=tk.RIGHT, padx=2)

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self.is_open = True

    def _toggle_topmost(self):
        """Toggle always-on-top setting."""
        self.always_on_top = self.topmost_var.get()
        if self.window:
            self.window.attributes('-topmost', self.always_on_top)

    def _clear(self):
        """Clear all transcriptions from the window."""
        if self.text_area:
            self.text_area.configure(state='normal')
            self.text_area.delete(1.0, tk.END)
            self.text_area.configure(state='disabled')

    def _copy_all(self):
        """Copy all transcriptions to clipboard."""
        if self.text_area:
            text = self.text_area.get(1.0, tk.END).strip()
            if text:
                self.window.clipboard_clear()
                self.window.clipboard_append(text)
                self.set_status("Copied to clipboard!")

    def _close(self):
        """Close the window."""
        self.is_open = False
        if self.window:
            self.window.destroy()
            self.window = None
        if self.on_close_callback:
            self.on_close_callback()

    def set_status(self, status: str):
        """Update the status label."""
        if self.status_label and self.window:
            try:
                self.window.after(0, lambda: self.status_label.configure(text=status))
            except tk.TclError:
                pass

    def show_recording(self):
        """Show recording indicator."""
        self._append_text("● Recording...", tag="recording", add_timestamp=True)
        self.set_status("Recording...")

    def show_transcribing(self):
        """Show transcribing indicator."""
        # Remove the recording indicator and replace with transcribing
        self._remove_last_line()
        self._append_text("◐ Transcribing...", tag="transcribing", add_timestamp=True)
        self.set_status("Transcribing...")

    def show_transcription(self, text: str):
        """Show a completed transcription.

        Args:
            text: The transcribed text
        """
        # Remove the transcribing indicator
        self._remove_last_line()

        # Add the transcription with timestamp
        self._append_text(text, tag="text", add_timestamp=True)
        self.set_status("Ready")

        # Scroll to bottom
        if self.text_area:
            self.text_area.see(tk.END)

    def show_cancelled(self):
        """Show that recording was cancelled."""
        self._remove_last_line()
        self._append_text("(cancelled)", tag="timestamp", add_timestamp=True)
        self.set_status("Cancelled")

    def show_error(self, message: str):
        """Show an error message."""
        self._remove_last_line()
        self._append_text(f"Error: {message}", tag="recording", add_timestamp=True)
        self.set_status("Error")

    def _append_text(self, text: str, tag: str = "text", add_timestamp: bool = False):
        """Append text to the text area.

        Args:
            text: Text to append
            tag: Tag for styling
            add_timestamp: Whether to add a timestamp prefix
        """
        if not self.text_area or not self.window:
            return

        try:
            self.text_area.configure(state='normal')

            if add_timestamp:
                timestamp = datetime.now().strftime("[%H:%M:%S] ")
                self.text_area.insert(tk.END, timestamp, "timestamp")

            self.text_area.insert(tk.END, text + "\n", tag)
            self.text_area.configure(state='disabled')
            self.text_area.see(tk.END)
        except tk.TclError:
            pass

    def _remove_last_line(self):
        """Remove the last line from the text area."""
        if not self.text_area or not self.window:
            return

        try:
            self.text_area.configure(state='normal')
            # Get the last line
            last_line_start = self.text_area.index("end-2l linestart")
            last_line_end = self.text_area.index("end-1l lineend")
            content = self.text_area.get(last_line_start, last_line_end).strip()

            # Only remove if it's a status line (Recording/Transcribing/cancelled)
            if "Recording" in content or "Transcribing" in content or "cancelled" in content:
                self.text_area.delete(last_line_start, tk.END)

            self.text_area.configure(state='disabled')
        except tk.TclError:
            pass

    def run(self):
        """Run the window main loop (blocking)."""
        if self.window:
            self.window.mainloop()

    def update(self):
        """Process pending window events (non-blocking)."""
        if self.window:
            try:
                self.window.update()
            except tk.TclError:
                pass


class TranscriptionWindowManager:
    """Manages the transcription window in a separate thread."""

    def __init__(self):
        self.window: Optional[TranscriptionWindow] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.enabled = False
        self.always_on_top = True

    def set_enabled(self, enabled: bool):
        """Enable or disable the transcription window."""
        self.enabled = enabled
        if not enabled and self.window:
            self.close()

    def set_always_on_top(self, value: bool):
        """Set whether window should always be on top."""
        self.always_on_top = value
        if self.window:
            self.window.always_on_top = value

    def show(self):
        """Show the transcription window."""
        if not self.enabled:
            return

        with self._lock:
            if self.window and self.window.is_open:
                return

            # Create window in main thread context
            self.window = TranscriptionWindow(
                always_on_top=self.always_on_top,
                on_close=self._on_window_close
            )
            self.window.show()

    def close(self):
        """Close the transcription window."""
        with self._lock:
            if self.window:
                self.window._close()
                self.window = None

    def _on_window_close(self):
        """Handle window close."""
        with self._lock:
            self.window = None

    def on_recording_start(self):
        """Called when recording starts."""
        if not self.enabled:
            return
        self.show()
        if self.window:
            self.window.show_recording()

    def on_transcribing(self):
        """Called when transcription starts."""
        if self.window:
            self.window.show_transcribing()

    def on_transcription_complete(self, text: str):
        """Called when transcription is complete."""
        if self.window:
            self.window.show_transcription(text)

    def on_recording_cancelled(self):
        """Called when recording is cancelled."""
        if self.window:
            self.window.show_cancelled()

    def on_error(self, message: str):
        """Called when an error occurs."""
        if self.window:
            self.window.show_error(message)

    def update(self):
        """Update the window (call from main thread)."""
        if self.window:
            self.window.update()


# Global instance
_manager: Optional[TranscriptionWindowManager] = None


def get_transcription_window_manager() -> TranscriptionWindowManager:
    """Get the global transcription window manager."""
    global _manager
    if _manager is None:
        _manager = TranscriptionWindowManager()
    return _manager
