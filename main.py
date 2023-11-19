__version__ = "0.0.1"

import logging
import sys
import traceback as tb

import qdarktheme
from qtpy.QtWidgets import QApplication

from video_scoring import MainWindow

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Video Scoring")
    app.setApplicationVersion(__version__)
    main_window = MainWindow()
    qdarktheme.setup_theme(theme="auto", corner_shape="rounded")
    main_window.show()
    sys.exit(app.exec())
