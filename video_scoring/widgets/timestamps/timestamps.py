import json
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
        if not all(
            key in value.keys() for key in ["offset", "sure", "notes"]
        ):
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
        self._onset_offset = dict(sorted(self._onset_offset.items(), key=lambda x: x[0]))

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
    def __init__(self, main_win: "MainWindow"):
        super().__init__()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_win = main_win
        self.timestamps: Dict[float, Dict[str, Any]] = {}
        self.show_tpye: Literal["frame", "time"] = "frame"
        self._current_onset = None

        # UI Elements
        self.setWindowTitle("Video Behavior Tracker")
        self.layout = QtWidgets.QVBoxLayout()

        # Table to display timestamps
        self.table = customTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Onset", "Offset", "Sure", "Notes"])
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
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.layout.addWidget(self.table)

        # Add Buttons
        self.onset_button = QtWidgets.QPushButton("Add Onset")
        self.onset_button.clicked.connect(self.add_onset)
        self.layout.addWidget(self.onset_button)

        # custom context menu for table
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        # when a row is selcted set the current onset to the onset time of the row
        self.table.itemSelectionChanged.connect(self._set_current_onset)

        # if we don't click on a row, unselect the current selection and set the current onset to None
        self.table.itemClicked.connect(self._row_selector)
        self.setLayout(self.layout)

    @property
    def current_onset(self):
        return self._current_onset

    @current_onset.setter
    def current_onset(self, value):
        # if we're setting the current onset to None, we're done other wise highlight the row
        if value is None:
            self._current_onset = None
            return
        try:
            # get the row index of the onset
            row = self.table.findItems(str(value), QtCore.Qt.MatchFlag.MatchExactly)[
                0
            ].row()
            # select the row
            self.table.selectRow(row)
        except IndexError:
            pass
        # set the current onset
        self._current_onset = value

    def _row_selector(self, item):
        # if we clicked on a row highlight it and set the current onset to the onset time of the row
        if item.row() != -1:
            self.table.selectRow(item.row())
            self._set_current_onset()

        # otherwise unselect the current row and set the current onset to None
        self.table.clearSelection()
        self._current_onset = None
        # remove focus from table
        self.table.setFocus()

    def _set_current_onset(self):
        # get the row index of the onset
        row = self.table.currentRow()
        # get the onset time
        onset_time = float(self.table.item(row, 0).text())
        # set the current onset
        self._current_onset = onset_time

    def _check_overlap(self, new_onset=None, new_offset=None, current_onset=None):
        """
        Check if the provided onset and offset times overlap with any existing ranges.

        Parameters
        ----------
        new_onset : float, optional
            by default None
        new_offset : float, optional
            by default None

        Returns
        -------
        Is there overlap? : bool
            True if there is an overlap, False otherwise.
        The overlap message : str
        """
        # If we are adding a new onset, check if it will overlap with any existing onset - offset ranges
        if new_onset is not None and new_offset is None:
            for onset, entry in self.timestamps.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if new_onset >= onset and new_onset <= entry["offset"]:
                    return (
                        True,
                        f"The provided onset time of {new_onset} overlaps with an existing range: {onset} - {entry['offset']}",
                    )

        if current_onset is not None and new_offset is not None:
            if new_offset <= current_onset:
                return (
                    True,
                    f"The provided offset time of {new_offset} is before the current onset time of {current_onset}",
                )
            for onset, entry in self.timestamps.items():
                # some entries may not have an offset yet
                if current_onset < onset and new_offset > onset:
                    return (
                        True,
                        f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}",
                    )
                elif entry["offset"] is None:
                    continue
                elif new_offset >= onset and new_offset <= entry["offset"]:
                    return (
                        True,
                        f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}",
                    )

        elif new_onset is None and new_offset is not None:
            for onset, entry in self.timestamps.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if new_offset >= onset and new_offset <= entry["offset"]:
                    return (
                        True,
                        f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}",
                    )

        return False, None

    def _table_context_menu(self, position):
        # create context menu
        menu = QtWidgets.QMenu()
        # if we're not on a row, show only add onset
        if self.table.currentRow() == -1:
            save_timestamp_action = menu.addAction("Add Onset")
            save_timestamp_action.triggered.connect(self.add_onset)
            menu.exec_(self.table.viewport().mapToGlobal(position))
            return

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_timestamp)

        # show context menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def add_timestamp(self, timestamp):
        # determine if we are adding an onset or offset
        if self.current_onset is None:
            # add onset
            self.add_onset(onset_time=timestamp)
        else:
            # add offset
            self.add_offset(onset_time=self.current_onset, offset_time=timestamp)

    def add_onset(self, onset_time=None):
        if onset_time is None:
            # open dialog to get onset time
            onset_time, ok = QtWidgets.QInputDialog.getDouble(
                self, "Onset Time", "Enter onset time (seconds):"
            )
            if not ok:
                return

        overlap, er_msg = self._check_overlap(new_onset=onset_time)
        if overlap:
            # display error message
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText("Overlap Error")
            msg.setInformativeText(er_msg)
            msg.setWindowTitle("Error")
            msg.exec_()
            return

        # add onset time to timestamps
        self.timestamps[float(onset_time)] = {"offset": None, "sure": None, "notes": None}
        self.current_onset = onset_time
        # update table
        self.update_table()

    def add_offset(self, onset_time, offset_time=None):
        # open dialog to get offset time
        if offset_time is None:
            offset_time, ok = QtWidgets.QInputDialog.getDouble(
                self, "Offset Time", "Enter offset time (seconds):"
            )
            if not ok:
                return
        overlap, er_msg = self._check_overlap(
            current_onset=onset_time, new_offset=offset_time
        )
        if overlap:
            # display error message
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setText("Overlap Error")
            msg.setInformativeText(er_msg)
            msg.setWindowTitle("Error")
            msg.exec_()
            return

        self.timestamps[float(onset_time)]["offset"] = offset_time
        self.current_onset = None
        # update table
        self.update_table()

    # def delete_selected_timestamp(self):
    #     # get selected row
    #     selected_row = self.table.currentRow()

    #     # get onset time from selected row
        
    #     entry = self.get_entry_from_onset_text(self.table.item(selected_row, 0).text())
    #     # delete entry
    #     del entry

    #     # update table
    #     self.update_table()

    def get_entry_from_onset_text(self, onset_time: str):
        if self.show_tpye == "frame":
            return self.timestamps[onset_time]
        elif self.show_tpye == "time":
            return self.timestamps[self.time_to_frame(float(onset_time))]

    def time_to_frame(self, timestamp):
        # frame_ts is a dict of {frame_num: timestamp}
        # we want to get the frame number associated with the timestamp
        fts = self.main_win.video_player_dw.video_widget.play_worker.vc.video.frame_ts
        # get all the values from the dict
        values = list(fts.values())
        # get the index of the timestamp
        index = values.index(timestamp)
        # get the key of the timestamp
        frame_num = list(fts.keys())[index]
        return frame_num

    def frame_to_time(self, frame_num):
        # frame_ts is a dict of {frame_num: timestamp}
        fts = self.main_win.video_player_dw.video_widget.play_worker.vc.video.frame_ts
        return fts[frame_num]

    def update_table(self):
        # clear table
        self.table.clearContents()

        # sort timestamps by onset time
        sorted_timestamps = sorted(self.timestamps.items(), key=lambda x: x[0])

        # add rows to table
        self.table.setRowCount(len(sorted_timestamps))
        for i, (onset, entry) in enumerate(sorted_timestamps):
            # onset time
            if self.show_tpye == "frame":
                item = QtWidgets.QTableWidgetItem(str(onset))
            elif self.show_tpye == "time":
                item = QtWidgets.QTableWidgetItem(
                    str(self.frame_to_time(onset))
                )
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, item)

            # offset time
            if entry["offset"] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry["offset"]))
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, 1, item)

            # sure
            if entry["sure"] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry["sure"]))
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, 2, item)

            # notes
            if entry["notes"] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry["notes"]))
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, 3, item)

        # resize columns
        self.table.resizeColumnsToContents()


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
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.toolbar)

        self.table_widget = TsWidget(self.main_win)
        self.main_layout.addWidget(self.table_widget)
        self.add_toolbar_actions()

    def add_toolbar_actions(self):
        # add actions
        self.save_timestamp_action = QtWidgets.QAction(self.main_win._get_icon("brackets.png"), "Save Timestamp", self)
        self.save_timestamp_action.triggered.connect(lambda: self.add_vid_time_stamp(self.main_win.get_frame_num()))
        self.toolbar.addAction(self.save_timestamp_action)
        # set tooltip
        self.save_timestamp_action.setToolTip(f"{self.main_win.project_settings.key_bindings.help_text().get('save_timestamp')} `{self.main_win.project_settings.key_bindings.save_timestamp}`")

        # a dropdown menu for showing the different types of timestamps [frame, time]
        self.ts_type_combo = QtWidgets.QComboBox()
        self.ts_type_combo.addItems(["Frame", "Time"])
        self.ts_type_combo.currentTextChanged.connect(self._ts_type_changed)
        self.toolbar.addWidget(self.ts_type_combo)

    def _ts_type_changed(self, ts_type):
        # iterate over the timestamps and convert them to the new type
        for onset, entry in self.table_widget.timestamps.items():
            if ts_type == "Frame":
                # convert to frame
                # get the frame number associated with the onset
                entry["offset"] = self.timestamp_to_frame(entry["offset"])

            elif ts_type == "Time":
                # convert to time
                entry["offset"] = self.frame_to_timestamp(entry["offset"])

    def add_vid_time_stamp(self, frame_num):
        # frame_num = self.main_win.get_frame_num()
        # if frame_num is None:
        #     return

        self.table_widget.add_timestamp(frame_num)

    # def delete_selected_timestamp(self):
    #     self.table_widget.delete_selected_timestamp()

    def set_player_to_selected_timestamp(self):
        # get selected row
        
        selected_row = self.table_widget.table.currentRow()

        # get onset time from selected row
        onset_time = float(self.table_widget.table.item(selected_row, 0).text())

        # get if the ts is a frame or time
        ts_type = self.main_win.project_settings.scoring.save_frame_or_time
        if ts_type == "frame":
            self.main_win.video_player_dw.seek(onset_time)
        elif ts_type == "timestamp":
            self.main_win.video_player_dw.seek(self.timestamp_to_frame(onset_time))

    def timestamp_to_frame(self, timestamp):
        # frame_ts is a dict of {frame_num: timestamp}
        # we want to get the frame number associated with the timestamp
        fts = self.main_win.video_player_dw.video_widget.play_worker.vc.video.frame_ts
        # get all the values from the dict
        values = list(fts.values())
        # get the index of the timestamp
        index = values.index(timestamp)
        # get the key of the timestamp
        frame_num = list(fts.keys())[index]
        return frame_num        

    def frame_to_timestamp(self, frame_num):
        # frame_ts is a dict of {frame_num: timestamp}
        fts = self.main_win.video_player_dw.video_widget.play_worker.vc.video.frame_ts
        return fts[frame_num]
        
    # def import_ts(self, ts):
    #     del self.time_stamps_tree_view
    #     self.time_stamps_tree_view = TimeStampsTreeView(ts_type="On/Off")
    #     self.main_layout.addWidget(self.time_stamps_tree_view)
    #     self.time_stamps_tree_view.add_time_stamps(ts)
