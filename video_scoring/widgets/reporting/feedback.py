import json
from typing import TYPE_CHECKING
from uuid import uuid4

import requests
import sentry_sdk
from qtpy import QtCore, QtGui, QtWidgets
from sentry_sdk import last_event_id

if TYPE_CHECKING:
    from video_scoring import MainWindow


class FeedbackDialog(QtWidgets.QDialog):
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.feedback_url = (
            "https://sentry.io/api/0/projects/daniel-alas/video-scoring/user-feedback/"
        )

        self.setWindowTitle("Feedback")
        self.setWindowIcon(parent.get_icon("icon.png", self))

        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        # name label
        self.name_label = QtWidgets.QLabel("Name")
        self.name_line_edit = QtWidgets.QLineEdit()
        # email label
        self.email_label = QtWidgets.QLabel("Email")
        self.email_line_edit = QtWidgets.QLineEdit()
        # comments label
        self.comments_label = QtWidgets.QLabel("Comments")
        self.comments_text_edit = QtWidgets.QTextEdit()
        self.button_box = QtWidgets.QDialogButtonBox()

        self.submit_button = QtWidgets.QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit_feedback)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        # layout
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(self.name_label, 0, 0)
        layout.addWidget(self.name_line_edit, 0, 1)
        layout.addWidget(self.email_label, 1, 0)
        layout.addWidget(self.email_line_edit, 1, 1)
        layout.addWidget(self.comments_label, 2, 0)
        layout.addWidget(self.comments_text_edit, 2, 1)
        self.button_box.addButton(
            self.submit_button, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.button_box.addButton(
            self.cancel_button, QtWidgets.QDialogButtonBox.ButtonRole.RejectRole
        )
        layout.addWidget(self.button_box, 3, 0, 1, 2)

    def format_response_json(self, response_text):
        return json.dumps(
            json.loads(response_text), sort_keys=True, indent=4, separators=(",", ": ")
        )

    def validate(self):
        if not self.name_line_edit.text():
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Name is required",
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            raise ValueError("Name is required")
        if not self.email_line_edit.text():
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Email is required",
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            raise ValueError("Email is required")
        if not self.comments_text_edit.toPlainText():
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Comments are required",
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            raise ValueError("Comments are required")

    def submit_feedback(self):
        try:
            self.validate()
        except ValueError:
            return
        event_id = last_event_id()
        if not event_id:
            event_id = sentry_sdk.capture_message(str(uuid4()))
        payload = json.dumps(
            {
                "event_id": event_id,
                "name": self.name_line_edit.text(),
                "email": self.email_line_edit.text(),
                "comments": self.comments_text_edit.toPlainText(),
            }
        )
        headers = {
            "Authorization": "Bearer 79e5ec4fc7ff9238419bc3679c31ff641ee4c447f8be05191b05f147dafc0e76",
            "Content-Type": "application/json",
        }
        response = requests.request(
            "POST", self.feedback_url, headers=headers, data=payload
        )
        if response.status_code == 200:
            QtWidgets.QMessageBox.information(
                self,
                "Feedback Submitted",
                "Thank you for your feedback! ",
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            self.close()
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to submit feedback: {self.format_response_json(response.text)}",
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
