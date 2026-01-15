# Changelog

All notable changes to Whisper Tray are documented in this file.

## [2.0.15] - 2026-01-14

### Bug Fixes

#### Single-Instance Check Fixed
- **Fixed multiple instances being able to run simultaneously**
- Root cause: Windows mutex handle was stored in a local variable that Python could garbage collect
- Fix: Store mutex handle at module level so it persists for the lifetime of the process
- This was causing the app to appear unresponsive when clicking the Start menu icon (duplicate processes)

## [2.0.14] - 2026-01-07

### Bug Fixes

#### First Transcription Not Auto-Pasting Fixed
- **Fixed first transcription failing to auto-paste** after app startup
- Root cause: `pyautogui` wasn't fully initialized on Windows before first use
- Fix: Added warm-up call (`pyautogui.position()`) during app initialization
- Subsequent transcriptions were always working; now first one works too

### New Features

#### About Tab Added to Settings
- **Added "About" tab** in Settings with version number and links
- Shows WhisperTray version (now displayed in the app!)
- "Why I Built This" section explaining the motivation
- Quick links to GitHub repository and latest releases
- Privacy reminder: "100% local - your voice never leaves your computer"

### Improvements

#### Cleanup Script Made More Robust
- **Fixed cleanup script not stopping WhisperTray** before deleting files
- Now uses wildcard matching to find all WhisperTray-related processes (handles versioned installer names)
- Waits 2 seconds after killing processes for file locks to release
- Shows clear error messages if deletion fails instead of failing silently
- Fixed step numbering consistency (now correctly shows [1/7] through [7/7])

## [2.0.13] - 2026-01-07

### Bug Fixes

#### PortAudio DLL Missing from Bundle Fixed
- **Fixed "PortAudio library not found" crash** on startup
- Added `collect_data_files('sounddevice')` to spec file to include PortAudio DLL
- Previous versions may have worked due to leftover temp files from earlier builds

### Improvements

#### Enhanced Cleanup Script
- Updated `CleanupWhisperTray.ps1` to clear PyInstaller temp directories (`_MEI*` folders in `%TEMP%`)
- More thorough cleanup ensures fresh install testing works reliably

### Known Behavior

#### Two Processes in Task Manager (Normal)
- PyInstaller `--onefile` bundles show **two processes** in Task Manager - this is normal:
  1. **Bootloader process** - Extracts bundle to temp directory
  2. **Python process** - Runs the actual WhisperTray application
- Both processes are required for the app to function correctly
- When you Quit, both processes terminate together

### Future Enhancements (Planned)
- Detect already-downloaded models during install wizard
- Currently, models in HuggingFace cache aren't detected until download is attempted

## [2.0.12] - 2026-01-07

### Bug Fixes

#### Quit Not Exiting Fixed
- **Fixed Quit not actually stopping the process** - added `os._exit(0)` to `stop()` method
- Added `multiprocessing.freeze_support()` for PyInstaller compatibility
- Quit from tray menu now fully terminates the application

## [2.0.11] - 2026-01-07

### Bug Fixes

#### Model Change Not Persisting After Restart Fixed
- **Fixed model change being lost** after clicking "Restart now"
- Root cause: `os._exit(0)` was terminating before config file fully flushed to disk
- Fix: Force save config explicitly before showing restart dialog, add 0.5s delay before exit
- Model selection now correctly persists through restart

## [2.0.10] - 2026-01-07

### Improvements

#### Better Restart UX for Model Changes
- **Improved model change restart prompt** - now shows clear dialog instead of vague toast
- Dialog asks "Restart now?" with Yes/No buttons
- Clicking Yes automatically restarts WhisperTray with new model
- No more confusion about how to restart the app

## [2.0.9] - 2026-01-07

### Bug Fixes

#### Downloaded Models Not Persisting Fixed
- **Fixed downloaded models being forgotten** after clicking Save in Settings
- Root cause: `_save()` was using stale config copy from when Settings opened
- When models were downloaded, `mark_model_downloaded()` saved to disk, but Save button overwrote it with old data
- Fix: `_save()` now re-loads config from disk before applying UI changes, preserving downloaded_models

## [2.0.8] - 2026-01-07

### Bug Fixes

