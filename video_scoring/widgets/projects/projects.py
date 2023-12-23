"""
This is a projects dock widget. It will list the current projects in a tree view with the ability to add, remove, and rename projects.
"""

import logging
import datetime
import os
from typing import TYPE_CHECKING
from PyQt6.QtGui import QShowEvent

from qtpy import QtCore, QtGui, QtWidgets

from video_scoring.settings import ProjectSettings

if TYPE_CHECKING:
    from video_scoring import MainWindow



class CreateProject(QtWidgets.QWidget):
    created_project = QtCore.Signal(ProjectSettings)
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setWindowTitle("Create Project")
        self.resize(400, 200)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QtWidgets.QGridLayout(self)
        self.project_name = QtWidgets.QLineEdit()
        self.project_name.setPlaceholderText("Project Name")
        self.project_name_label = QtWidgets.QLabel("Project Name")
        self.project_name_label.setBuddy(self.project_name)
        self.project_scorer = QtWidgets.QLineEdit()
        self.project_scorer.setPlaceholderText("Project Scorer")
        self.project_scorer_label = QtWidgets.QLabel("Project Scorer")
        self.project_scorer_label.setBuddy(self.project_scorer)
        self.project_location_label = QtWidgets.QLabel("Project Location")
        self.project_location = QtWidgets.QLineEdit()
        self.project_location.setPlaceholderText("Project Location")
        self.project_location_label.setBuddy(self.project_location)
        self.project_location_button = QtWidgets.QPushButton("Browse")
        self.project_location_button.clicked.connect(self.browse_project_location)
        self.create_project_button = QtWidgets.QPushButton("Create Project")
        self.create_project_button.clicked.connect(self.create_project)
        self.layout.addWidget(self.project_name_label, 0, 0)
        self.layout.addWidget(self.project_name, 0, 1)
        self.layout.addWidget(self.project_scorer_label, 0, 2)
        self.layout.addWidget(self.project_scorer, 0, 3)
        self.layout.addWidget(self.project_location_label, 1, 0)
        self.layout.addWidget(self.project_location, 1, 1, 1, 3)
        self.layout.addWidget(self.project_location_button, 1, 4)
        self.layout.addWidget(self.create_project_button, 2, 0, 1, 5)

    def input_valid(self):
        # change border back to normal
        self.project_name.setStyleSheet("")
        self.project_scorer.setStyleSheet("")
        self.project_location.setStyleSheet("")
        if self.project_name.text() == "":
            # change to a red border
            self.project_name.setStyleSheet("border: 1px solid red;")
            return False
        if self.project_scorer.text() == "":
            # change to a red border
            self.project_scorer.setStyleSheet("border: 1px solid red;")
            return False
        import os
        if not os.path.exists(os.path.dirname(self.project_location.text())):
            self.project_location.setStyleSheet("border: 1px solid red;")
            return False
        return True
        
    def create_project(self):
        if not self.input_valid():
            return
        project = ProjectSettings(
            name=self.project_name.text(),
            scorer=self.project_scorer.text(),
            file_location=self.project_location.text(),
        )
        project.save()
        # TODO: maybe check uid and location?
        if project.file_location not in [p[1] for p in self.main_win.app_settings.projects]:
            self.main_win.app_settings.projects.append((project.uid, project.file_location))
        #self.main_win.set_project_from_uid(project.uid)
        self.created_project.emit(project)
        self.close()

    def browse_project_location(self):
        # open file dialog to make a custom .vsap file
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        file_dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly)
        file_dialog.setNameFilter("Video Scoring Archive File (*.vsap) ;; All Files (*.*)")
        file_dialog.setWindowTitle("Select Project Location")
        file_dialog.setDefaultSuffix("vsap")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDirectory([os.path.expanduser("~"), os.path.expanduser("~/Documents")][os.name == "nt"])

        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # check that the file is a .vsap file
            file_path = file_dialog.selectedFiles()[0]
            if not file_path.endswith(".vsap"):
                # Error
                return
            self.project_location.setText(file_path)

