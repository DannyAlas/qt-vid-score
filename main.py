VERSION = "0.2.0"
import argparse
import logging
import os
import sys
import traceback as tb

import sentry_sdk
from dotenv import load_dotenv
from logtail import LogtailHandler

os.environ["VERSION"] = VERSION  # WE MUST SET THIS BEFORE IMPORTING THE PROJECT
from video_scoring import MainWindow
from video_scoring.singleton_app import SingleInstanceApplication

load_dotenv()
log = logging.getLogger("video_scoring")


def logging_exept_hook(exctype: type, value: BaseException, trace: BaseException):
    log.critical(f"{str(exctype).upper()}: {value}\n\t{tb.format_exc()}")
    os.environ["UNHANDLED_EXCEPTION"] = "True"
    sys.__excepthook__(exctype, value, trace)


sys.excepthook = logging_exept_hook

handler = LogtailHandler(source_token=os.getenv("LOGTAIL_TOKEN"))
log.addHandler(handler)

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    enable_tracing=True,
    release=VERSION,
    environment="dev",
    send_default_pii=True,  # TODO: implement custom scrubber for now no PII is included so this is safe
    debug=False,
)
try:
    from ctypes import windll

    myappid = "danielalas.video.scoring." + str(VERSION).strip(".")
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

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
    app = SingleInstanceApplication(sys.argv)
    app.setApplicationName("Video Scoring")
    app.setOrganizationName("Daniel Alas")
    app.setOrganizationDomain("danielalas.com")
    app.setApplicationVersion(VERSION)
    if args.file:
        main_window = MainWindow(load_file=True, logging_level=log.getEffectiveLevel())
        main_window.open_project_file(args.file)
    else:
        main_window = MainWindow(logging_level=log.getEffectiveLevel())
    main_window.show()
    sys.exit(app.exec())
