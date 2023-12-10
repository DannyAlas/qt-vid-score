import json
import os
from turtle import st
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Tuple, Union

from qtpy import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from video_scoring import MainWindow


class OnsetOffset(dict):
    """
    Represents a dictionary of onset and offset frames. Provides methods to add a new entry with checks for overlap. Handels sorting.

    Notes
    -----
    The Key is the onset frame and the value is a dict with the keys "offset", "sure", and "notes". The value of "offset" is the offset frame. The value of "sure" is a bool indicating if the onset-offset pair is sure. The value of "notes" is a string.

    We only store frames in the dict. The conversion to a time is handled by the UI. We will always store the onset and offset as frames.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._onset_offset = {}

    def __setitem__(self, key, value):
        # check if the key is a frame number
        if not isinstance(key, int):
            raise TypeError("The key must be an integer")

        # check if the value is a dict
        if not isinstance(value, dict):
            raise TypeError("The value must be a dict")

        # check if the value has the correct keys
        if not all(key in value.keys() for key in ["offset", "sure", "notes"]):
            raise ValueError(
                'The value must have the keys "offset", "sure", and "notes"'
            )

        # check if the offset is a frame number
        if value["offset"] is not None and not isinstance(value["offset"], int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if not isinstance(value["sure"], bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if not isinstance(value["notes"], str):
            raise TypeError("The notes value must be a string")

        # check if the onset is already in the dict
        if key in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

    def add_onset(self, onset, offset=None, sure=None, notes=None):
        # check if the onset is already in the dict
        if onset in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

        # check if the offset is a frame number
        if offset is not None and not isinstance(offset, int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if sure is not None and not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if notes is not None and not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # check for overlap
        self._check_overlap(onset=onset, offset=offset)

        # sort dict by onset
        self._onset_offset = dict(
            sorted(self._onset_offset.items(), key=lambda x: x[0])
        )

    def _check_overlap(self, onset, offset=None):
        """
        Check if the provided onset and offset times overlap with any existing ranges.

        Parameters
        ----------
        onset : int
            The onset frame.
        offset : int, optional
            The offset frame, by default None.

        Raises
        ------
        ValueError
            If there is an overlap.
        """

        # If we are adding a new onset, check if it will overlap with any existing onset - offset ranges
        if offset is None:
            for n_onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if onset >= n_onset and onset <= entry["offset"]:
                    raise ValueError(
                        f"The provided onset time of {onset} overlaps with an existing range: {n_onset} - {entry['offset']}"
                    )

        if offset is not None:
            if offset <= onset:
                raise ValueError(
                    f"The provided offset frame of {offset} is before the onset frame of {onset}"
                )
            for onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if offset >= onset and offset <= entry["offset"]:
                    raise ValueError(
                        f"The provided offset time of {offset} overlaps with an existing range: {onset} - {entry['offset']}"
                    )


class customTableWidget(QtWidgets.QTableWidget):
    """A a custom table widget that adds a border around selected rows"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

    def selectionChanged(self, selected, deselected):
        """When a row is selected, add a border around it"""
        super().selectionChanged(selected, deselected)
        self.viewport().update()

    def paintEvent(self, event):
        """Paint the border around the selected row"""
        super().paintEvent(event)
        if self.selectionModel() is not None:
            for row in range(self.rowCount()):
                if self.isRowSelected(row):
                    option = QtWidgets.QStyleOptionFrame()
                    option.initFrom(self)
                    painter = QtGui.QPainter(self.viewport())
                    option.lineWidth = 10
                    style = QtWidgets.QApplication.style()
                    # get the size of the row
                    rect = style.subElementRect(
                        QtWidgets.QStyle.SubElement.SE_ItemViewItemFocusRect,
                        option,
                        self,
                    )
                    # set the size of the border
                    rect.setLeft(0)
                    rect.setRight(self.viewport().width())
                    rect.setTop(rect.top() + 5)
                    rect.setBottom(rect.bottom() - 5)
                    # set the color to red
                    option.palette.setColor(
                        QtGui.QPalette.WindowText, QtGui.QColor("red")
                    )
                    # draw the border
                    style.drawPrimitive(
                        QtWidgets.QStyle.PrimitiveElement.PE_PanelItemViewItem,
                        option,
                        painter,
                        self,
                    )
                    style.drawControl(
                        QtWidgets.QStyle.ControlElement.CE_ItemViewItem, option, painter
                    )

    def isRowSelected(self, row):
        """Check if a row is selected"""
        model = self.selectionModel()
        return model is not None and model.isRowSelected(row, QtCore.QModelIndex())


