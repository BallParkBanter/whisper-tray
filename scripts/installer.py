"""Self-installation functionality for WhisperTray.

This module handles copying the EXE to proper locations, creating shortcuts,
and managing Windows startup entries.
"""
import os
import sys
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_exe_path() -> Path:
    """Get path to current executable.

    Returns:
        Path to the running EXE (or script if not frozen)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable)
    # Development mode - return a reasonable path
    return Path(__file__).parent.parent / "WhisperTray.exe"


def get_standard_install_dir() -> Path:
    """Get the standard install directory (AppData\\Local\\WhisperTray).

    Returns:
        Path to standard install directory
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        return Path(local_appdata) / "WhisperTray"
    return Path.home() / "AppData" / "Local" / "WhisperTray"


def is_running_from_install_location() -> bool:
    """Check if running from a proper install location.

    Returns:
        True if running from AppData\\Local\\WhisperTray or portable location
    """
    exe_path = get_exe_path()

    # Check if in standard install location (AppData\Local\WhisperTray)
    standard_dir = get_standard_install_dir()
    if exe_path.parent == standard_dir:
        return True

    # Check if portable (config folder exists next to exe)
    if (exe_path.parent / "config").exists():
        return True

    return False


def is_portable_install() -> bool:
    """Check if this is a portable installation.

    Returns:
        True if config folder exists next to the EXE
    """
    exe_path = get_exe_path()
    return (exe_path.parent / "config").exists()


def install_standard() -> Path:
    """Install to AppData\\Local with Start Menu shortcut.

    Copies the EXE to %LOCALAPPDATA%\\WhisperTray\\WhisperTray.exe

    Returns:
        Path to the installed EXE

    Raises:
        RuntimeError: If LOCALAPPDATA environment variable is not set
        PermissionError: If cannot write to target directory
    """
    exe_path = get_exe_path()
    install_dir = get_standard_install_dir()

    logger.info(f"Installing to standard location: {install_dir}")

    # Create install directory
    install_dir.mkdir(parents=True, exist_ok=True)

    target_exe = install_dir / "WhisperTray.exe"

    # Copy EXE if not already there or if source is different
    if exe_path != target_exe:
        if target_exe.exists():
            # Check if same file (by size for quick check)
            if exe_path.stat().st_size != target_exe.stat().st_size:
                logger.info(f"Updating existing installation")
                shutil.copy2(exe_path, target_exe)
            else:
                logger.info(f"Installation already up to date")
        else:
            logger.info(f"Copying EXE to {target_exe}")
            shutil.copy2(exe_path, target_exe)

    return target_exe


def install_portable(target_folder: Path) -> Path:
    """Install to custom folder with all data local.

    Creates the folder structure:
    - target_folder/WhisperTray.exe
    - target_folder/config/  (for settings)
    - target_folder/models/  (for AI models)

    Args:
        target_folder: Destination folder for portable install

    Returns:
        Path to the installed EXE

    Raises:
        PermissionError: If cannot write to target directory
    """
    exe_path = get_exe_path()

    logger.info(f"Installing portable to: {target_folder}")

    # Create folder structure
    target_folder.mkdir(parents=True, exist_ok=True)
    (target_folder / "config").mkdir(exist_ok=True)
    (target_folder / "models").mkdir(exist_ok=True)

    target_exe = target_folder / "WhisperTray.exe"

    # Copy EXE if not already there
    if exe_path != target_exe:
        if target_exe.exists():
            if exe_path.stat().st_size != target_exe.stat().st_size:
                logger.info(f"Updating existing portable installation")
                shutil.copy2(exe_path, target_exe)
            else:
                logger.info(f"Portable installation already up to date")
        else:
            logger.info(f"Copying EXE to {target_exe}")
            shutil.copy2(exe_path, target_exe)

    return target_exe


