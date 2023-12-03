"""
This file contains the installer class for the video scoring application.

The main program will check for updates on startup. If an update is found, it will download the latest release from github and start the application with the --install argument. 

The flag will run this installer instead of the main program. Here we will extract the downloaded release into the approriate directory and start the main program again.
"""

import logging
import os
import sys
from pathlib import Path
from zipfile import ZipFile

from video_scoring.main import __version__ as VERSION

# get our current directory
CURRENT_DIR = Path(__file__).parent.absolute()

