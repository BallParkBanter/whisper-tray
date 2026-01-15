# <img src="icons/mic_icon.png" width="32" align="center" style="vertical-align: middle;"> WhisperTray

Voice-to-text for Windows. Press a hotkey, talk, and your words appear wherever your cursor is.

**100% local.**  Your voice never leaves your computer. No accounts, no subscriptions, no internet required after setup.

## ✨ What It Does

1. Press `Ctrl+Alt+Space`
2. Talk
3. Press `Ctrl+Alt+Space` again
4. Text appears in whatever app you're using

Works everywhere: Word, email, Slack, VS Code, terminals, browser text boxes — anywhere you can type.

## 📥 Getting Started

1. **Download** `WhisperTray.exe` from [Releases](../../releases)
2. **Run it:** First-run wizard walks you through setup
3. **Download a model:** Start with "small" for best balance of speed and accuracy
4. **Done:** Look for the green microphone in your system tray

No installation needed. No admin rights required. Just run the EXE.

## 🎯 Quick Tips

### Pin the tray icon
The icon hides by default. Make it always visible:
1. Click the `^` arrow in your system tray (bottom-right)
2. Drag the WhisperTray icon onto your taskbar

### For terminals
Regular paste (`Ctrl+V`) doesn't work in some terminals. Enable **Use typing mode** in Settings → Behavior. It types the text character-by-character instead.

### Cursor moves after transcription
When text is pasted, your cursor ends up at the end of the transcribed text. Plan accordingly if you're inserting text mid-sentence.

## 🧠 Models

Pick based on your needs:

| Model | Size | Speed | When to use |
|-------|------|-------|-------------|
| tiny | ~75 MB | ⚡ Fastest | Quick notes, testing |
| base | ~145 MB | ⚡ Fast | Light use |
| **small** | **~465 MB** | **Balanced** | **Most people should start here** |
| medium | ~1.5 GB | Slower | Need better accuracy |
| turbo | ~1.6 GB | Fast | Best bang for buck (nearly as good as large, 8x faster) |
| large-v3 | ~3.0 GB | Slowest | Maximum accuracy |

Have an NVIDIA GPU? WhisperTray uses it automatically. Big speed boost.

## ⌨️ Shortcuts

| Key | What it does |
|-----|--------------|
| `Ctrl+Alt+Space` | Start/stop recording |
| `Esc` | Cancel recording |

Change the hotkey in Settings → General if it conflicts with something else.

## 🔧 Settings

Right-click the tray icon → **Settings**

**General:** Model, language, hotkey
**Audio:** Microphone selection, test recording
**Behavior:** Send Enter after paste, keep clipboard, typing mode
**Output:** Notifications, logging, history length
**Models:** Download more models, delete unused ones
**About:** Version info, links

## 📁 Where Things Live

**Settings & logs:** `%APPDATA%\WhisperTray\`
**Models:** `%USERPROFILE%\.cache\huggingface\hub\`

Want portable mode? Create a file named `portable.txt` next to the EXE. Settings move to `.\config\` but models stay in the HuggingFace cache (can't be changed).

## ❓ Troubleshooting

### Nothing happens when I press the hotkey
- Another app might be using that shortcut. Change it in Settings → General.
- Check that WhisperTray is running (green icon in tray).

### Microphone not detected
- Windows Settings → Privacy → Microphone — make sure apps can access it
- Try Settings → Audio → Refresh Devices

### Text doesn't paste
- Some apps block automated paste. Enable **Use typing mode** in Settings → Behavior.
- Or just press `Ctrl+V` manually after the transcription completes.

### Transcription is slow
- Use a smaller model (tiny or base)
- If you have an NVIDIA GPU, it's already being used automatically
- Close other GPU-heavy apps

### "Already running" message
Only one instance allowed. Check your system tray for the existing icon.

## 🗑️ Uninstall / Reset

Download `CleanupWhisperTray.bat` from [Releases](../../releases) and double-click it.

**What it removes:**
- Config files and settings
- Start Menu and Startup shortcuts
- App installation folders
- PyInstaller temp files

**What it keeps:**
- Your downloaded Whisper models (they're large and reusable)

Use this to completely uninstall, or to reset for a fresh install (re-run the setup wizard).

## 🏗️ Building From Source

```powershell
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Build
.venv\Scripts\pyinstaller whisper_tray.spec --clean
# Output: dist\WhisperTray.exe
```

## 📄 License

MIT. Do whatever you want with it.

## 🙏 Thanks To

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — The fast Whisper implementation that makes this possible
- [OpenAI Whisper](https://github.com/openai/whisper) — The original speech recognition model
- [pystray](https://github.com/moses-palmer/pystray) — System tray functionality
