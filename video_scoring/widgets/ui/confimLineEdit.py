from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QEnterEvent, QMouseEvent, QMoveEvent, QPaintEvent, QResizeEvent
from PyQt6.QtCore import QEvent
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from video_scoring import MainWindow
    
class CheckButton(QtWidgets.QPushButton):
    """A check button that changes icon when hovered."""

    def __init__(self, parent: QtWidgets.QWidget, main_win: "MainWindow"):
        super().__init__(parent)
        self.main_win = main_win
        self.setFixedSize(20, 20)
        self.setIcon(main_win.get_icon("check.png", self))
        self.setIconSize(QtCore.QSize(20, 20))
        self.setFlat(True)
        self.setMouseTracking(True)
        self.hovered = False

    def enterEvent(self, a0: QEvent | None) -> None:
        self.hovered = True
        self.setIcon(self.main_win.get_icon("checkbox_checked.png", self))
        return super().enterEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hovered = False
        self.setIcon(self.main_win.get_icon("check.png", self))
        return super().leaveEvent(a0)


class ConfirmLineEdit(QtWidgets.QWidget):
    """A QWidget with a confirm and exit button that appear when focused. If confirm is clicked the text is saved and the buttons are hidden, if exit is clicked the text is reverted to the original text and the buttons are hidden. If unfocused the buttons are hidden and the text is reverted."""
    def __init__(
        self, 
        parent: "QtWidgets.QWidget", 
        main_win: "MainWindow", 
        text: str, 
    ):
        super().__init__(parent)
        self._parent = parent
        self.main_win = main_win
        self.text = text
        self.hovered = False
        
        self.setMouseTracking(True)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        self.edit = QtWidgets.QLineEdit(self)
        self.edit.setText(text)
        self.edit.installEventFilter(self)
        self.edit.returnPressed.connect(self.on_confirm_button_clicked)
        self.confirm_button = None
        self.setup_buttons()
        
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            self.confirm_button.show()
        elif event.type() == QEvent.Type.FocusOut:
            # if it wasn't the check button that was clicked
            if not self.confirm_button.underMouse():
                self.confirm_button.hide()
                self.edit.setText(self.text)
        return super().eventFilter(obj, event)

    def setText(self, text: str):
        self.text = text
        self.edit.setText(text)

    def setup_buttons(self):
        self.confirm_button = CheckButton(self, self.main_win)
        self.confirm_button.setFixedSize(20, 20)
        self.confirm_button.clicked.connect(self.on_confirm_button_clicked)
        self.confirm_button.hide()
        self.layout.addWidget(self.edit)
        self.layout.addWidget(self.confirm_button)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        self.hovered = True
        return super().mouseMoveEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hovered = False
        return super().leaveEvent(a0)

    def on_confirm_button_clicked(self):
        self.text = self.edit.text()
        self.confirm_button.hide()
        self.save_func(self.text)

    def save_func(self, text: str):
        """
        Overload this function to perform an action when the text is saved.

        Parameters
        ----------
        text : str
            The text that was saved
        """
        pass

    def revert_func(self, text: str):
        """
        Overload this function to perform an action when the text is reverted.

        Parameters
        ----------
        text : str
            The text that was reverted
        """
        pass

