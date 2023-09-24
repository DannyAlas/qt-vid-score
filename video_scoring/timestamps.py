from typing import Any, Dict, List, Tuple, Union, Literal
from qtpy import QtCore, QtWidgets, QtGui
import json

class TupleTimestamps(list):
    """
    Implements a list of time stamps as tuples. Ensures the first time stamps of the tuple is always smaller than the second ts, sorts by the first ts. Raises a ValueError if two time stamps tuples overlap. Implements a stack like interface for un/redoing time stamps.

    Parameters
    ----------
    list : list of tuples
        List of tuples of time stamps

    Example
    -------
    >>> ts = TimeStamps([(3, 4), (5, 6)])
    >>> ts.append((2.1, 2))
    >>> ts.append((1, 2))
    >>> ts.extend([(0, 1), (0.5, 1.5)])
    >>> print(ts)
    [(0, 1), (0.5, 1.5), (1, 2), (2.1, 2), (3, 4), (5, 6)]

    >>> ts = TimeStamps([(0, 1), (0.5, 1.5), (1.5, 2.5)])
    >>> ts.append((1, 2))
        ValueError: Time stamp (1, 2) overlaps with (1.5, 2.5)

    Raises
    ------
        ValueError: If two time stamps overlap

    """

    def __init__(self, *args):
        super().__init__(*args)
        self.sort(key=lambda x: x[0])
        self._check()

    def _append(self, ts):
        if ts[0] > ts[1]:
            ts = (ts[1], ts[0])
        super().append((float(ts[0]), float(ts[1])))
        self.sort(key=lambda x: x[0])
        try:
            self._check()
        except ValueError as e:
            super().remove(ts)
            raise e

    def _extend(self, ts_list):
        for ts in ts_list:
            self._append(ts)
        self.sort(key=lambda x: x[0])

    def _remove(self, __value: Any) -> None:
        super().remove(__value)
        self.sort(key=lambda x: x[0])

    def _edit(self, ts, new_ts):
        self._remove(ts)
        try:
            self._append(new_ts)
        except Exception as e:
            self._append(ts)
            raise e

    def _check(self):
        for i in range(len(self) - 1):
            if self[i][1] > self[i + 1][0]:
                raise ValueError(f"Time stamp {self[i + 1]} overlaps with {self[i]}")


class BehaviorTimeStamps(TupleTimestamps):
    """
    Implements a list like class for (onset,offset) time stamps with an interface for un/redoing time stamps. See `TupleTimestamps` for more information.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.action_stack = []
        self.undone_action_stack = []

    def append(self, ts):
        super()._append(ts)
        self.action_stack.append(("append", ts))
        self.undone_action_stack = []

    def extend(self, ts_list):
        super()._extend(ts_list)
        self.action_stack.append(("extend", ts_list))
        self.undone_action_stack = []

    def remove(self, ts):
        super().remove(ts)
        self.action_stack.append(("remove", ts))
        self.undone_action_stack = []

    def edit(self, ts, new_ts):
        if ts == new_ts:
            return
        super()._edit(ts, new_ts)
        self.action_stack.append(("edit", (ts, new_ts)))
        self.undone_action_stack = []

    def undo(self):
        if self.action_stack:
            action = self.action_stack.pop()
            if action[0] == "append":
                self.undone_action_stack.append(("append", action[1]))
                super()._remove(action[1])
            elif action[0] == "extend":
                self.undone_action_stack.append(("extend", action[1]))
                for ts in action[1]:
                    super()._remove(ts)
            elif action[0] == "remove":
                self.undone_action_stack.append(("remove", action[1]))
                super()._append(action[1])
            elif action[0] == "edit":
                self.undone_action_stack.append(("edit", (action[1][1], action[1][0])))
                super()._edit(action[1][1], action[1][0])

    def redo(self):
        if self.undone_action_stack:
            action = self.undone_action_stack.pop()
            if action[0] == "append":
                self.action_stack.append(("append", action[1]))
                super()._append(action[1])
            elif action[0] == "extend":
                self.action_stack.append(("extend", action[1]))
                super()._extend(action[1])
            elif action[0] == "remove":
                self.action_stack.append(("remove", action[1]))
                super()._remove(action[1])
            elif action[0] == "edit":
                self.action_stack.append(("edit", (action[1][1], action[1][0])))
                super()._edit(action[1][1], action[1][0])


class SingleTimeStamps(list):
    """
    Implements a list of time stamps as single values. Sorts the list. Raises a ValueError if two time stamps overlap. Implements a stack like interface for un/redoing time stamps.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.sort()
        self._check()

    def _append(self, ts):
        super().append(float(ts))
        self.sort()
        self._check()

    def _extend(self, ts_list):
        for ts in ts_list:
            self._append(ts)
        self.sort()

    def _remove(self, __value: Any) -> None:
        super().remove(__value)
        self.sort()

    def _edit(self, ts, new_ts):
        self._remove(ts)
        try:
            self._append(new_ts)
        except Exception as e:
            self._append(ts)
            raise e

    def _check(self):
        for i in range(len(self) - 1):
            if self[i] > self[i + 1]:
                raise ValueError(f"Time stamp {self[i + 1]} overlaps with {self[i]}")


