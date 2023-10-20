# a class that represents a video to be analyzed, with methods for loading and saving
import cv2
from typing import TYPE_CHECKING
from qtpy import QtWidgets, QtCore, QtGui

if TYPE_CHECKING:
    from video_scoring import MainWindow
class Video:
    def __init__(self, main_win: 'MainWindow') -> None:
        self.main_win = main_win
        self.path = None
        self.cap = None
        self.frame_count = None
        self.fps = None
        self.width = None
        self.height = None
        self.duration = None
        self.refrence_frame = 0

    def load_video(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.frame_count / self.fps


    def downsample_frame(self, frame, scale_factor, interpolation=cv2.INTER_AREA):
        return cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=interpolation)

    def cropframe(self, frame,crop: dict):
        """ 
        Crop a frame according to the crop dict

        Parameters
        ----------
        frame : numpy array
            The frame to crop
        crop : dict
            A dict containing the crop coordinates in the form {'x0':x0,'x1':x1,'y0':y0,'y1':y1}

        Returns
        -------
        numpy array
            The cropped frame or the original frame if the crop dict is not valid
        """
        
        try:
            Xs=[crop['x0'],crop['x1']]
            Ys=[crop['y0'],crop['y1']]
            fxmin,fxmax=int(min(Xs)), int(max(Xs))
            fymin,fymax=int(min(Ys)), int(max(Ys))
            return frame[fymin:fymax,fxmin:fxmax]
        except Exception as e:
            self.main_win.update_status(f'Error cropping frame: {e}', log_level='error')


# a dock widget that contains for video analysis

class VideoAnalysisDock(QtWidgets.QDockWidget):
    def __init__(self, main_win: 'MainWindow') -> None:
        super().__init__()
        self.main_win = main_win
        self.setWindowTitle('Video Analysis')
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.main_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.layout)
        self.setWidget(self.main_widget)
        self._init_ui()

    def _init_ui(self):
        # We will first have a label and button to load a video
        self.video_label = QtWidgets.QLabel('No video loaded')
        self.video_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.video_label)
        self.load_video_button = QtWidgets.QPushButton('Load Video')
        self.load_video_button.clicked.connect(self.load_video)
        self.layout.addWidget(self.load_video_button)

    def load_video(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Video', filter='Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.m2v *.3gp *.3g2 *.mxf *.roq *.ts *.mts *.m2ts *.vob *.gif *.gifv *.mng *.avi *.mov *.qt *.wmv *.yuv *.rm *.rmvb *.asf *.amv *.mp4 *.m4p *.m4v *.mpg *.mp2 *.mpeg *.mpe *.mpv *.mpg *.mpeg *.m2v *.m4v *.svi *.3gp *.3g2 *.mxf *.roq *.nsv *.flv *.f4v *.f4p *.f4a *.f4b)')
        if path:
            self.main_win.video.load_video(path)
            self.video_label.setText(f'Video: {path}')
            self.main_win.update_status(f'Loaded video: {path}')

        