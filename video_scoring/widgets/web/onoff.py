from qtpy import QtCore, QtGui, QtWidgets


class OnlineOfflineWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.online = False
        self.setFixedSize(10, 10)
        self.setToolTip("Offline")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        if self.online:
            painter.setBrush(QtGui.QColor("#85ff97"))
        else:
            painter.setBrush(QtGui.QColor("#ff8585"))
            self.setToolTip("Offline")
        painter.drawEllipse(self.rect())

    def update(self, active_users: int = None):
        if active_users is not None:
            self.setToolTip(f"Active Users: {active_users}")
        self.updateGeometry()
        super().update()