#### Settings Model Download Fixed
- **Fixed model download failure** in Settings → Models tab
- Root cause: Was trying to spawn external Python subprocess (not available on fresh installs)
- Fix: Now uses bundled `faster_whisper` directly, same approach as the setup wizard
- Downloads now work without needing Python installed on the system

## [2.0.7] - 2026-01-07

### Bug Fixes

#### Settings Window Improvements
- **Fixed gray title bar** in Settings window - now matches dark theme like the wizard
- **Fixed "Refresh Devices" button cutoff** on Audio tab - reduced combo width, shortened button text
- **Fixed model list cutoff** on Models tab - increased window height from 680 to 780 pixels
- **Fixed notebook reference bug** - "Download more models" link now correctly switches to Models tab

## [2.0.6] - 2026-01-06

### Bug Fixes

#### Button Squishing Fix
- **Fixed button squishing** on high-DPI displays in the setup wizard
- Root cause: `pyautogui` sets DPI awareness when imported, which interfered with Tkinter layout
- Fix: Lazy-load pyautogui (import only when needed, after wizard completes)
- Extensive testing (39 test builds) isolated the root cause
- Also removed unnecessary DPI awareness code from v2.0.5

## [2.0.5] - 2026-01-06

### Bug Fixes (Superseded by v2.0.6)
- Added DPI awareness code (later found to cause issues, removed in v2.0.6)

## [2.0.4] - 2026-01-06

### Bug Fixes

#### Command Window Popup Fixed
- **Fixed PowerShell window flash** during installation when creating Start Menu shortcut
- Added `CREATE_NO_WINDOW` flag to subprocess call in `installer.py`

#### Finish Button Visual Feedback
- **Added button press/release visual feedback** to all wizard buttons
- Buttons now visually "depress" when clicked (darker color + sunken relief)
- Improves user feedback that the button click was registered

### Code Cleanup
- Removed temporary Debug tab from Settings (was used during v2.0.2 development)
- Removed all `[DEBUG]` print statements from `settings_gui.py`
- Removed debug logging to `whisper_download_debug.log` file

## [2.0.3] - 2025-12-31

### Bug Fixes

#### Toast Notification Icon Fix
- **Fixed green circle icon** in toast notifications - now shows correct microphone icon
- Root cause: `mic_icon.png` was missing from PyInstaller bundle (`whisper_tray.spec`)
- The code was updated in v2.0.0 to use `mic_icon.png`, but the spec file was never updated to include it
- Added `('icons/mic_icon.png', 'icons')` to spec file datas
- See `docs/BUG-toast-icon-green-circle.md` for full technical details

### Maintenance
- Created `backup_copies/` directory for EXE backups and test builds
- Cleaned up `dist/` folder - now contains only the main WhisperTray.exe

## [2.0.2] - 2025-12-28

### Bug Fixes

#### High-DPI Display Fixes (Multi-Approach Fallback System)
- **Fixed squished buttons** on Windows machines with different DPI scaling
- Implemented **automatic 5-method fallback system** for button rendering:
  1. tk.Button with padx/pady config
  2. tk.Button with height=2 parameter
  3. tk.Button with ipady=10 via pack
  4. tk.Button with ipadx=15 ipady=8 via pack
  5. Label styled as button (guaranteed to work)
- System automatically tries each method until one renders correctly (height >= 25px)
- Buttons now render consistently across ALL Windows machines regardless of DPI

#### UI Improvements
- **Dark title bar** now matches window theme on Windows 10/11
- **Model download path** now pre-filled with default HuggingFace cache location
- **Microphone selection** now auto-selects actual Windows default input device (not Microsoft Sound Mapper)

## [2.0.0] - 2025-12-10

### Major Features

#### Modern Setup Wizard
- **7-step first-run wizard** with dark theme UI (purple accents, Segoe UI font)
- **Storage Location step** - Choose between AppData (standard) or Portable mode
- **Microphone selection** with test recording (3-second record/playback)
- **Hotkey configuration** with visual capture popup
- **Model download step** - Download multiple models with progress indication
- **Model selection** - Choose default from downloaded models only
- **Completion summary** - Shows all settings, storage locations, and tray icon pinning tip

#### Dark-Themed Settings GUI
- **5-tab interface**: General, Audio, Behavior, Output, Models
- **Matches wizard styling** - Same dark theme with purple accents
- **Model Manager** - Download/delete models from Settings → Models tab
- **Storage info display** - Shows actual model cache and config locations (read-only)
- **Opens automatically** after first-run wizard for user to review all options