class TimeStampsModel(QtCore.QAbstractItemModel):
    """
    Implements a custom model to display the time stamps tuple list. Provides methods to add and remove time stamps.
    """

    def __init__(self, ts_type: Literal["Single", "On/Off"], parent=None):
        super().__init__(parent)
        self.time_stamps: Union[SingleTimeStamps, BehaviorTimeStamps] = (
            SingleTimeStamps() if ts_type == "Single" else BehaviorTimeStamps()
        )

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.time_stamps)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 2

    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self.time_stamps[index.row()][index.column()]
        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return ["Start", "End"][section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section
        return None

    def index(
        self, row: int, column: int, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if parent.isValid():
            return QtCore.QModelIndex()
        return self.createIndex(row, column)

    def parent(self, child: QtCore.QModelIndex) -> QtCore.QModelIndex:
        return QtCore.QModelIndex()

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def add_time_stamp(self, ts):
        self.beginInsertRows(
            QtCore.QModelIndex(), len(self.time_stamps), len(self.time_stamps)
        )
        self.time_stamps.append(ts)
        self.endInsertRows()

    def add_time_stamps(self, ts_list):
        self.beginInsertRows(
            QtCore.QModelIndex(),
            len(self.time_stamps),
            len(self.time_stamps) + len(ts_list),
        )
        self.time_stamps.extend(ts_list)
        self.endInsertRows()

    def remove_time_stamp(self, ts):
        self.beginRemoveRows(
            QtCore.QModelIndex(), self.time_stamps.index(ts), self.time_stamps.index(ts)
        )
        self.time_stamps.remove(ts)
        self.endRemoveRows()

    def get_time_stamps(self):
        return self.time_stamps

    def edit_time_stamp(self, ts, new_ts):
        self.beginRemoveRows(
            QtCore.QModelIndex(), self.time_stamps.index(ts), self.time_stamps.index(ts)
        )
        self.time_stamps.edit(ts, new_ts)
        self.endRemoveRows()

    def undo(self):
        self.time_stamps.undo()

    def redo(self):
        self.time_stamps.redo()

    def refresh(self):
        for i in range(len(self.time_stamps)):
            self.beginRemoveRows(QtCore.QModelIndex(), i, i)
            self.endRemoveRows()
        for i in range(len(self.time_stamps)):
            self.beginInsertRows(QtCore.QModelIndex(), i, i)
            self.endInsertRows()


class TimeStampsTreeView(QtWidgets.QTreeView):
    """
    A Qt widget that displays time stamps as a tree view. Implements a custom model to display the time stamps tuple list. Provides methods to add, edit, and remove time stamps.

    Parameters
    ----------
    ts_type : Literal["Single", "On/Off"]
        The type of time stamps to display. "Single" displays time stamps as single values, "On/Off" displays time stamps as tuples of (onset, offset) values. See `SingleTimeStamps` and `BehaviorTimeStamps` for more information.
    """

    def __init__(self, ts_type: Literal["Single", "On/Off"], parent=None):
        super().__init__(parent)
        self.model: TimeStampsModel = TimeStampsModel(ts_type=ts_type)
        self.setModel(self.model)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)

    def add_time_stamp(self, ts):
        try:
            self.model.add_time_stamp(ts)
        except Exception as e:
            self.refresh()
            raise e

    def add_time_stamps(self, ts_list):
        try:
            self.model.add_time_stamps(ts_list)
        except Exception as e:
            self.refresh()
            raise e

    def remove_time_stamp(self, ts):
        try:
            self.model.remove_time_stamp(ts)
        except Exception as e:
            self.refresh()
            raise e

    def edit_time_stamp(self, ts, new_ts):
        try:
            self.model.edit_time_stamp(ts, new_ts)
        except Exception as e:
            self.refresh()
            raise e

    def get_time_stamps(self):
        try:
            return self.model.get_time_stamps()
        except Exception as e:
            self.refresh()
            raise e

    def undo(self):
        try:
            self.model.undo()
        except Exception as e:
            self.refresh()
            raise e

    def redo(self):
        try:
            self.model.redo()
        except Exception as e:
            self.refresh()
            raise e

    def refresh(self):
        self.model.refresh()

class KeyBoardShortcuts(QtWidgets.QDockWidget):
    """Reads a json file with keyboard shortcuts and displays them in a tree view. Allows the user to edit the key sequences."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tree_view = QtWidgets.QTreeView()
        self.setWidget(self.tree_view)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        self.model = QtGui.QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.load_shortcuts()
        self.tree_view.expandAll()
        self.tree_view.doubleClicked.connect(self.edit_key_sequence)

    def load_shortcuts(self):
        self.model.clear()
        with open(r"C:\dev\projects\qt-vid-scoring\src\shortcuts.json", "r") as f:
            shortcuts = json.load(f)
        # two columns, one for the action, one for the key sequence
        self.model.setColumnCount(2)
        # headers: action, key sequence
        self.model.setHorizontalHeaderLabels(["Action", "Key sequence"])
        for action, key_sequence in shortcuts.items():
            action_item = QtGui.QStandardItem(action)
            key_sequence_item = QtGui.QStandardItem(QtGui.QKeySequence(key_sequence).toString())
            self.model.appendRow((action_item, key_sequence_item))


    def edit_key_sequence(self, index):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Edit key sequence")
        dialog.resize(200, 100)
        layout = QtWidgets.QVBoxLayout()
        keysequence = QtWidgets.QKeySequenceEdit()
        keysequence.setKeySequence(QtGui.QKeySequence(index.data()))
        layout.addWidget(keysequence)
        dialog.setLayout(layout)
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("Ok")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.model.setData(index, keysequence.keySequence().toString())

    def save_shortcuts(self):
        shortcuts = {}
        for i in range(self.model.rowCount()):
            parent = self.model.item(i)
            shortcuts[parent.text()] = []
            for j in range(parent.rowCount()):
                child = parent.child(j)
                shortcuts[parent.text()].append(child.text())
        with open(r"C:\dev\projects\qt-vid-scoring\src\shortcuts.json", "w") as f:
            json.dump(shortcuts, f, indent=4)
    
class MainWindow(QtWidgets.QMainWindow):
    """just a test for the time stamps tree view"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tree_view = TimeStampsTreeView(ts_type="On/Off")
        self.setCentralWidget(self.tree_view)
        self.tree_view.add_time_stamps([(0, 1), (1, 2), (2, 3), (3, 4)])
        # context menu to add and remove time stamps
        self.tree_view.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.tree_view.customContextMenuRequested.connect(self.open_menu)
        # double click to edit time stamp line
        self.tree_view.doubleClicked.connect(self.edit_time_stamp)
        self.removeChildrenFocus()
        self.shortcuts = json.loads(open(r"C:\dev\projects\qt-vid-scoring\src\shortcuts.json", "r").read())
        print(self.shortcuts)

    def removeChildrenFocus (self):
        # TODO: add method to save original focus policy and restore it
        def recursiveSetChildFocusPolicy (parentQWidget):
            for childQWidget in parentQWidget.findChildren(QtWidgets.QWidget):
                childQWidget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
                recursiveSetChildFocusPolicy(childQWidget)
        recursiveSetChildFocusPolicy(self)

    def open_menu(self, position):
        menu = QtWidgets.QMenu()
        add_action = menu.addAction("Add time stamp")
        remove_action = menu.addAction("Remove time stamp")
        keysequence_edit_action = menu.addAction("Edit key sequence")
        action = menu.exec(self.tree_view.viewport().mapToGlobal(position))
        if action == add_action:
            # open a dialog to add a time stamp
            dialog = QtWidgets.QDialog()
            dialog.setWindowTitle("Add time stamp")
            dialog.resize(200, 100)
            layout = QtWidgets.QVBoxLayout()
            start_time = QtWidgets.QLineEdit()
            end_time = QtWidgets.QLineEdit()
            layout.addWidget(start_time)
            layout.addWidget(end_time)
            dialog.setLayout(layout)
            dialog.exec()
            try:
                self.tree_view.add_time_stamp(
                    (float(start_time.text()), float(end_time.text()))
                )
            except ValueError as e:
                print(e)
        elif action == remove_action:
            # remove the selected time stamp
            self.tree_view.remove_time_stamp(
                self.tree_view.get_time_stamps()[
                    self.tree_view.selectedIndexes()[0].row()
                ]
            )
        elif action == keysequence_edit_action:
            # open the keybaord shortcuts dock widget
            self.key_sequence_dock_widget = KeyBoardShortcuts()
            self.key_sequence_dock_widget.load_shortcuts()
            self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.key_sequence_dock_widget)
            self.key_sequence_dock_widget.show()

    def keyPressEvent(self, event):
        sequence = ""
        key = event.key()
        modifier = event.modifiers()
        if modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
            sequence += "Ctrl+"
        if modifier == QtCore.Qt.KeyboardModifier.ShiftModifier:
            sequence += "Shift+"
        if modifier == QtCore.Qt.KeyboardModifier.AltModifier:
            sequence += "Alt+"
        if modifier == QtCore.Qt.KeyboardModifier.MetaModifier:
            sequence += "Meta+"
        sequence += QtGui.QKeySequence(key).toString()
        print(sequence)
        for action, key_sequence in self.shortcuts.items():
            if str(key_sequence).capitalize() == sequence:
                print(action)
        if (
            event.key() == QtCore.Qt.Key.Key_Z
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.undo()
            self.tree_view.refresh()
        # ctrl + shift + z to redo
        elif (
            event.key() == QtCore.Qt.Key.Key_Z
            and event.modifiers()
            == QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            self.redo()
            self.tree_view.refresh()
        elif event.key() == QtCore.Qt.Key.Key_Delete:
            self.tree_view.remove_time_stamp(
                self.tree_view.get_time_stamps()[
                    self.tree_view.selectedIndexes()[0].row()
                ]
            )

        super().keyPressEvent(event)

    # edit the selected time stamp
    def edit_time_stamp(self, item: QtCore.QModelIndex):
        ts = self.tree_view.get_time_stamps()[item.row()]
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Edit time stamp")
        dialog.resize(200, 100)
        layout = QtWidgets.QVBoxLayout()
        start_time = QtWidgets.QLineEdit()
        start_time.setText(str(ts[0]))
        end_time = QtWidgets.QLineEdit()
        end_time.setText(str(ts[1]))
        layout.addWidget(start_time)
        layout.addWidget(end_time)
        dialog.setLayout(layout)
        dialog.exec()
        try:
            self.tree_view.edit_time_stamp(
                ts, (float(start_time.text()), float(end_time.text()))
            )
        except ValueError as e:
            print(e)

    def undo(self):
        self.tree_view.undo()
        self.tree_view.expandAll()

    def redo(self):
        self.tree_view.redo()
        self.tree_view.expandAll()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
