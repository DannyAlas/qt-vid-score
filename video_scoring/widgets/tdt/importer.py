from qtpy import QtCore, QtWidgets
from typing import TYPE_CHECKING
from video_scoring.widgets.tdt import TDT, TDTLoader, TDTSettings
import logging
import logtail
log = logging.getLogger("video_scoring")


if TYPE_CHECKING:
    from video_scoring import MainWindow


class TDTImporter(QtWidgets.QWidget):
    imported = QtCore.Signal()

    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent=parent)
        self.main_win = main_win


    def _init_ui(self):
        # a line edit to enter in the name for the timestamps
        self.name = self.main_win.project_settings.name
        if self.main_win.project_settings.scoring_data.tdt_data is not None:
            self.name = self.main_win.project_settings.scoring_data.tdt_data.blockname
        self.name_label = QtWidgets.QLabel("Name")
        self.name_line = QtWidgets.QLineEdit(self.name)
        self.name_line.textChanged.connect(self.name_line_changed)

        self.block_label = QtWidgets.QLabel("TDT Block")
        self.block_line = QtWidgets.QLineEdit()
        self.block_line.setReadOnly(True)
        self.block_button = QtWidgets.QPushButton("Select Block")
        self.block_button.clicked.connect(self.select_block)
        if self.main_win.project_settings.scoring_data.tdt_data is not None:
            self.block_line.setText(
                self.main_win.project_settings.scoring_data.tdt_data.blockname
            )
            self.block_line.setToolTip(
                self.main_win.project_settings.scoring_data.tdt_data.blockpath
            )

    def name_line_changed(self):
        self.name = self.name_line.text()

    def select_block(self):
        # file dialog to select a folder
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        file_dialog.setDirectory(self.main_win.project_settings.file_location)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                self.tdt_loader_thread = QtCore.QThread()
                self.tdt_loader = TDTLoader(file_dialog.selectedFiles()[0])
                self.tdt_loader.moveToThread(self.tdt_loader_thread)
                self.tdt_loader_thread.started.connect(self.tdt_loader.run)
                self.tdt_loader.signals.complete.connect(self.tdt_loader_thread.quit)
                self.tdt_loader.signals.complete.connect(
                    lambda: self.load_block(self.tdt_loader)
                )
                self.tdt_loader_thread.start()
                self.main_win.start_pbar(
                    self.tdt_loader.signals,
                    f"Importing TDT Tank {file_dialog.selectedFiles()[0]}",
                    "Imported TDT Tank",
                    popup=True,
                )
            except:
                self.main_win.update_status(
                    f"Failed to import TDT Tank {file_dialog.selectedFiles()[0]}"
                )

    def load_block(self, loader: TDTLoader):
        # FIXME: proper loading please :)
        try:
            self.main_win.save_settings()
            self.main_win.project_settings.scoring_data.tdt_data = TDTSettings()
            self.tdt = TDT(loader.block, self.main_win.project_settings.scoring_data.tdt_data)
            self.tdt.load_settings_from_block(loader.block)
            log.info(self.tdt.block.info.blockpath)
            try:
                self.main_win.project_settings.scoring_data.video_file_location = (
                    self.tdt.get_video_path()
                )
            except Exception as e:
                log.warning("Error getting video path from TDT", exc_info=e)
                self.main_win.project_settings.scoring_data.video_file_location = ""
            self.main_win.update_status(
                f"Imported video at {self.main_win.project_settings.scoring_data.video_file_location}"
            )
            with logtail.context(
                device={"id": self.main_win.app_settings.device_id},
                tank=self.main_win.project_settings.scoring_data.tdt_data.model_dump(),
            ):
                log.info(f"Imported TDT Tank")
            self.main_win.save_settings()
            self.main_win._loaders()
        except:
            self.main_win.update_status(
                f"Failed to import Tank at {loader.block.info.blockpath}"
            )