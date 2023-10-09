# a timeline widget simmilar to the premeire pro timeline
# it will have a slider to move through the video and tracks. One track for the video and one track for each behavior, the timestamps will either compose a block or a line depending on the scoring type
# will will need a robus zooming and panning system to navigate the timeline

from unittest import skip
from qtpy import QtWidgets, QtGui, QtCore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_scoring.main import MainWindow
from superqt import QDoubleRangeSlider


# a custom slider that will allow the user to zoom in and out of the timeline. There will be two handles, moving the handles will change the range of the slider, grabbing any other part of the slider will allow you to move the slider along the timeline


class Timeline(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.main_win = main_win
        # there will be four main components to the timeline, the slider top section will be a horizontal slider that will allow the user to move through the video with time stamps on the top and ticks on the bottom, the middle section will be the tracks, the bottom section will be the zoom slider, and the left section will be the track names and other controls
        self.slider = QDoubleRangeSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setStyleSheet("""""")
        self.slider.setRange(0, 100)
        self.slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBothSides)
        self.slider.setValue((0.2, 0.8))
        # self.slider.valueChanged.connect(self.slider_value_changed)
        # self.slider.sliderPressed.connect(self.slider_pressed)

        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.addWidget(self.slider)
        self.setWidget(self.main_widget)

    def slider_value_changed(self, value):
        print(value)

    def slider_pressed(self):
        print("slider pressed")

    def slider_released(self):
        print("slider released")

    def zoom_slider_value_changed(self, value):
        print(value)

    def zoom_slider_pressed(self):
        print("zoom slider pressed")

    def zoom_slider_released(self):
        print("zoom slider released")
