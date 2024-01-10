from typing import TYPE_CHECKING, Literal, Optional

from qtpy import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from video_scoring import MainWindow


def create_qaction(
    main_win: "MainWindow", icon_name: str, name: str, parent: QtCore.QObject
) -> QtWidgets.QAction:
    action = QtWidgets.QAction(name, parent)
    action.setIcon(main_win.get_icon(icon_name, action))
    return action
