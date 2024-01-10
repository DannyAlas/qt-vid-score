from uuid import uuid4

from qtpy.QtCore import QObject, QTimer, QUrl
from qtpy.QtWebSockets import QWebSocket


class WebSocketClient(QObject):
    def __init__(self, uid: str):
        super().__init__()
        self.uid = str(uuid4())
        self.online = False
        self.web_socket = QWebSocket()
        self.web_socket.connected.connect(self.on_connected)
        self.web_socket.disconnected.connect(self.on_disconnected)
        self.connect_to_server()

    def connect_to_server(self):
        # Replace with your WebSocket server URL
        self.web_socket.open(QUrl(f"ws://localhost:8000/ws/{self.uid}"))

    def disconnect_from_server(self):
        self.web_socket.sendTextMessage("disconnect")
        self.web_socket.close()

    def on_connected(self):
        self.online = True
        self.web_socket.sendTextMessage("connected")

    def on_disconnected(self):
        self.online = False
        # timer that tries to reconnect
        QTimer.singleShot(1000, self.connect_to_server)
