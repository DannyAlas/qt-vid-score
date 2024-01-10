import sys

from PyQt6.QtCore import QSharedMemory
from PyQt6.QtWidgets import QApplication


class SingleInstanceApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.sharedMemory = QSharedMemory("video_scoring")
        if self.sharedMemory.attach():
            sys.exit(0)
        else:
            self.sharedMemory.create(1)

    def __del__(self):
        # on Windows if crashed the kernel will clean up the shared memory when the process exits resulting in an error here, so we just ignore it, on Unix the shared memory will persist so we need to clean it up.
        # https://stackoverflow.com/a/42551052/15579014
        try:
            self.sharedMemory.detach()
        except Exception:
            pass
