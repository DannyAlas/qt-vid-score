from typing import TYPE_CHECKING, Any, Dict, List, Literal, Tuple, Union

from qtpy import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from video_scoring import MainWindow


class customTableWidget(QtWidgets.QTableWidget):
    """A a custom table widget that adds a border around selected rows"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
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
        self.table = customTableWidget(0, 2)
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
            self.main_win.video_player_dw.seek(int(item[0].text()))
        # if the item is in the offset column, move the playhead to the offset
        elif item[0].column() == 1:
            self.main_win.video_player_dw.seek(int(item[0].text()))

    def update(self):
        """Update the table with the timestamps"""
        # clear the table
        if len(self.main_win.timeline_dw.timeline_view.behavior_tracks) == 0:
            return
        # get the track name to save on from the timeline
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
            # add data to the onset for it unsure
            onset_item.setData(QtCore.Qt.ItemDataRole.UserRole, item.unsure)
            if item.unsure:
                onset_item.setBackground(QtGui.QColor("#cc8e47"))
                offset_item.setBackground(QtGui.QColor("#cc8e47"))
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
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
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
        self.save_act = QtWidgets.QAction("Save", self)
        self.save_act.setIcon(self.main_win.get_icon("diskette.png", self.save_act))
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
        self.update_act = QtWidgets.QAction("Refresh", self)
        self.update_act.setIcon(self.main_win.get_icon("refresh.svg", self.update_act))
        self.update_act.triggered.connect(self.refresh)
        self.toolbar.addAction(self.update_act)

        self.table_widget = TsWidget(self.main_win, self)
        self.main_layout.addWidget(self.table_widget)
        self.main_win.loaded.connect(self.init_connections)

    def context_menu(self, pos):
        menu = QtWidgets.QMenu()
        # get the text of the first column of the selected row
        row = self.table_widget.table.currentRow()
        if row == -1:
            return
        onset = self.table_widget.table.item(row, 0).text()

        # get the item from the timeline
        track = self.main_win.timeline_dw.timeline_view.get_track_from_name(
            self.behavior_track_combo.currentText()
        )
        if track is not None:
            item = track.get_item(int(onset))
            if item is not None:
                # get the context menu from the item and add it to the menu
                itm_ctx = item.get_context_menu()
                if itm_ctx is not None:
                    for act in itm_ctx.actions():
                        menu.addAction(act)
        menu.exec(self.mapToGlobal(pos))

    def init_connections(self):
        self.main_win.timeline_dw.timeline_view.track_name_to_save_on_changed.connect(
            self.update_tracks
        )
        self.update()

    def update_tracks(self):
        self.behavior_track_combo.clear()
        if len(self.main_win.timeline_dw.timeline_view.behavior_tracks) == 0:
            self.table_widget.table.clearContents()
            self.table_widget.table.setRowCount(0)
            return
        for track in self.main_win.timeline_dw.timeline_view.behavior_tracks:
            self.behavior_track_combo.addItem(track.name)
        # set the current index to the item whith the name of the track to save on
        self.behavior_track_combo.setCurrentIndex(
            self.behavior_track_combo.findText(
                self.main_win.timeline_dw.timeline_view.track_name_to_save_on
            )
        )

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
        self.main_win.project_settings.scoring_data.timestamp_file_location = file_path
        # save the table
        with open(file_path, "w") as f:
            # write the header
            f.write("Onset,Offset,Unsure\n")
            # write the data
            for row in range(self.table_widget.table.rowCount()):
                onset = self.table_widget.table.item(row, 0).text()
                offset = self.table_widget.table.item(row, 1).text()
                unsure = self.table_widget.table.item(row, 0).data(
                    QtCore.Qt.ItemDataRole.UserRole
                )
                f.write(f"{onset},{offset},{unsure}\n")
        # show a message box
        self.main_win.statusBar().showMessage(f"Saved timestamps to {file_path}")
