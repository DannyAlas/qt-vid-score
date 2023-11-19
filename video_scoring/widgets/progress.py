from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QThread, Signal
from qtpy.QtWidgets import QGridLayout, QLabel, QProgressBar, QWidget

if TYPE_CHECKING:
    from video_scoring import MainWindow

# The general workflow for this will be:
# If you want to pop up a progress bar you will instantiate a progress bar signal object and add your connections
# Then pass it to the main window which will instantiate a progress bar and pass your provided signal object to it


class ProgressSignals(QObject):
    started = Signal()
    progress = Signal(int)
    complete = Signal()


class ProgressBar(QWidget):
    def __init__(
        self,
        signals: ProgressSignals,
        title: str,
        completed_msg: str,
        main_window: "MainWindow",
    ):
        super().__init__()
        self.pbar = QProgressBar(self)
        self.main_win = main_window
        self.completed_msg = completed_msg
        self.layout = QGridLayout()
        self.layout.addWidget(self.pbar, 0, 0)
        self.setLayout(self.layout)
        self.setWindowTitle(title)

        self.signals = signals
        self.p_thread = QThread()
        self.signals.progress.connect(self.on_count_changed)
        self.signals.moveToThread(self.p_thread)
        self.signals.complete.connect(self.complete_progress)
        self.signals.complete.connect(
            self.hide
        )  # To hide the progress bar after the progress is completed

    def start_progress(self):  # To restart the progress every time
        self.p_thread.start()
        self.place_in_status_bar()

    def place_in_status_bar(self):
        # set pbar to be small
        self.pbar.setFixedHeight(15)
        self.pbar.setFixedWidth(200)
        # add the title to the right of the progress bar, adding a ... to the end if it is too long
        label = [
            QLabel(self.windowTitle())
            if len(self.windowTitle()) < 20
            else QLabel(self.windowTitle()[:25] + "...")
        ][0]
        self.layout.addWidget(label, 0, 1)
        # add the progress bar to the status bar
        self.main_win.statusBar().addWidget(self)

    def complete_progress(self):
        # kill the thread
        self.p_thread.quit()
        self.p_thread.wait()
        # remove the progress bar from the status bar
        self.main_win.statusBar().removeWidget(self.pbar)
        self.main_win.statusBar().removeWidget(self)
        self.main_win.statusBar().showMessage(self.completed_msg)
        self.close()

    def on_count_changed(self, value):
        self.pbar.setValue(value)

    def closeEvent(self, event):
        self.p_thread.quit()
        self.p_thread.wait()
        # mark us for deletion
        self.deleteLater()
        # accept the event
        event.accept()