#### New Whisper Models
- Added **large-v3** (~3.0 GB) - Best accuracy, newest model
- Added **turbo** (~1.6 GB) - Excellent accuracy, 8x faster than large (OpenAI's optimized model)
- Total 7 models available: tiny, base, small, medium, large-v2, large-v3, turbo

#### Single-Instance Protection
- **Prevents multiple instances** from running simultaneously
- Shows helpful popup: "WhisperTray is already running. Check your system tray."

#### Startup Model Check
- **Warning popup** if no models are downloaded when app starts
- Offers to open Settings to download models

### Bug Fixes

#### Icon Fixes
- **Tray icons now work in bundled EXE** - Uses `sys._MEIPASS` for PyInstaller detection
- **Toast notification icon** - Now correctly uses `mic_icon.png`
- **All three status icons load properly**: idle (green), recording (red), processing (orange)

#### History Menu Fix
- **Menu now rebuilds** after each transcription (was showing empty)
- Added debug logging for history menu building

#### CUDA Auto-Detection
- **Automatically detects GPU** - Tries CUDA first, falls back to CPU
- No longer requires `torch` to be bundled (uses try/except around WhisperModel)

#### Model Storage
- **Removed custom path setting** - faster-whisper ignores `download_root` parameter
- Models always download to HuggingFace cache: `C:\Users\<user>\.cache\huggingface\hub\`
- Settings now displays actual storage locations (read-only)

### UI/UX Improvements

#### Wizard UI
- **Modern flat design** - Dark background (#1e1e2e), purple accents (#7c3aed)
- **Progress dots** - Visual step indicator at top of wizard
- **Compact layout** - Fits on 768px laptop screens (620x600 window)
- **Full microphone name display** - Uses wraplength to prevent truncation

#### Settings UI
- **Tab sizing fixed** - Selected tab same size as unselected tabs
- **Purple selected tab** with white text for clear indication
- **Download button width** increased to prevent text cutoff
- **Status label** - Shows download progress with color feedback (purple=progress, green=success, red=error)

#### Install Type Clarification
- Renamed "Install Type" to **"Storage Location"**
- Added note: "This is a standalone app - just run the EXE directly. No Windows installation required."
- Clarified that Standard vs Portable only affects where settings/logs are stored

### Disabled Features (Future Release)

#### Transcription Window
- **Temporarily disabled** due to tkinter mainloop conflicts
- When enabled, caused recording to fail with "volume too low" errors
- Menu item and Settings checkbox commented out
- Will be fixed in future release

### Technical Changes

#### Code Organization
- `scripts/` folder structure with modular files
- `icons/` folder for all icon assets
- PyInstaller spec bundles icons into EXE

#### Configuration
- Config stored in `%APPDATA%\WhisperTray\config.json` (standard mode)
- Or `.\config\config.json` (portable mode with `portable.txt` marker)
- Transcription logs in `transcriptions/YYYY/MM/DD.txt`

#### Build
- Single EXE output (~103 MB) via PyInstaller
- Includes all dependencies and icons
- No installation required - just run the EXE

### Known Issues

1. **Settings model download requires Python** - Downloading from Settings → Models tab requires Python + huggingface_hub installed. Workaround: Download all needed models during the first-run wizard (no Python required), or delete config.json to re-run the wizard.
2. **Transcription window** disabled until threading issues resolved
3. **Mic name truncation** in dropdown may still occur (source data issue, not display)

---

## [1.0.0] - 2024-11-XX (Original Release)

### Features
- System tray application with hotkey toggle (Ctrl+Alt+Space)
- Speech-to-text using faster-whisper
- Three tray icon states: idle, recording, transcribing
- Toast notifications for status updates
- Transcription history (last 5 items)
- Cancel recording with ESC key
- Auto-paste to focused window
- GPU acceleration support (--device cuda)
- Typing mode for terminals (--use-typing)
- Keep clipboard option (--keep-clipboard)
- Custom hotkey configuration (--hotkey)
- Microphone selection (--input-device)
- Auto-start on Windows login

### Models
- tiny (~39 MB)
- base (~74 MB)
- small (~244 MB) - recommended
- medium (~769 MB)
- large-v2 (~1.5 GB)
