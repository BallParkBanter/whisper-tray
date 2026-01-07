# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Whisper-Tray
Creates a single executable file for Windows distribution.

To build:
    cd D:\whisper-tray
    .\.venv\Scripts\pyinstaller whisper_tray.spec --clean

Output: dist\WhisperTray.exe
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect faster-whisper and ctranslate2 data
datas = []
datas += collect_data_files('faster_whisper')
datas += collect_data_files('ctranslate2')
datas += collect_data_files('sounddevice')  # Includes PortAudio DLL

# Add our icons
datas += [
    ('icons/idle_icon.webp', 'icons'),
    ('icons/recording_icon.png', 'icons'),
    ('icons/processing_icon.webp', 'icons'),
    ('icons/mic_icon.png', 'icons'),  # Toast notification icon (fix: 2025-12-31)
]

# Add our Python modules
datas += [
    ('scripts/config.py', 'scripts'),
    ('scripts/settings_gui.py', 'scripts'),
    ('scripts/first_run.py', 'scripts'),
    ('scripts/errors.py', 'scripts'),
    ('scripts/transcription_window.py', 'scripts'),
    ('scripts/installer.py', 'scripts'),
]

# Hidden imports for faster-whisper and dependencies
hiddenimports = [
    'faster_whisper',
    'ctranslate2',
    'sounddevice',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'pystray',
    'pystray._win32',
    'keyboard',
    'pyperclip',
    'pyautogui',
    'winotify',
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.scrolledtext',
    # For self-installing wizard (shortcuts, startup registry)
    'win32com',
    'win32com.client',
    'winshell',
    'winreg',
]
hiddenimports += collect_submodules('ctranslate2')

a = Analysis(
    ['scripts/windows_mic_button.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhisperTray',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - runs as tray app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/mic_icon.ico',
    version_info=None,
)
