import ctypes
import logging
import os
import subprocess
import sys
from typing import Union

log = logging.getLogger("video_scoring")
VERSION = os.environ.get("VERSION", "")
if VERSION == "":
    log.error("VERSION environment variable not set")


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


def unicode(s: str):
    # just in case
    return s.encode("utf-8").decode("utf-8")


import ctypes
import sys


def run_self_admin(argv=None, debug=False):
    """
    Run the program as an administrator.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. Defaults to None.
    debug : bool, optional
        Flag to enable debug mode. Defaults to False.

    Returns
    -------
    bool or None
        True if the program is already running as an administrator,
        False if the program failed to run as an administrator,
        None if the program is not running as an administrator and needs to be elevated.
    """
    shell32 = ctypes.windll.shell32
    if argv is None and shell32.IsUserAnAdmin():
        return True

    if argv is None:
        argv = sys.argv
    if hasattr(sys, "_MEIPASS"):
        arguments = map(unicode, argv[1:])
    else:
        arguments = map(unicode, argv)
    argument_line = " ".join(arguments)
    executable = unicode(sys.executable)
    if debug:
        log.debug("Command line: ", executable, argument_line)
    ret = shell32.ShellExecuteW(None, "runas", executable, argument_line, None, 1)
    if int(ret) <= 32:
        return False
    return None


def run_exe_as_admin(exe_path: str, argv: list = None):
    """
    Run an executable as an administrator.

    Parameters
    ----------
    exe_path : str
        Path to the executable to run as an administrator.
    argv : list, optional
        List of command-line arguments. Defaults to None.
    debug : bool, optional
        Flag to enable debug mode. Defaults to False.

    Returns
    -------
    bool or None
        True if the program is already running as an administrator,
        False if the program failed to run as an administrator,
        None if the program is not running as an administrator and needs to be elevated.
    """
    shell32 = ctypes.windll.shell32
    log.debug("Running as admin: ", exe_path)
    if argv is not None:
        ret = shell32.ShellExecuteW(None, "runas", exe_path, argv, None, 1)
    else:
        ret = shell32.ShellExecuteW(None, "runas", exe_path, None, None, 1)
    if int(ret) <= 32:
        return False
    return None