def create_start_menu_shortcut(exe_path: Path) -> Path | None:
    """Create Start Menu shortcut.

    Creates a shortcut at: Start Menu\\Programs\\WhisperTray.lnk

    Args:
        exe_path: Path to the installed EXE

    Returns:
        Path to created shortcut, or None if creation failed
    """
    try:
        # Try using winshell (preferred)
        import winshell
        from win32com.client import Dispatch

        programs_folder = Path(winshell.start_menu()) / "Programs"
        shortcut_path = programs_folder / "WhisperTray.lnk"

        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        shortcut.IconLocation = str(exe_path)
        shortcut.Description = "WhisperTray - Voice to Text"
        shortcut.save()

        logger.info(f"Created Start Menu shortcut: {shortcut_path}")
        return shortcut_path

    except ImportError:
        logger.warning("winshell/pywin32 not available, trying alternative method")

        try:
            # Alternative: Use PowerShell
            import subprocess

            appdata = os.environ.get("APPDATA", "")
            if not appdata:
                return None

            programs_folder = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            shortcut_path = programs_folder / "WhisperTray.lnk"

            # PowerShell command to create shortcut
            ps_command = f'''
            $WScriptShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WScriptShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{exe_path}"
            $Shortcut.WorkingDirectory = "{exe_path.parent}"
            $Shortcut.IconLocation = "{exe_path}"
            $Shortcut.Description = "WhisperTray - Voice to Text"
            $Shortcut.Save()
            '''

            # CREATE_NO_WINDOW prevents PowerShell window from flashing
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                creationflags=creationflags
            )

            if result.returncode == 0:
                logger.info(f"Created Start Menu shortcut via PowerShell: {shortcut_path}")
                return shortcut_path
            else:
                logger.error(f"PowerShell shortcut creation failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Failed to create shortcut: {e}")
            return None

    except Exception as e:
        logger.error(f"Failed to create Start Menu shortcut: {e}")
        return None


def remove_start_menu_shortcut() -> bool:
    """Remove Start Menu shortcut if it exists.

    Returns:
        True if removed or didn't exist, False on error
    """
    try:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            shortcut_path = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "WhisperTray.lnk"
            if shortcut_path.exists():
                shortcut_path.unlink()
                logger.info(f"Removed Start Menu shortcut: {shortcut_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove Start Menu shortcut: {e}")
        return False


def add_to_startup(exe_path: Path, enable: bool = True) -> bool:
    """Add or remove from Windows startup.

    Modifies registry key: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

    Args:
        exe_path: Path to the EXE
        enable: True to add to startup, False to remove

    Returns:
        True on success, False on failure
    """
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )

        try:
            if enable:
                winreg.SetValueEx(key, "WhisperTray", 0, winreg.REG_SZ, str(exe_path))
                logger.info(f"Added to Windows startup: {exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, "WhisperTray")
                    logger.info("Removed from Windows startup")
                except FileNotFoundError:
                    pass  # Already not in startup
        finally:
            winreg.CloseKey(key)

        return True

    except Exception as e:
        logger.error(f"Failed to modify startup registry: {e}")
        return False


def is_in_startup() -> bool:
    """Check if WhisperTray is configured to run at startup.

    Returns:
        True if in startup, False otherwise
    """
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_READ
        )

        try:
            value, _ = winreg.QueryValueEx(key, "WhisperTray")
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)

    except Exception:
        return False


def get_running_from_path() -> str:
    """Get a human-readable description of where the app is running from.

    Returns:
        String describing the current run location (e.g., "Downloads folder")
    """
    exe_path = get_exe_path()
    parent = exe_path.parent.name.lower()

    if parent == "downloads":
        return "Downloads folder"
    elif parent == "desktop":
        return "Desktop"
    elif parent == "whispertray":
        return "installed location"
    else:
        return str(exe_path.parent)


def needs_installation() -> bool:
    """Check if the app needs to be installed (not running from proper location).

    Returns:
        True if running from a temporary location like Downloads
    """
    if is_running_from_install_location():
        return False

    # Check if running from common temporary locations
    exe_path = get_exe_path()
    parent_lower = str(exe_path.parent).lower()

    temp_locations = ["downloads", "temp", "tmp", "desktop"]
    for loc in temp_locations:
        if loc in parent_lower:
            return True

    # If not in a known install location, suggest installation
    return True
