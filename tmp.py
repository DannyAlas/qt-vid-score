from qtpy.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QApplication
from qtpy.QtCore import QRectF, Qt
import sys
class MovableRectItem(QGraphicsRectItem):
    def __init__(self, rect, parent=None):
        super(MovableRectItem, self).__init__(rect, parent)
        self.setFlag(QGraphicsItem.ItemIsMovable)  # Make the item movable
    def mousePressEvent(self, event):
        # Handle mouse press events
        print('mousePressEvent')
        super().mousePressEvent(event)
class TrackItem(QGraphicsItem):
    def __init__(self, track_height, track_y, parent=None):
        super(TrackItem, self).__init__(parent)
        self.track_height = track_height
        self.track_y = track_y
        # Additional initialization as needed

    def boundingRect(self):
        # Define the bounding rect of the track item
        return QRectF(0, self.track_y, 1000, self.track_height)

    def paint(self, painter, option, widget=None):
        # Track item drawing code (if needed)
        pass

    def mousePressEvent(self, event):
        # Handle mouse press events
        print('mousePressEvent')
        super(TrackItem, self).mousePressEvent(event)
class MainWindow(QGraphicsView):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Create a track
        track = TrackItem(50, 0)
        self.scene.addItem(track)

        # Add movable rectangles to the scene
        for i in range(3):
            rect_item = MovableRectItem(QRectF(10 + i*50, 10, 30, 30))
            self.scene.addItem(rect_item)

app = QApplication(sys.argv)
mainWindow = MainWindow()
mainWindow.show()
sys.exit(app.exec_())