class ProjectTree(QtWidgets.QTreeWidget):
    """This is a tree widget that will display the project settings in a tree format. 
    Each project item will have a root item that will contain the project name, date created, and date modified. It's children will be
    """
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.paint_drop_indicator = False
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.setDragDropOverwriteMode(False)
        self.setDragEnabled(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setHeaderLabels(["Project Name", "Scorer", "Date Created", "Date Modified"])
        self.setColumnCount(4)

    # accept drops
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        self.paint_drop_indicator = True
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        event.accept()

    # accept drops
    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        self.paint_drop_indicator = True
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        event.accept()

    def dragLeaveEvent(self, event):
        self.paint_drop_indicator = False
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent | None) -> None:
        files = event.mimeData().urls()
        for file in files:
            file = file.toLocalFile()
            if not file.endswith(".vsap"):
                self.main_win.update_status(f"File is not a valid project file: {file}", logging.ERROR)
                continue
                # get the uid
            project = ProjectSettings()
            project.load_from_file(file)
            if project.uid in [p[0] for p in self.main_win.app_settings.projects]:
                self.main_win.update_status(f"Project already exists: {project.name}", logging.ERROR)
                continue
            self.main_win.app_settings.projects.append((project.uid, file))
        self.main_win.app_settings.save()
        self.main_win.projects_w.add_projects()
        self.paint_drop_indicator = False
        event.accept()

