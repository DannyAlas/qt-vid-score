import typing
from PyQt6 import QtGui
from PyQt6.QtWidgets import QGraphicsSceneHoverEvent
from qtpy import QtWidgets, QtCore, QtGui

class MyItem(QtWidgets.QGraphicsRectItem):
    # a basic item
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # set geometry
        self.setPos(0, 0)
        self.setRect(0, 0, 100, 100)
        self.setZValue(0)
        # black brush
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
        

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        print(event.pos())
        return super().hoverMoveEvent(event)
    
class MyView(QtWidgets.QGraphicsView):
    # a basic view
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setSceneRect(0, 0, 500, 500)
        self.setMouseTracking(True)
        self.scene().addItem(MyItem())

    def paintEvent(self, event) -> None:
        for item in self.scene().items():
            if isinstance(item, MyItem):
                item.setRect(0, 0, 50, 50)
        super().paintEvent(event)
        

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Timeline")
    timeline_view = MyView()
    window.setCentralWidget(timeline_view)
    window.show()
    sys.exit(app.exec())