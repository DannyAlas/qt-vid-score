import enum
import re
from calendar import c
from typing import TYPE_CHECKING, TypeVar

import pandas as pd
from qtpy import QtCore, QtGui, QtWidgets

from video_scoring.settings import TDTData
from video_scoring.widgets.loaders import TDTLoader

if TYPE_CHECKING:
    from video_scoring import MainWindow
# enum for delimiters
class Delimiters(enum.Enum):
    TAB = "\t"
    COMMA = ","
    SPACE = " "
    SEMICOLON = ";"
    COLON = ":"
    NEWLINE = "\n"


# delimiter type
DelimiterValue = TypeVar("DelimiterValue", bound=str)


class ManualImporter(QtWidgets.QWidget):
    imported = QtCore.Signal()

    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent=parent)
        self.main_win = main_win
        self.onset_offset_unsure: list[tuple[int, int, bool]] = []
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        # a line edit to enter in the name for the timestamps
        self.name = self.main_win.project_settings.name
        self.name_label = QtWidgets.QLabel("Name")
        self.name_line = QtWidgets.QLineEdit(self.name)
        self.name_line.textChanged.connect(self.name_line_changed)

        # a combo box to select the delimiter
        self.delimiter_label = QtWidgets.QLabel("Delimiter")
        self.delimiter_combo = QtWidgets.QComboBox()
        self.delimiter_combo.addItems([delimiter.name for delimiter in Delimiters])
        self.delimiter_combo.setCurrentText("TAB")
        self.delimiter_combo.currentTextChanged.connect(self.delimiter_combo_changed)
        # a text edit to enter in the timestamps
        self.text_edit_label = QtWidgets.QLabel("Enter Timestamps")
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.textChanged.connect(self.text_edit_changed)
        self.text_edit.setAcceptRichText(False)
        # eroor label
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color: red")

        # a combo box to select the onset column
        self.onset_label = QtWidgets.QLabel("Onset Column (RED)")
        self.onset_combo = QtWidgets.QComboBox()
        self.onset_combo.currentTextChanged.connect(self.populate_table)
        # a combo box to select the offset column
        self.offset_label = QtWidgets.QLabel("Offset Column (BLUE)")
        self.offset_combo = QtWidgets.QComboBox()
        self.offset_combo.currentTextChanged.connect(self.populate_table)
        # a combo box to select the unsure column
        self.unsure_label = QtWidgets.QLabel("Unsure Column (YELLOW)")
        self.unsure_combo = QtWidgets.QComboBox()
        self.unsure_combo.addItem("None")
        self.unsure_combo.currentTextChanged.connect(self.populate_table)

        # a table to show the parsed timestamps
        self.table_label = QtWidgets.QLabel("Parsed Timestamps Preview")
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setRowCount(0)

        # a button to accept the input, will set the onset_offset attribute
        self.import_button = QtWidgets.QPushButton("Import")
        self.import_button.clicked.connect(self.accept_input)
        self.import_button.setEnabled(False)

        # all the options on the left, texedit and table on the right
        options_container = QtWidgets.QWidget()
        options_container_layout = QtWidgets.QGridLayout()
        edit_container = QtWidgets.QWidget()
        edit_container_layout = QtWidgets.QGridLayout()
        options_container.setLayout(options_container_layout)
        edit_container.setLayout(edit_container_layout)
        options_container_layout.addWidget(self.name_label, 0, 0)
        options_container_layout.addWidget(self.name_line, 0, 1)
        options_container_layout.addWidget(self.delimiter_label, 1, 0)
        options_container_layout.addWidget(self.delimiter_combo, 1, 1)
        options_container_layout.addWidget(self.onset_label, 2, 0)
        options_container_layout.addWidget(self.onset_combo, 2, 1)
        options_container_layout.addWidget(self.offset_label, 3, 0)
        options_container_layout.addWidget(self.offset_combo, 3, 1)
        options_container_layout.addWidget(self.unsure_label, 4, 0)
        options_container_layout.addWidget(self.unsure_combo, 4, 1)
        edit_container_layout.addWidget(self.text_edit_label, 0, 0)
        edit_container_layout.addWidget(self.text_edit, 1, 0)
        edit_container_layout.addWidget(self.error_label, 2, 0)
        edit_container_layout.addWidget(self.table_label, 3, 0)
        edit_container_layout.addWidget(self.table, 4, 0)

        self.layout.addWidget(options_container, 0, 0)
        self.layout.addWidget(edit_container, 0, 1)
        self.layout.addWidget(self.import_button, 1, 0, 1, 2)

    def name_line_changed(self):
        self.name = self.name_line.text()

    def text_edit_changed(self):
        self.text = self.text_edit.toPlainText()
        # detect the delimiter
        self.detect_delimiter()
        self.detect_columns()
        self.populate_table()

    def delimiter_combo_changed(self):
        # update the table and detect the columns
        self.detect_columns()
        self.populate_table()

    def detect_columns(self):
        self.onset_combo.clear()
        self.offset_combo.clear()
        self.unsure_combo.clear()
        self.unsure_combo.addItem("None")
        # get the first line
        line = self.text.split("\n")
        if len(line) < 2:
            return
        # first line is the columns, but skip empty lines
        first_line = next(line for line in line if line)
        # get the columns
        columns = first_line.split(self.get_delimiter())
        for column in columns:
            self.onset_combo.addItem(column)
            self.offset_combo.addItem(column)
            self.unsure_combo.addItem(column)
            if column.lower().__contains__("onset"):
                self.onset_combo.setCurrentText(column)
            if column.lower().__contains__("offset"):
                self.offset_combo.setCurrentText(column)
            if column.lower().__contains__("unsure"):
                self.unsure_combo.setCurrentText(column)

    def populate_table(self):
        # display all of the input in the table given the delimiter
        text = self.text_edit.toPlainText()
        # split the text by newlines
        lines = text.split("\n")
        if len(lines) < 2:
            self.table.clear()
            return
        first_line = next(line for line in lines if line)
        # if the first line is empty, return
        if not first_line:
            return
        else:
            # pop the first line and set it as the headers
            first_line = lines.pop(0)

        # get the delimiter
        delimiter = self.get_delimiter()
        # set the number of columns in the table based on the number of columns detected when splitting the first line by the delimiter
        self.table.setColumnCount(len(first_line.split(delimiter)))
        self.table.setHorizontalHeaderLabels(first_line.split(delimiter))
        # set the number of rows in the table based on the number of lines
        self.table.setRowCount(len(lines))
        # loop through the lines
        for row, line in enumerate(lines):
            # split the line by the delimiter
            columns = line.split(delimiter)
            # loop through the columns
            for column, text in enumerate(columns):
                # create a table item
                item = QtWidgets.QTableWidgetItem(text)
                # set the item in the table
                self.table.setItem(row, column, item)
        # highlight the table
        self.highlight_table()

    def highlight_table(self):
        # loop through the rows
        onset_offset = []
        for row in range(self.table.rowCount()):
            # get the onset and offset items
            onset_item = self.table.item(row, self.onset_combo.currentIndex())
            offset_item = self.table.item(row, self.offset_combo.currentIndex())
            unsure_item = self.table.item(row, self.unsure_combo.currentIndex() - 1)
            if self.unsure_combo.currentText() == "None" or unsure_item is None:
                unsure_item = None
            if onset_item is None or offset_item is None:
                continue
            try:
                self.check_onset_offset(onset_item.text(), offset_item.text())
                # set the background color of the onset item to pastel red
                onset_item.setBackground(QtGui.QColor("#b36868"))
                # set the background color of the offset item to blue
                offset_item.setBackground(QtGui.QColor("#6884b3"))
                if unsure_item is not None:
                    unsure_item.setBackground(QtGui.QColor("#cc8e47"))
                    onset_offset.append(
                        (
                            onset_item.text(),
                            offset_item.text(),
                            unsure_item.text() == "True",
                        )
                    )
                else:
                    onset_offset.append((onset_item.text(), offset_item.text(), False))
                # remove the tooltip
                onset_item.setToolTip("")
                self.error_label.setText("")
                self.import_button.setEnabled(True)
            except ValueError as e:
                # if there is an error, set the background color of the items to red
                onset_item.setBackground(QtGui.QColor("red"))
                offset_item.setBackground(QtGui.QColor("red"))
                # add a tooltip to the items
                onset_item.setToolTip(str(e))
                self.error_label.setText(f"""ERROR AT ROW {row + 1}: {e}""")
                break
            self.onset_offset_unsure = onset_offset

    def detect_delimiter(self):
        """Detect the delimiter based on the input. Will set the delimiter combo box to the detected delimiter"""
        text = self.text_edit.toPlainText()
        # split the text by newlines
        lines = text.split("\n")
        # dict cohmprhension to store the counts of each delimiter
        counts = {delimiter: 0 for delimiter in Delimiters}
        # loop through the delimiters
        for delimiter in Delimiters:
            # count the number of times the delimiter appears in each line
            count = sum(line.count(delimiter.value) for line in lines)
            # append the count to the list
            counts[delimiter] = count
        # get the delimiter that appears the most
        delimiter = max(counts, key=counts.get)
        # set the delimiter combo box to the delimiter
        self.delimiter_combo.setCurrentText(delimiter.name)

    def get_delimiter(self) -> DelimiterValue:
        # get the delimiter from the combo box
        return Delimiters[self.delimiter_combo.currentText()].value

    def parse_input(self):
        # parse the input and display it in the table
        # get the delimiter
        delimiter = self.get_delimiter()
        # split the text by newlines
        lines = self.text.split("\n")
        # get the number of columns
        columns = len(lines[0].split(delimiter))
        # set the number of columns in the table
        self.table.setColumnCount(columns)

    def accept_input(self):
        self.imported.emit()

    def check_onset_offset(self, onset, offset):
        try:
            onset = int(onset)
            offset = int(offset)
        except ValueError:
            raise ValueError(f"""ONSET OR OFFSET IS NOT AN INTEGER""")
        if int(onset) > int(offset):
            raise ValueError(f"""ONSET IS GREATER THAN OFFSET""")
        if int(onset) < 0:
            raise ValueError(f"""ONSET IS LESS THAN 0""")
        if int(offset) < 0:
            raise ValueError(f"""OFFSET IS LESS THAN 0""")
        if int(onset) == int(offset):
            raise ValueError(f"""ONSET AND OFFSET ARE EQUAL""")