class ProjectsWidget(QtWidgets.QWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.setup_ui()
        # size hint
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumSize(500, 300)

    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        # search bar
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search Projects")
        self.search_bar.setClearButtonEnabled(True)
        # connect the search bar to the search function
        self.search_bar.textChanged.connect(self.filter_projects)
        self.layout.addWidget(self.search_bar)
        
        self.project_list = ProjectTree(self.main_win)
        self.project_list.setDragEnabled(True)
        self.project_list.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.project_list.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # drag and drop project files
        self.project_list.setAcceptDrops(True)
        self.project_list.setDropIndicatorShown(True)
        self.project_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.project_list.setDragDropOverwriteMode(False)


        self.add_projects()

        self.project_list.itemDoubleClicked.connect(self.open_project)
        self.layout.addWidget(self.project_list)
        self.project_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self.project_list_menu)

        self.project_list_menu = QtWidgets.QMenu(self)
        self.open_project_action = QtWidgets.QAction("Open Project", self)
        self.open_project_action.triggered.connect(self.open_project)
        self.project_list_menu.addAction(self.open_project_action)
        self.project_list_menu.addSeparator()
        self.create_project_action = QtWidgets.QAction("Create Project", self)
        self.create_project_action.triggered.connect(self.create_project)
        self.project_list_menu.addAction(self.create_project_action)
        self.remove_project_action = QtWidgets.QAction("Remove Project", self)
        self.remove_project_action.triggered.connect(self.remove_project)
        self.project_list_menu.addAction(self.remove_project_action)


        # button layout
        self.button_layout = QtWidgets.QHBoxLayout()
        self.import_project_button = QtWidgets.QPushButton("Import Project")
        self.import_project_button.clicked.connect(self.import_project)
        self.button_layout.addWidget(self.import_project_button)

        self.button_layout.addStretch(1)
        

        # add a button to create a new project
        self.create_project_button = QtWidgets.QPushButton("Create Project")
        self.create_project_button.clicked.connect(self.create_project)

        # add a button to open a project
        self.open_project_button = QtWidgets.QPushButton("Open Project")
        self.open_project_button.clicked.connect(self.open_project)

        self.layout.addWidget(self.search_bar)
        self.layout.addWidget(self.project_list)
        self.layout.addLayout(self.button_layout)
        self.button_layout.addWidget(self.create_project_button)
        self.button_layout.addWidget(self.open_project_button)

        # connect the project list selection so that buttons are enabled/disabled
        self.project_list.itemSelectionChanged.connect(self.project_list_selection_changed)

    def filter_projects(self, text: str):
        # clear the search bar
        if text == "":
            self.add_projects()
            return
        # clear the project list
        self.project_list.clear()
        # loop through the projects
        for project_t in self.main_win.app_settings.projects:
            project = ProjectSettings()
            project.load_from_file(project_t[1])
            # check if the text is in the project name
            if text.lower() in project.name.lower():
                self.add_project(project)
                continue
            # check if the text is in the project scorer
            if text.lower() in project.scorer.lower():
                self.add_project(project)
                continue
            # check if the text is in the project created date
            if text.lower() in project.created.lower():
                self.add_project(project)
                continue
            # check if the text is in the project modified date
            if text.lower() in project.modified.lower():
                self.add_project(project)
                continue

    def project_list_selection_changed(self):
        if len(self.project_list.selectedItems()) > 0:
            self.open_project_button.setEnabled(True)
        else:
            self.open_project_button.setEnabled(False)
        
    def project_list_menu(self, pos):
        self.project_list_menu.exec(self.project_list.mapToGlobal(pos))

    def open_project(self):
        """Opens the selected project"""
        # get selected item
        selected_items = self.project_list.selectedItems()
        # print the uid of the selected project
        for item in selected_items:
            uid = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            project = self.main_win.settings.get_project(uid)
            if project is None:
                self.main_win.update_status("Project not found", logging.ERROR)
                return
            self.main_win.load_project(project)

    def import_project(self):
        # open file dialog to open a .vsap file
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Video Scoring Archive File (*.vsap) ;; All Files (*.*)")
        file_dialog.setWindowTitle("Import Project")
        file_dialog.setDefaultSuffix("vsap")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setDirectory([os.path.expanduser("~"), os.path.expanduser("~/Documents")][os.name == "nt"])

        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # check that the file is a .vsap file
            file_path = file_dialog.selectedFiles()[0]
            if not file_path.endswith(".vsap"):
                self.main_win.update_status(f"File is not a valid project file: {file_path}", logging.ERROR)
                return
            # get the uid
            project = ProjectSettings()
            project.load_from_file(file_path)

            if project.uid in [p[0] for p in self.main_win.app_settings.projects]:
                # error
                self.main_win.update_status(f"Project already exists: {project.name}", logging.ERROR)
                # highlight the project in the project list
                for i in range(self.project_list.topLevelItemCount()):
                    item = self.project_list.topLevelItem(i)
                    if item.data(0, QtCore.Qt.ItemDataRole.UserRole) == project.uid:
                        self.project_list.setCurrentItem(item)
                        break
                return
            
            self.main_win.app_settings.projects.append((project.uid, file_path))
            self.main_win.app_settings.save()
            self.add_projects()
             
    def create_project(self):
        """Creates a project and adds it to the project list"""
        # open create project dialog
        self.create_project_dialog = CreateProject(self.main_win)
        self.create_project_dialog.created_project.connect(self.add_project)
        self.create_project_dialog.show()

    def remove_project(self):
        # remove project from app settings
        selected_items = self.project_list.selectedItems()
        for item in selected_items:
            uid = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            for project_t in self.main_win.app_settings.projects:
                if project_t[0] == uid:
                    self.main_win.app_settings.projects.remove(project_t)
                    self.main_win.app_settings.save()
                    self.add_projects()
                    break
                    
    def add_projects(self):
        self.project_list.clear()
        for project_t in self.main_win.app_settings.projects:
            project = ProjectSettings()
            try:
                project.load_from_file(project_t[1])
            except:
                for t in self.main_win.app_settings.projects:
                    if t[1] == project_t[1]:
                        self.main_win.app_settings.projects.remove(t)
                self.main_win.update_status(f"Failed to load project: {project_t[1]}", logging.ERROR)
            self.add_project(project)

    def add_project(self, project: ProjectSettings):
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, project.name)
        item.setText(1, project.scorer)
        if isinstance(project.created, datetime.datetime):
            # format the date to be month name day, year
            item.setText(2, project.created.strftime("%B %d, %Y"))
        else:
            # convert the string to a datetime object, then format it
            item.setText(2, datetime.datetime.strptime(project.created, "%Y-%m-%d %H:%M:%S.%f").strftime("%B %d, %Y"))
        if isinstance(project.modified, datetime.datetime):
            item.setText(3, project.modified.strftime("%B %d, %Y"))
        else:
            item.setText(3, datetime.datetime.strptime(project.modified, "%Y-%m-%d %H:%M:%S.%f").strftime("%B %d, %Y"))
            
        # user data will be the project uid
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, project.uid)
        # make the item size hint bigger
        item.setSizeHint(0, QtCore.QSize(0, 25))
        # add the item to the project list
        self.project_list.addTopLevelItem(item)
        self.project_list.expandAll()

