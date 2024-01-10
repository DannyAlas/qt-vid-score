import os
import subprocess
import sys
from typing import Union

VERSION = os.environ.get("VERSION", "")
if VERSION == "":
    raise ValueError("VERSION environment variable not set")


def user_data_dir(file_name: Union[str, None] = None):
    r"""
    Get OS specific data directory path for a file in the Video Scoring application data directory. Will be version specific.

    Parameters
    ----------
    file_name: Union[str, None]
        The name of the file to join with the data directory path, if None will return the data directory path

    Returns
    -------
    `str`
        Path to the data directory or the file in the data directory

    Notes
    -----
    Typical user data directories are:
        macOS:    ~/Library/Application Support/Video Scoring/<version>
        Unix:     ~/.local/share/Video Scoring/<version>
        Unix XDG:      $XDG_DATA_HOME/Video Scoring/<version>
        Win 10:   C:\Users\<username>\AppData\Local\Video Scoring\<version>

    For Unix, we follow the XDG spec and support $XDG_DATA_HOME if defined.
    """
    # get os specific path
    if (
        sys.platform.startswith("win")
        or sys.platform == "cygwin"
        or sys.platform == "msys"
    ):
        os_path = os.getenv("LOCALAPPDATA")
    elif sys.platform.startswith("darwin"):
        os_path = "~/Library/Application Support"
    else:
        # linux if $XDG_DATA_HOME is defined, use it
        os_path = os.getenv("XDG_DATA_HOME", "~/.local/share")

    # join with Video Scoring dir and version
    path = os.path.join(str(os_path), "Video Scoring", VERSION)
    if file_name is None:
        return path
    else:
        return os.path.join(path, file_name)


def cmd_run(cmd):
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, check=True, encoding="utf-8"
        ).stdout.strip()
    except:
        return ""


def get_device_id():

    if sys.platform.startswith("linux"):
        return cmd_run("cat /var/lib/dbus/machine-id") or cmd_run("cat /etc/machine-id")

    if sys.platform == "darwin":
        return cmd_run(
            "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'"
        )

    if sys.platform.startswith("openbsd") or sys.platform.startswith("freebsd"):
        return cmd_run("cat /etc/hostid") or cmd_run("kenv -q smbios.system.uuid")

    if sys.platform == "win32" or sys.platform == "cygwin" or sys.platform == "msys":
        return cmd_run("wmic csproduct get uuid").split("\n")[2].strip()