class TDTImporter(QtWidgets.QWidget):
    imported = QtCore.Signal()

    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent=parent)
        self.main_win = main_win
        self.onset_offset_unsure: list[tuple[int, int, bool]] = []
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.frame_dict_cache = {}
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

        # a combo box to select the delimiter
        self.delimiter_label = QtWidgets.QLabel("Delimiter")
        self.delimiter_combo = QtWidgets.QComboBox()
        self.delimiter_combo.addItems([delimiter.name for delimiter in Delimiters])
        self.delimiter_combo.setCurrentText("TAB")
        self.delimiter_combo.currentTextChanged.connect(self.delimiter_combo_changed)
        # a text edit to enter in the timestamps
        self.text_edit_label = QtWidgets.QLabel("Enter TDT Timestamps")
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.textChanged.connect(self.text_edit_changed)
        self.text_edit.setAcceptRichText(False)

        # eroor label
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color: red")

        # a combo box to select the onset column
        self.onset_label = QtWidgets.QLabel("Onset Column (RED)")
        self.onset_combo = QtWidgets.QComboBox()
        self.onset_combo.currentTextChanged.connect(self.populate_table)
        # a combo box to select the offset column
        self.offset_label = QtWidgets.QLabel("Offset Column (BLUE)")
        self.offset_combo = QtWidgets.QComboBox()
        self.offset_combo.currentTextChanged.connect(self.populate_table)
        # a combo box to select the unsure column
        self.unsure_label = QtWidgets.QLabel("Unsure Column (YELLOW)")
        self.unsure_combo = QtWidgets.QComboBox()
        self.unsure_combo.addItem("None")
        self.unsure_combo.currentTextChanged.connect(self.populate_table)

        # a table to show the parsed timestamps
        self.table_label = QtWidgets.QLabel("Parsed Timestamps Preview")
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setRowCount(0)

        # a button to accept the input, will set the onset_offset attribute
        self.import_button = QtWidgets.QPushButton("Import")
        self.import_button.clicked.connect(self.accept_input)
        self.import_button.setEnabled(False)

        # all the options on the left, texedit and table on the right
        options_container = QtWidgets.QWidget()
        options_container_layout = QtWidgets.QGridLayout()
        edit_container = QtWidgets.QWidget()
        edit_container_layout = QtWidgets.QGridLayout()
        options_container.setLayout(options_container_layout)
        edit_container.setLayout(edit_container_layout)
        options_container_layout.addWidget(self.name_label, 0, 0)
        options_container_layout.addWidget(self.name_line, 0, 1)
        options_container_layout.addWidget(self.block_label, 1, 0)
        options_container_layout.addWidget(self.block_line, 1, 1)
        options_container_layout.addWidget(self.block_button, 1, 2)
        options_container_layout.addWidget(self.delimiter_label, 2, 0)
        options_container_layout.addWidget(self.delimiter_combo, 2, 1)
        options_container_layout.addWidget(self.onset_label, 3, 0)
        options_container_layout.addWidget(self.onset_combo, 3, 1)
        options_container_layout.addWidget(self.offset_label, 4, 0)
        options_container_layout.addWidget(self.offset_combo, 4, 1)
        options_container_layout.addWidget(self.unsure_label, 5, 0)
        options_container_layout.addWidget(self.unsure_combo, 5, 1)
        edit_container_layout.addWidget(self.text_edit_label, 0, 0)
        edit_container_layout.addWidget(self.text_edit, 1, 0)
        edit_container_layout.addWidget(self.error_label, 2, 0)
        edit_container_layout.addWidget(self.table_label, 3, 0)
        edit_container_layout.addWidget(self.table, 4, 0)

        self.layout.addWidget(options_container, 0, 0)
        self.layout.addWidget(edit_container, 0, 1)
        self.layout.addWidget(self.import_button, 1, 0, 1, 2)

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
        self.main_win.save_settings()
        self.main_win.project_settings.scoring_data.tdt_data = TDTData()
        self.main_win.project_settings.scoring_data.tdt_data.load_from_block(
            loader.block
        )
        self.main_win.project_settings.scoring_data.video_file_location = (
            self.main_win.project_settings.scoring_data.tdt_data.video_path
        )
        self.block_line.setText(
            self.main_win.project_settings.scoring_data.tdt_data.blockname
        )
        self.block_line.setToolTip(
            self.main_win.project_settings.scoring_data.tdt_data.blockpath
        )
        self.main_win.save_settings()
        self.main_win._loaders()

    def name_line_changed(self):
        self.name = self.name_line.text()

    def text_edit_changed(self):
        self.text = self.text_edit.toPlainText()
        # detect the delimiter
        self.detect_delimiter()
        self.detect_columns()
        self.populate_table()

    def delimiter_combo_changed(self):
        # update the table and detect the columns
        self.detect_columns()
        self.populate_table()

    def detect_columns(self):
        self.onset_combo.clear()
        self.offset_combo.clear()
        self.unsure_combo.clear()
        self.unsure_combo.addItem("None")
        # get the first line
        line = self.text.split("\n")
        if len(line) < 2:
            return
        # first line is the columns, but skip empty lines
        first_line = next(line for line in line if line)
        # get the columns
        columns = first_line.split(self.get_delimiter())
        for column in columns:
            self.onset_combo.addItem(column)
            self.offset_combo.addItem(column)
            self.unsure_combo.addItem(column)
            if column.lower().__contains__("onset"):
                self.onset_combo.setCurrentText(column)
            if column.lower().__contains__("offset"):
                self.offset_combo.setCurrentText(column)
            if column.lower().__contains__("unsure"):
                self.unsure_combo.setCurrentText(column)

    def populate_table(self):
        if self.main_win.project_settings.scoring_data.tdt_data is None:
            self.error_label.setText("No TDT Block Loaded")
            return
        # display all of the input in the table given the delimiter
        text = self.text_edit.toPlainText()
        # split the text by newlines
        lines = text.split("\n")
        if len(lines) < 2:
            self.table.clear()
            return
        first_line = next(line for line in lines if line)
        # if the first line is empty, return
        if not first_line:
            return
        else:
            # pop the first line and set it as the headers
            first_line = lines.pop(0)

        # get the delimiter
        delimiter = self.get_delimiter()
        # set the number of columns in the table based on the number of columns detected when splitting the first line by the delimiter
        self.table.setColumnCount(len(first_line.split(delimiter)))
        self.table.setHorizontalHeaderLabels(first_line.split(delimiter))
        # set the number of rows in the table based on the number of lines
        self.table.setRowCount(len(lines))
        # loop through the lines
        for row, line in enumerate(lines):
            # split the line by the delimiter
            columns = line.split(delimiter)
            # loop through the columns
            for column, text in enumerate(columns):
                # create a table item
                try:
                    text = float(text)
                    text = self.convert_tdt_to_frame(text)
                    item = QtWidgets.QTableWidgetItem(text)
                except ValueError:
                    item = QtWidgets.QTableWidgetItem(text)
                # set the item in the table
                self.table.setItem(row, column, item)
        # highlight the table
        self.highlight_table()

    def convert_tdt_to_frame(self, tdt_time: float):
        if self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict is None:
            raise ValueError("No TDT Block Loaded")
        if tdt_time == "nan" or tdt_time == "NaN" or tdt_time == "" or tdt_time == " ":
            return "NaN"
        tdt_time = float(tdt_time)
        if self.frame_dict_cache.get(tdt_time) is None:
            closest_tdt_time = min(
                self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict.values(),
                key=lambda x: abs(x - float(tdt_time)),
            )
            # get the frame gien the tdt time (it's a value in the dict)
            frame = list(
                self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict.keys()
            )[
                list(
                    self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict.values()
                ).index(closest_tdt_time)
            ]
            self.frame_dict_cache[tdt_time] = frame
            return str(frame)
        else:
            return str(self.frame_dict_cache[tdt_time])

    def convert_frame_to_tdt(self, frame: int):
        if self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict is None:
            raise ValueError("No TDT Block Loaded")
        if int(frame) in self.frame_dict_cache.values():
            return list(
                self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict.values()
            )[
                list(
                    self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict.keys()
                ).index(frame)
            ]
        else:
            return "NaN"

    def highlight_table(self):
        # loop through the rows
        onset_offset = []
        for row in range(self.table.rowCount()):
            # get the onset and offset items
            onset_item = self.table.item(row, self.onset_combo.currentIndex())
            offset_item = self.table.item(row, self.offset_combo.currentIndex())
            unsure_item = self.table.item(row, self.unsure_combo.currentIndex() - 1)
            if self.unsure_combo.currentText() == "None" or unsure_item is None:
                unsure_item = None
            if (
                onset_item is None
                or onset_item == ""
                or offset_item is None
                or offset_item == ""
            ):
                continue
            try:
                self.check_onset_offset(onset_item.text(), offset_item.text())
                # set the background color of the onset item to pastel red
                onset_item.setBackground(QtGui.QColor("#b36868"))
                # set the background color of the offset item to blue
                offset_item.setBackground(QtGui.QColor("#6884b3"))
                if unsure_item is not None:
                    unsure_item.setBackground(QtGui.QColor("#cc8e47"))
                    onset_offset.append(
                        (
                            onset_item.text(),
                            offset_item.text(),
                            unsure_item.text().lower() == "true",
                        )
                    )
                else:
                    onset_offset.append((onset_item.text(), offset_item.text(), False))
                # remove the tooltip
                onset_item.setToolTip("")
                self.error_label.setText("")
                self.import_button.setEnabled(True)
            except ValueError as e:
                # if there is an error, set the background color of the items to red
                onset_item.setBackground(QtGui.QColor("red"))
                offset_item.setBackground(QtGui.QColor("red"))
                # add a tooltip to the items
                onset_item.setToolTip(str(e))
                self.error_label.setText(
                    f"""ERROR AT ROW {row + 1}: {e}
ONSET Frame: {onset_item.text()} (TDT: {self.convert_frame_to_tdt(int(onset_item.text()))})
OFFSET Frame: {offset_item.text()} (TDT: {self.convert_frame_to_tdt(int(offset_item.text()))})
"""
                )
                break
            self.onset_offset_unsure = onset_offset

    def detect_delimiter(self):
        """Detect the delimiter based on the input. Will set the delimiter combo box to the detected delimiter"""
        text = self.text_edit.toPlainText()
        # split the text by newlines
        lines = text.split("\n")
        # dict cohmprhension to store the counts of each delimiter
        counts = {delimiter: 0 for delimiter in Delimiters}
        # loop through the delimiters
        for delimiter in Delimiters:
            # count the number of times the delimiter appears in each line
            count = sum(line.count(delimiter.value) for line in lines)
            # append the count to the list
            counts[delimiter] = count
        # get the delimiter that appears the most
        delimiter = max(counts, key=counts.get)
        # set the delimiter combo box to the delimiter
        self.delimiter_combo.setCurrentText(delimiter.name)

    def get_delimiter(self) -> DelimiterValue:
        # get the delimiter from the combo box
        return Delimiters[self.delimiter_combo.currentText()].value

    def parse_input(self):
        # parse the input and display it in the table
        # get the delimiter
        delimiter = self.get_delimiter()
        # split the text by newlines
        lines = self.text.split("\n")
        # get the number of columns
        columns = len(lines[0].split(delimiter))
        # set the number of columns in the table
        self.table.setColumnCount(columns)

    def accept_input(self):
        self.imported.emit()

    def check_onset_offset(self, onset, offset):
        try:
            onset = int(onset)
            offset = int(offset)
        except ValueError:
            raise ValueError(f"""ONSET OR OFFSET IS NOT AN INTEGER""")
        if int(onset) > int(offset):
            raise ValueError(f"""ONSET IS GREATER THAN OFFSET""")
        if int(onset) < 0:
            raise ValueError(f"""ONSET IS LESS THAN 0""")
        if int(offset) < 0:
            raise ValueError(f"""OFFSET IS LESS THAN 0""")
        if int(onset) == int(offset):
            raise ValueError(f"""ONSET AND OFFSET ARE EQUAL""")


