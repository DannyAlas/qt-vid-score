import os
from typing import TYPE_CHECKING, Literal, Optional

import qdarktheme
from PyQt6.QtCore import QObject
from qtpy import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from video_scoring import MainWindow


class StyleSheet(QtCore.QObject):
    complete = QtCore.Signal()

    def __init__(self, main_win: "MainWindow", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.main_win = main_win
        self.icons_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources"
        )
        self.dynamic_icons: dict[str, "DynamicIcon"] = {}  # icon_name: icon
        self.main_win.loaded.connect(
            lambda: self.set_theme(self.main_win.app_settings.theme)
        )

    def set_additional_style(self):
        if self.main_win.app_settings.theme == "dark":
            additional_style = "QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }"
        elif self.main_win.app_settings.theme == "light":
            additional_style = "QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }"
        else:
            return
        qdarktheme.setup_theme(
            self.main_win.app_settings.theme, additional_qss=additional_style
        )
        self.ss = qdarktheme.load_stylesheet(theme=self.main_win.app_settings.theme)

    def set_theme(self, theme: Literal["dark", "light"]):
        old_theme = self.main_win.app_settings.theme
        self.main_win.app_settings.theme = theme
        additional_style = ""
        if theme == "dark":
            additional_style = "QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }"
        elif theme == "light":
            additional_style = "QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }"

        qdarktheme.setup_theme(theme, additional_qss=additional_style)
        self.ss = qdarktheme.load_stylesheet(theme=theme)
        self.run()
        if old_theme != theme:
            self.update_icons()

    def update_icons(self):
        for _, icon in self.dynamic_icons.items():
            icon.update_icon()

    def run(self):
        for widget in self.main_win.findChildren(QtWidgets.QWidget):
            widget.update()
            widget.setStyleSheet(self.ss)
        self.complete.emit()

    def get_icon_path(self, icon_name):
        if self.main_win.app_settings.theme == "dark":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        elif self.main_win.app_settings.theme == "light":
            icon_path = os.path.join(self.icons_dir, icon_name)
        elif self.main_win.app_settings.theme == "auto":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        else:
            raise Exception(f"Theme {self.main_win.app_settings.theme} not recognized")
        return icon_path

    def get_icon(self, icon_name, request_object) -> "DynamicIcon":
        icon_path = self.get_icon_path(icon_name)
        icon = DynamicIcon(icon_path, self, self.main_win, request_object)
        self.dynamic_icons[icon_name] = icon
        return icon

    def get_static_icon(self, icon_name) -> QtGui.QIcon:
        icon_path = self.get_icon_path(icon_name)
        return QtGui.QIcon(icon_path)


class DynamicIcon(QtGui.QIcon):
    def __init__(
        self,
        icon_path,
        style_sheet: "StyleSheet",
        main_window: "MainWindow",
        parent: QtCore.QObject,
    ):
        super().__init__(icon_path)
        self.icon_path = icon_path
        self.icon_name = os.path.basename(icon_path)
        self.main_window = main_window
        self.style_sheet = style_sheet
        self.parent = parent

    def update_icon(self):
        icon_path = self.main_window.style_sheet.get_icon_path(self.icon_name)
        self.icon_path = icon_path
        self.icon_name = os.path.basename(icon_path)
        self.swap_icon(icon_path)

    def swap_icon(self, icon_path):
        if self.parent:
            if type(self.parent) == QtWidgets.QAction:
                self.parent.setIcon(QtGui.QIcon(icon_path))
