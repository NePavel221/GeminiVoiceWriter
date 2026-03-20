"""
Paths module - PORTABLE mode: all data stored next to exe.
"""
import os
import sys


def get_app_dir() -> str:
    """Get the application directory (where exe is located)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir() -> str:
    """Get the data directory - PORTABLE: always next to exe."""
    # Always store data next to the executable (portable mode)
    data_dir = os.path.join(get_app_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_recordings_dir() -> str:
    """Get directory for audio recordings."""
    recordings_dir = os.path.join(get_data_dir(), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    return recordings_dir


def get_logs_dir() -> str:
    """Get directory for log files."""
    logs_dir = os.path.join(get_data_dir(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_settings_path() -> str:
    """Get path to settings file."""
    return os.path.join(get_data_dir(), "settings.json")


def get_database_path() -> str:
    """Get path to history database."""
    return os.path.join(get_data_dir(), "history.db")