class FileImporter(QtWidgets.QWidget):
    imported = QtCore.Signal()

    def __init__(self, file_path=None, main_win=None, parent=None):
        super().__init__(parent=parent)
        self.name = "File Import"
        self.main_win = main_win
        self.file_path = file_path
        self.imported_timestamps = None
        self.onset_offset_unsure: list[tuple[int, int, bool]] = []
        # make like a dialog
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setWindowTitle("Timestamp Importer")
        self.resize(600, 200)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.name_label = QtWidgets.QLabel("Name")
        self.name_line = QtWidgets.QLineEdit(self.name)
        self.name_line.textChanged.connect(self.name_line_changed)

        self.import_file_button = QtWidgets.QPushButton("Select Import File")
        self.import_file_button.clicked.connect(self.import_timestamps_file)
        self.file_line = QtWidgets.QLineEdit()
        self.file_line.setReadOnly(True)

        self.delimiter_label = QtWidgets.QLabel("Delimiter")
        self.delimiter_combo = QtWidgets.QComboBox()
        self.delimiter_combo.addItems([delimiter.name for delimiter in Delimiters])
        self.delimiter_combo.setCurrentText("TAB")
        self.delimiter_combo.currentTextChanged.connect(self.delimiter_combo_changed)

        # a widget containing the onset and offset column selection
        self.column_selection = QtWidgets.QWidget()
        self.column_selection_layout = QtWidgets.QHBoxLayout()
        self.column_selection.setLayout(self.column_selection_layout)
        self.onset_label = QtWidgets.QLabel("Onset Column")
        self.column_selection_layout.addWidget(self.onset_label)
        self.onset_combo = QtWidgets.QComboBox()
        self.column_selection_layout.addWidget(self.onset_combo)

        self.offset_label = QtWidgets.QLabel("Offset Column")
        self.column_selection_layout.addWidget(self.offset_label)
        self.offset_combo = QtWidgets.QComboBox()
        self.column_selection_layout.addWidget(self.offset_combo)

        self.unsure_label = QtWidgets.QLabel("Unsure Column")
        self.column_selection_layout.addWidget(self.unsure_label)
        self.unsure_combo = QtWidgets.QComboBox()
        self.unsure_combo.addItem("None")
        self.column_selection_layout.addWidget(self.unsure_combo)

        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color: red")

        self.table_label = QtWidgets.QLabel("Parsed Timestamps Preview")
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setRowCount(0)

        # import button
        self.import_button = QtWidgets.QPushButton("Import")
        self.import_button.clicked.connect(self.import_timestamps)
        self.import_button.setEnabled(False)

        self.layout.addWidget(self.name_label, 0, 0)
        self.layout.addWidget(self.name_line, 0, 1)
        self.layout.addWidget(self.import_file_button, 1, 0)
        self.layout.addWidget(self.file_line, 1, 1)
        self.layout.addWidget(self.delimiter_label, 2, 0)
        self.layout.addWidget(self.delimiter_combo, 2, 1)
        self.layout.addWidget(self.column_selection, 3, 0, 1, 2)
        self.layout.addWidget(self.error_label, 4, 0, 1, 2)
        self.layout.addWidget(self.table_label, 5, 0, 1, 2)
        self.layout.addWidget(self.table, 6, 0, 1, 2)
        self.layout.addWidget(self.import_button, 7, 0, 1, 2)

        if self.file_path:
            self.import_timestamps_file()

    def name_line_changed(self):
        self.name = self.name_line.text()

    def delimiter_combo_changed(self):
        # update the table and detect the columns
        self.imported_timestamps = pd.read_csv(
            self.file_path,
            delimiter=Delimiters[self.delimiter_combo.currentText()].value,
        )
        self.detect_columns()
        self.populate_table()

    def detect_delimiter(self, text: str) -> DelimiterValue:
        """Detect the delimiter based on the input. Will set the delimiter combo box to the detected delimiter"""
        # split the text by newlines
        lines = text.split("\n")
        # dict cohmprhension to store the counts of each delimiter
        counts = {delimiter: 0 for delimiter in Delimiters}
        # loop through the delimiters
        for delimiter in Delimiters:
            # count the number of times the delimiter appears in each line
            count = sum(line.count(delimiter.value) for line in lines)
            # append the count to the list
            counts[delimiter] = count
        # get the delimiter that appears the most
        delimiter = max(counts, key=counts.get)
        # set the delimiter combo box to the delimiter
        self.delimiter_combo.setCurrentText(delimiter.name)

    def import_timestamps(self):
        if self.imported_timestamps is None:
            return
        onset_column = self.onset_combo.currentText()
        offset_column = self.offset_combo.currentText()
        unsure_column = self.unsure_combo.currentText()
        if unsure_column == "None":
            self.onset_offset_unsure = list(
                zip(
                    self.imported_timestamps[onset_column],
                    self.imported_timestamps[offset_column],
                    [False] * len(self.imported_timestamps),
                )
            )
        else:
            self.onset_offset_unsure = list(
                zip(
                    self.imported_timestamps[onset_column],
                    self.imported_timestamps[offset_column],
                    self.imported_timestamps[unsure_column],
                )
            )
        try:
            for onset, offset, unsure in self.onset_offset_unsure:
                self.check_onset_offset(onset, offset)
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.imported.emit()

    def import_timestamps_file(self):
        self.file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Timestamp File", "", "CSV (*.csv)"
        )
        if self.file_path:
            self.file_line.setText(self.file_path)
            self.name_line.setText(self.file_path.split("/")[-1].split(".")[0])
            try:
                with open(self.file_path, "r") as f:
                    text = f.read()
                    delimeter = self.detect_delimiter(text)
                self.imported_timestamps = pd.read_csv(
                    self.file_path, delimiter=delimeter
                )
                self.detect_columns()
                self.populate_table()
            except Exception as e:
                self.error_label.setText(str(e))
                self.imported_timestamps = None
                self.file_path = None
                self.file_line.clear()
                self.onset_combo.clear()
                self.offset_combo.clear()
                self.unsure_combo.clear()
                self.unsure_combo.addItem("None")
                self.onset_offset_unsure = None
                self.table.clear()
                self.error_label.setText("")
                return

    def populate_table(self):
        if self.imported_timestamps is None:
            return

        # set the number of columns in the table based on the number of columns detected when splitting the first line by the delimiter
        self.table.setColumnCount(len(self.imported_timestamps.columns))
        self.table.setHorizontalHeaderLabels(self.imported_timestamps.columns)
        # set the number of rows in the table based on the number of lines
        self.table.setRowCount(len(self.imported_timestamps))
        # loop through the rows
        for row in range(self.table.rowCount()):
            # loop through the columns
            for column in range(self.table.columnCount()):
                # create a table item
                item = QtWidgets.QTableWidgetItem(
                    str(self.imported_timestamps.iloc[row, column])
                )
                # set the item in the table
                self.table.setItem(row, column, item)

        # highlight the table
        self.highlight_table()

    def highlight_table(self):
        # loop through the rows
        onset_offset = []
        for row in range(self.table.rowCount()):
            # get the onset and offset items
            onset_item = self.table.item(row, self.onset_combo.currentIndex())
            offset_item = self.table.item(row, self.offset_combo.currentIndex())
            unsure_item = self.table.item(row, self.unsure_combo.currentIndex() - 1)
            if self.unsure_combo.currentText() == "None" or unsure_item is None:
                unsure_item = None
            if onset_item is None or offset_item is None:
                continue
            try:
                self.check_onset_offset(onset_item.text(), offset_item.text())
                # set the background color of the onset item to pastel red
                onset_item.setBackground(QtGui.QColor("#b36868"))
                # set the background color of the offset item to blue
                offset_item.setBackground(QtGui.QColor("#6884b3"))
                if unsure_item is not None:
                    unsure_item.setBackground(QtGui.QColor("#cc8e47"))
                    onset_offset.append(
                        (
                            onset_item.text(),
                            offset_item.text(),
                            unsure_item.text() == "True",
                        )
                    )
                else:
                    onset_offset.append((onset_item.text(), offset_item.text(), False))
                # remove the tooltip
                onset_item.setToolTip("")
                self.error_label.setText("")
                # enable the import button
                self.import_button.setEnabled(True)
            except ValueError as e:
                # if there is an error, set the background color of the items to red
                onset_item.setBackground(QtGui.QColor("red"))
                offset_item.setBackground(QtGui.QColor("red"))
                # add a tooltip to the items
                onset_item.setToolTip(str(e))
                self.error_label.setText(
                    f"""ERROR AT ROW {row + 1}: {e}
ONSET: {onset_item.text()}
OFFSET: {offset_item.text()}
"""
                )
                break

    def detect_columns(self):
        self.onset_combo.clear()
        self.offset_combo.clear()
        self.unsure_combo.clear()
        self.unsure_combo.addItem("None")
        for column in self.imported_timestamps.columns:
            self.onset_combo.addItem(column)
            self.offset_combo.addItem(column)
            self.unsure_combo.addItem(column)
            if column.lower().__contains__("onset"):
                self.onset_combo.setCurrentText(column)
            if column.lower().__contains__("offset"):
                self.offset_combo.setCurrentText(column)
            if column.lower().__contains__("unsure"):
                self.unsure_combo.setCurrentText(column)

    def check_onset_offset(self, onset, offset):
        try:
            onset = int(onset)
            offset = int(offset)
        except ValueError:
            raise ValueError(f"""ONSET OR OFFSET IS NOT AN INTEGER""")
        if int(onset) > int(offset):
            raise ValueError(f"""ONSET IS GREATER THAN OFFSET""")
        if int(onset) < 0:
            raise ValueError(f"""ONSET IS LESS THAN 0""")
        if int(offset) < 0:
            raise ValueError(f"""OFFSET IS LESS THAN 0""")
        if int(onset) == int(offset):
            raise ValueError(f"""ONSET AND OFFSET ARE EQUAL""")


