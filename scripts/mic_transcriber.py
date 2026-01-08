#!/usr/bin/env python3
import argparse
import os
import sys
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import tkinter as tk
from faster_whisper import WhisperModel


class Recorder:
    def __init__(self, samplerate: int):
        self.samplerate = samplerate
        self._stream = None
        self._frames = []
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time, status):
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


class TranscriberApp:
    def __init__(self, args):
        self.args = args
        self.recorder = Recorder(args.samplerate)
        self.model = WhisperModel(
            args.model_size,
            device=args.device,
            compute_type=args.compute_type,
        )

        self.root = tk.Tk()
        self.root.title("WSL Whisper Button")
        self.root.geometry("260x140")

        self.button = tk.Button(self.root, text="Start recording", command=self.toggle_recording)
        self.button.pack(pady=12)

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(self.root, textvariable=self.status_var, wraplength=220, justify="center")
        self.status_label.pack(pady=6)
        self._set_status("Idle")

        self.recording = False
        self.processing = False

    def _set_status(self, message: str):
        self.status_var.set(message)

    def toggle_recording(self):
        if self.processing:
            return
        if not self.recording:
            try:
                self.recorder.start()
            except Exception as exc:
                self._set_status(f"Record error: {exc}")
                return
            self.recording = True
            self.button.configure(text="Stop and transcribe")
            self._set_status("Recording… click again to finish")
        else:
            audio = self.recorder.stop()
            self.recording = False
            self.button.configure(text="Start recording")
            if audio is None:
                self._set_status("No audio captured, try again")
                return
            self.processing = True
            self._set_status("Transcribing…")
            thread = threading.Thread(target=self._transcribe_async, args=(audio,), daemon=True)
            thread.start()

    def _transcribe_async(self, audio: np.ndarray):
        try:
            segments, info = self.model.transcribe(
                audio,
                language=self.args.language,
                beam_size=self.args.beam_size,
            )
            text = "".join(segment.text for segment in segments).strip()
            if not text:
                self.root.after(0, lambda: self._set_status("Transcription empty"))
            else:
                self.root.after(0, lambda: self._after_transcription(text))
        except Exception as exc:
            self.root.after(0, lambda: self._set_status(f"Transcribe error: {exc}"))
        finally:
            self.processing = False

    def _after_transcription(self, text: str):
        if self.args.echo:
            print(text)
        self._set_status("Sending to terminal")
        try:
            inject_text(
                text,
                self.args.tty_path,
                send_enter=self.args.send_enter,
                trailing_space=self.args.trailing_space,
            )
        except Exception as exc:
            self._set_status(f"TTY write failed: {exc}")
            return
        self._set_status("Idle")

    def run(self):
        self.root.mainloop()


def inject_text(text: str, tty_path: Path, *, send_enter: bool, trailing_space: bool):
    payload = text
    if trailing_space and not payload.endswith(" "):
        payload += " "
    if send_enter and not payload.endswith("\n"):
        payload += "\n"
    elif not send_enter:
        payload = payload.replace("\n", " ")
    fd = os.open(tty_path, os.O_WRONLY)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)


def resolve_tty(override: Optional[str]):
    if override:
        return Path(override)
    env_tty = os.environ.get("TARGET_TTY")
    if env_tty:
        return Path(env_tty)
    tty = os.environ.get("TTY")
    if tty:
        return Path(tty)
    tty_cmd = None
    try:
        import subprocess

        tty_cmd = subprocess.check_output(["tty"], text=True).strip()
    except Exception:
        pass
    if tty_cmd:
        return Path(tty_cmd)
    raise RuntimeError("Unable to determine target TTY. Use --tty to specify one.")


def parse_args():
    parser = argparse.ArgumentParser(description="Record voice, transcribe with Whisper, and write into a terminal TTY.")
    parser.add_argument("--model-size", default="small", help="Whisper model to load (e.g. tiny, base, small, medium, large-v2).")
    parser.add_argument("--device", default="auto", help="Inference device (auto, cpu, cuda).")
    parser.add_argument("--compute-type", default="int8", help="Quantization to use with faster-whisper.")
    parser.add_argument("--samplerate", type=int, default=16000, help="Recording samplerate.")
    parser.add_argument("--language", default="en", help="Language hint for Whisper.")
    parser.add_argument("--beam-size", type=int, default=1, help="Beam size for decoding.")
    parser.add_argument("--tty", dest="tty", help="Explicit /dev/pts/N to send text to.")
    parser.add_argument("--send-enter", action="store_true", help="Append newline so the command is submitted immediately.")
    parser.add_argument(
        "--no-trailing-space",
        dest="trailing_space",
        action="store_false",
        default=True,
        help="Disable automatic trailing space.",
    )
    parser.add_argument("--echo", action="store_true", help="Print transcriptions to stdout as well.")
    args = parser.parse_args()
    args.tty_path = resolve_tty(args.tty)
    if args.device == "auto":
        args.device = None
    if not args.tty_path.exists():
        raise FileNotFoundError(f"TTY {args.tty_path} does not exist.")
    return args


def ensure_portaudio():
    try:
        sd.query_devices()
    except Exception as exc:
        raise RuntimeError(
            "PortAudio is not configured. Install portaudio and ensure microphone access in WSL."
        ) from exc


def main():
    args = parse_args()
    ensure_portaudio()
    app = TranscriberApp(args)
    app.run()


if __name__ == "__main__":
    main()
