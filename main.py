import argparse
import logging
import os
import sys
import traceback as tb

import qdarktheme
from qtpy.QtWidgets import QApplication

from video_scoring import MainWindow, __version__

try:
    from ctypes import windll

    myappid = "danielalas.video.scoring." + str(__version__).strip(".")
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass
log = logging.getLogger()


def logging_exept_hook(exctype, value, trace):
    log.critical(f"{str(exctype).upper()}: {value}\n\t{tb.format_exc()}")
    sys.__excepthook__(exctype, value, trace)


sys.excepthook = logging_exept_hook

parser = argparse.ArgumentParser(description="Video Scoring")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
parser.add_argument(
    "--debug-qt", action="store_true", help="Enable debug logging for Qt"
)
parser.add_argument("--version", action="store_true", help="Print version and exit")
args = parser.parse_args()
if args.debug:
    # set env variable QT_LOGGING_RULES="qt.qpa.*=true" to enable qt debug logging
    os.environ["DEBUG"] = args.debug.__str__()
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
if args.debug_qt:
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=true"
if args.version:
    print(f"Video Scoring v{__version__}")
    sys.exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Video Scoring")
    app.setOrganizationName("Daniel Alas")
    app.setOrganizationDomain("danielalas.com")
    app.setApplicationVersion(__version__)
    main_window = MainWindow()
    qdarktheme.setup_theme(theme="auto", corner_shape="rounded")
    main_window.show()
    sys.exit(app.exec())