class TimestampsImporter(QtWidgets.QDialog):
    """A widget with tabs to import timestamps from a file or manually"""

    imported = QtCore.Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.setWindowTitle("Timestamp Importer")
        self.resize(600, 400)

        self.tab_widget = QtWidgets.QTabWidget()
        self.file_importer = FileImporter()
        self.manual_importer = ManualImporter(self.parent())
        self.tdt_importer = TDTImporter(self.parent())
        self.tab_widget.addTab(self.file_importer, "File")
        self.tab_widget.addTab(self.manual_importer, "Manual")
        self.tab_widget.addTab(self.tdt_importer, "TDT")

        self.layout.addWidget(self.tab_widget, 0, 0, 1, 2)
        self.layout.setRowStretch(0, 1)
        self.layout.setColumnStretch(0, 1)

        self.manual_importer.imported.connect(self.manual_import)
        self.file_importer.imported.connect(self.file_import)
        self.tdt_importer.imported.connect(self.tdt_import)

    def manual_import(self):
        if self.manual_importer.onset_offset_unsure is None:
            return
        self.imported.emit(
            self.manual_importer.name, self.manual_importer.onset_offset_unsure
        )
        self.accept()

    def file_import(self):
        if self.file_importer.onset_offset_unsure is None:
            return
        self.imported.emit(
            self.file_importer.name, self.file_importer.onset_offset_unsure
        )
        self.accept()

    def tdt_import(self):
        if self.tdt_importer.onset_offset_unsure is None:
            return
        self.imported.emit(
            self.tdt_importer.name, self.tdt_importer.onset_offset_unsure
        )
        self.accept()

    def check_onset_offset(self):
        self.manual_importer.check_onset_offset()
        self.file_importer.check_onset_offset()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication([])
    win = TimestampsImporter()
    win.show()
    sys.exit(app.exec())
