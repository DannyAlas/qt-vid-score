VERSION = "0.2.0"
import argparse
import logging
import os
import sys
import traceback as tb

import qdarktheme
from qtpy.QtWidgets import QApplication

import sentry_sdk

os.environ["VERSION"] = VERSION # WE MUST SET THIS BEFORE IMPORTING THE PROJECT
from video_scoring import MainWindow

sentry_sdk.init(
    dsn="https://8b9d5384e79de12983fc6977a221168c@o4506504253538304.ingest.sentry.io/4506504259764224",
    enable_tracing=True,
    release=VERSION,
    environment="dev",
    send_default_pii=True, # TODO: implement custom scrubber for now now PII is included so this is safe
    debug=True
)
log = logging.getLogger()


def logging_exept_hook(exctype: type, value: BaseException, trace: BaseException):
    # create BaseException instance to get traceback
    sentry_sdk.capture_exception(value)
    log.critical(f"{str(exctype).upper()}: {value}\n\t{tb.format_exc()}")
    sys.__excepthook__(exctype, value, trace)

sys.excepthook = logging_exept_hook

try:
    from ctypes import windll

    myappid = "danielalas.video.scoring." + str(VERSION).strip(".")
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass
log = logging.getLogger()


parser = argparse.ArgumentParser(description="Video Scoring")
# we can be passed a .vsap file to open there will be no args passed to the app just a file
parser.add_argument("file", nargs="?", help="Video Scoring Archive File")
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
    print(f"Video Scoring v{VERSION}")
    sys.exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Video Scoring")
    app.setOrganizationName("Daniel Alas")
    app.setOrganizationDomain("danielalas.com")
    app.setApplicationVersion(VERSION)

    main_window = MainWindow()
    qdarktheme.setup_theme(theme="auto", corner_shape="rounded")
    main_window.show()
    sys.exit(app.exec())