class TsWidget(QtWidgets.QWidget):
    def __init__(self, main_win: "MainWindow", ts_dw: "TimeStampsDockwidget"):
        super().__init__()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_win = main_win
        self.ts_dw = ts_dw
        # UI Elements
        self.setWindowTitle("Video Behavior Tracker")
        self.layout = QtWidgets.QVBoxLayout()

        # Table to display timestamps
        self.table = customTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Onset", "Offset"])
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        # not editable
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems
        )

        self.main_win.loaded.connect(self.init_connections)

        self.layout.addWidget(self.table)

        self.setLayout(self.layout)

    def init_connections(self):
        self.table.itemSelectionChanged.connect(self.on_row_selected)

    def on_row_selected(self):
        item = self.table.selectedItems()
        if len(item) == 0:
            return
        # if the item is in the onset column, move the playhead to the onset
        if item[0].column() == 0:
            self.main_win.timeline_dw.timeline_view.move_playhead_to_frame(
                int(item[0].text())
            )
        # if the item is in the offset column, move the playhead to the offset
        elif item[0].column() == 1:
            self.main_win.timeline_dw.timeline_view.move_playhead_to_frame(
                int(item[0].text())
            )

    def update(self):
        """Update the table with the timestamps"""
        # clear the table
        if len(self.main_win.timeline_dw.timeline_view.behavior_tracks) == 0:
            return
        ts_behaviors = self.main_win.timeline_dw.timeline_view.behavior_tracks[
            self.ts_dw.behavior_track_combo.currentIndex()
        ].behavior_items
        ts_behaviors_sorted = dict(sorted(ts_behaviors.items(), key=lambda x: x[0]))
        tb_onsets = [str(onset) for onset in ts_behaviors_sorted.keys()]
        tb_offsets = [str(item.offset) for item in ts_behaviors_sorted.values()]
        self.table.clearContents()
        self.table.setRowCount(0)
        for onset, item in ts_behaviors_sorted.items():
            # add the onset to the table
            self.table.insertRow(self.table.rowCount())
            onset_item = QtWidgets.QTableWidgetItem(str(onset))
            self.table.setItem(self.table.rowCount() - 1, 0, onset_item)
            # add the offset to the table
            offset_item = QtWidgets.QTableWidgetItem(str(item.offset))
            self.table.setItem(self.table.rowCount() - 1, 1, offset_item)
            # scroll to the item if it has changed from the previous update
            if len(tb_onsets) == 0 or len(tb_offsets) == 0:
                self.table.scrollToItem(onset_item)
            elif str(onset) not in tb_onsets or str(item.offset) not in tb_offsets:
                self.table.scrollToItem(onset_item)


class TimeStampsDockwidget(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Time Stamps")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_win = main_win
        self.main_widget = QtWidgets.QWidget()
        self.setWidget(self.main_widget)
        # add toolbar
        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(1)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.toolbar)

        # add a save button
        self.save_act = QtWidgets.QAction(
            self.main_win._get_icon("diskette.png"), "Save", self
        )
        self.save_act.triggered.connect(self.save)
        self.toolbar.addAction(self.save_act)
        # add dropdown to select the behavior track
        self.behavior_track_combo = QtWidgets.QComboBox()
        self.behavior_track_combo.currentTextChanged.connect(self.update)
        self.toolbar.addWidget(self.behavior_track_combo)
        # add spacer
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.toolbar.addWidget(spacer)
        # add an update button
        self.update_act = QtWidgets.QAction(
            self.main_win._get_icon("refresh.svg", svg=True), "Refresh", self
        )
        self.update_act.triggered.connect(self.refresh)
        self.toolbar.addAction(self.update_act)

        self.table_widget = TsWidget(self.main_win, self)
        self.main_layout.addWidget(self.table_widget)
        self.main_win.loaded.connect(self.init_connections)

    def init_connections(self):
        self.main_win.timeline_dw.timeline_view.behavior_tracks_changed.connect(
            self.update_tracks
        )
        self.update()

    def update_tracks(self):
        self.behavior_track_combo.clear()
        for track in self.main_win.timeline_dw.timeline_view.behavior_tracks:
            self.behavior_track_combo.addItem(track.name)

    def update(self):
        self.table_widget.update()

    def refresh(self):
        self.update_tracks()
        self.table_widget.update()

    def save(self):
        # save the table to a csv file
        # get the file path
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Timestamps",
            self.behavior_track_combo.currentText() + "_timestamps.csv",
            "CSV (*.csv)",
        )
        if file_path == "":
            return
        # save the file path
        self.main_win.project_settings.timestamp_file_location = file_path
        # save the table
        with open(file_path, "w") as f:
            # write the header
            f.write("Onset,Offset\n")
            # write the data
            for row in range(self.table_widget.table.rowCount()):
                onset = self.table_widget.table.item(row, 0).text()
                offset = self.table_widget.table.item(row, 1).text()
                f.write(f"{onset},{offset}\n")
        # show a message box
        self.main_win.statusBar().showMessage(f"Saved timestamps to {file_path}")

    def load_from_csv(self, file_path):
        """Load timestamps from a csv file"""
        # load the file
        with open(file_path, "r") as f:
            # skip the header
            f.readline()
            # read the data
            data = f.readlines()
        # if the first line contains "Onset,Offset", skip it
        if data[0].strip() == "Onset,Offset":
            data = data[1:]
        # clear the table
        self.table_widget.table.clearContents()
        self.table_widget.table.setRowCount(0)
        # add the data to the table
        for line in data:
            onset, offset = line.strip().split(",")
            self.table_widget.table.insertRow(self.table_widget.table.rowCount())
            onset_item = QtWidgets.QTableWidgetItem(onset)
            self.table_widget.table.setItem(
                self.table_widget.table.rowCount() - 1, 0, onset_item
            )
            offset_item = QtWidgets.QTableWidgetItem(offset)
            self.table_widget.table.setItem(
                self.table_widget.table.rowCount() - 1, 1, offset_item
            )
        # save the file path
        self.main_win.project_settings.timestamp_file_location = file_path
        # show a message box
        self.main_win.statusBar().showMessage(f"Loaded timestamps from {file_path}")
