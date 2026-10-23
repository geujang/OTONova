"""Platform-neutral resources, writable logs and inference subprocess launch."""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent


def resources():
    return Path(getattr(sys, "_MEIPASS", ROOT))


def workspace():
    base = resources()
    if (base / "Japanese/phonemes.txt").is_file():
        return base
    executable = Path(sys.executable).parent
    if (executable / "Japanese/phonemes.txt").is_file():
        return executable
    return base


def log_directory(platform=None, home=None):
    platform = platform or sys.platform
    home = Path(home) if home else Path.home()
    if platform == "darwin":
        return home / "Library/Logs/OTONova"
    if platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
            / "OTONova/Logs"
        )
    return (
        Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state"))) / "OTONova"
    )


def log_path(name):
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def backend_command(
    workspace_path,
    resource_path,
    model_root,
    model_dir,
    *,
    platform=None,
    frozen=None,
    executable=None,
):
    platform = platform or sys.platform
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    executable = executable or sys.executable
    base = Path(workspace_path)
    if frozen and platform == "darwin":
        return [str(executable), "--wfl-backend", str(model_root), str(model_dir)]
    candidates = (
        [base / "runtime/python.exe", base / ".wfl-venv/Scripts/python.exe"]
        if platform == "win32"
        else [
            base / "runtime/bin/python3",
            base / ".wfl-venv/bin/python3",
            base / ".venv/bin/python3",
        ]
    )
    python = next((p for p in candidates if p.is_file()), Path(executable))
    return [
        str(python),
        "-B",
        "-I",
        str(Path(resource_path) / "tools/wfl_backend.py"),
        str(model_root),
        str(model_dir),
    ]


# Keep native icon handles alive for the lifetime of the GUI process.
_taskbar_icons = []


def set_windows_taskbar_icon(window, icon_path):
    """Set both native window icon sizes used by Windows taskbar and Alt+Tab."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    for kind, size in ((0, 16), (1, 32)):
        icon = user32.LoadImageW(None, str(icon_path), 1, size, size, 0x10)
        if not icon:
            raise ctypes.WinError(ctypes.get_last_error())
        _taskbar_icons.append(icon)
        user32.SendMessageW(int(window.winId()), 0x80, kind, icon)
