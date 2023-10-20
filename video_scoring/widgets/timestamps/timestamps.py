from typing import Any, Dict, List, Tuple, Union, Literal, TYPE_CHECKING
from qtpy import QtCore, QtWidgets, QtGui
import json

if TYPE_CHECKING:
    from video_scoring import MainWindow

class customTableWidget(QtWidgets.QTableWidget):
    """A a custom table widget that adds a border around selected rows"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

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
                    rect = style.subElementRect(QtWidgets.QStyle.SE_ItemViewItemDecoration, option, self)
                    # set the size of the border
                    rect.setLeft(0)
                    rect.setRight(self.viewport().width())
                    rect.setTop(rect.top() + 5)
                    rect.setBottom(rect.bottom() - 5)
                    # set the color to red
                    option.palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('red'))
                    # draw the border
                    style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, option, painter, self)
                    
                    
                   
                    

    def isRowSelected(self, row):
        """Check if a row is selected"""
        model = self.selectionModel()
        return model is not None and model.isRowSelected(row, QtCore.QModelIndex())
    

class TsWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.timestamps = {} 
        self._current_onset = None

        # UI Elements
        self.setWindowTitle('Video Behavior Tracker')
        self.layout = QtWidgets.QVBoxLayout()

        # Table to display timestamps
        self.table = customTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Onset', 'Offset', 'Sure', 'Notes'])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        # not editable
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        self.layout.addWidget(self.table)

        # Add Buttons
        self.onset_button = QtWidgets.QPushButton('Add Onset')
        self.onset_button.clicked.connect(self.add_onset)
        self.layout.addWidget(self.onset_button)

        # custom context menu for table
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
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
            row = self.table.findItems(str(value), QtCore.Qt.MatchExactly)[0].row()
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
                if entry['offset'] is None:
                    continue
                if new_onset >= onset and new_onset <= entry['offset']:
                    return True, f"The provided onset time of {new_onset} overlaps with an existing range: {onset} - {entry['offset']}"

        if current_onset is not None and new_offset is not None:
            if new_offset <= current_onset:
                return True, f"The provided offset time of {new_offset} is before the current onset time of {current_onset}"
            for onset, entry in self.timestamps.items():
                # some entries may not have an offset yet
                if current_onset < onset and new_offset > onset:
                    return True, f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}"
                elif entry['offset'] is None:
                    continue
                elif new_offset >= onset and new_offset <= entry['offset']:
                    return True, f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}"
                
        elif new_onset is None and new_offset is not None:
                for onset, entry in self.timestamps.items():
                    # some entries may not have an offset yet
                    if entry['offset'] is None:
                        continue
                    if new_offset >= onset and new_offset <= entry['offset']:
                        return True, f"The provided offset time of {new_offset} overlaps with an existing range: {onset} - {entry['offset']}"
                    

        return False, None

    def _table_context_menu(self, position):
        # create context menu
        menu = QtWidgets.QMenu()
        # if we're not on a row, show only add onset
        if self.table.currentRow() == -1:
            add_onset_action = menu.addAction('Add Onset')
            add_onset_action.triggered.connect(self.add_onset)
            menu.exec_(self.table.viewport().mapToGlobal(position))
            return
        
        add_offset_action = menu.addAction('Add Offset')
        add_offset_action.triggered.connect(self._add_offset_from_context_menu)
        add_sure_action = menu.addAction('Add Sure')
        add_sure_action.triggered.connect(self._add_sure_from_context_menu)
        add_notes_action = menu.addAction('Add Notes')
        add_notes_action.triggered.connect(self._add_notes_from_context_menu)
        menu.addSeparator()
        delete_action = menu.addAction('Delete')
        delete_action.triggered.connect(self._delete_from_context_menu)

        # show context menu
        menu.exec_(self.table.viewport().mapToGlobal(position))

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
            onset_time, ok = QtWidgets.QInputDialog.getDouble(self, 'Onset Time', 'Enter onset time (seconds):')
            if not ok:
                return
        
        overlap, er_msg = self._check_overlap(new_onset=onset_time)
        if overlap:
            # display error message
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText('Overlap Error')
            msg.setInformativeText(er_msg)
            msg.setWindowTitle('Error')
            msg.exec_()
            return

        # add onset time to timestamps
        self.timestamps[onset_time] = {'offset': None, 'sure': None, 'notes': None}
        self.current_onset = onset_time
        # update table
        self.update_table()

    def add_offset(self, onset_time, offset_time=None):
        # open dialog to get offset time
        if offset_time is None:
            offset_time, ok = QtWidgets.QInputDialog.getDouble(self, 'Offset Time', 'Enter offset time (seconds):')
            if not ok:
                return
        overlap, er_msg = self._check_overlap(current_onset=onset_time, new_offset=offset_time)
        if overlap:
            # display error message
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText('Overlap Error')
            msg.setInformativeText(er_msg)
            msg.setWindowTitle('Error')
            msg.exec_()
            return

        self.timestamps[onset_time]['offset'] = offset_time
        self.current_onset = None
        # update table
        self.update_table()

    def _add_offset_from_context_menu(self):
        # get selected row
        selected_row = self.table.currentRow()

        # get onset time from selected row
        onset_time = float(self.table.item(selected_row, 0).text())

        # add offset
        self.add_offset(onset_time=onset_time)

    def _add_sure_from_context_menu(self):
        # get selected row
        selected_row = self.table.currentRow()

        # get onset time from selected row
        onset_time = float(self.table.item(selected_row, 0).text())

        # open dialog to get sure
        sure, ok = QtWidgets.QInputDialog.getDouble(self, 'Sure', 'Enter sure value:')
        if not ok:
            return

        # add sure to timestamps
        self.timestamps[onset_time]['sure'] = sure

        # update table
        self.update_table()

    def _add_notes_from_context_menu(self):
        # get selected row
        selected_row = self.table.currentRow()

        # get onset time from selected row
        onset_time = float(self.table.item(selected_row, 0).text())

        # open dialog to get notes
        notes, ok = QtWidgets.QInputDialog.getText(self, 'Notes', 'Enter notes:')
        if not ok:
            return

        # add notes to timestamps
        self.timestamps[onset_time]['notes'] = notes

        # update table
        self.update_table()

    def _delete_from_context_menu(self):
        # get selected row
        selected_row = self.table.currentRow()

        # get onset time from selected row
        onset_time = float(self.table.item(selected_row, 0).text())

        # delete entry
        del self.timestamps[onset_time]

        # update table
        self.update_table()

    def update_table(self):
        # clear table
        self.table.clearContents()

        # sort timestamps by onset time
        sorted_timestamps = sorted(self.timestamps.items(), key=lambda x: x[0])

        # add rows to table
        self.table.setRowCount(len(sorted_timestamps))
        for i, (onset, entry) in enumerate(sorted_timestamps):
            # onset time
            item = QtWidgets.QTableWidgetItem(str(onset))
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.table.setItem(i, 0, item)

            # offset time
            if entry['offset'] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry['offset']))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.setItem(i, 1, item)

            # sure
            if entry['sure'] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry['sure']))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.setItem(i, 2, item)

            # notes
            if entry['notes'] is not None:
                item = QtWidgets.QTableWidgetItem(str(entry['notes']))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.setItem(i, 3, item)

        # resize columns
        self.table.resizeColumnsToContents()

class TimeStampsDockwidget(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Time Stamps")
        self.main_win = main_win
        self.main_widget = QtWidgets.QWidget()
        self.setWidget(self.main_widget)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self.table_widget = TsWidget()
        self.main_layout.addWidget(self.table_widget)

        

    def add_vid_time_stamp(self, frame_num):
        # frame_num = self.main_win.get_frame_num()
        # if frame_num is None:
        #     return

        self.table_widget.add_timestamp(frame_num)

    # def import_ts(self, ts):
    #     del self.time_stamps_tree_view
    #     self.time_stamps_tree_view = TimeStampsTreeView(ts_type="On/Off")
    #     self.main_layout.addWidget(self.time_stamps_tree_view)
    #     self.time_stamps_tree_view.add_time_stamps(ts)
