import os
import base64

from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QUrl, QSize, Qt, QStandardPaths, QFile
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from RemoteImage import RemoteImage


class CardWidget(QDialog):
    def __init__(self, parent = None):
        super().__init__(parent, Qt.Popup | Qt.ToolTip)
        self._remote_image = RemoteImage(self)
        self._remote_image.imageReady.connect(self.repaint)
        self._default_image = QImage(self._imageFullName("default.jpg"))


    def setUrl(self, url):
        self._remote_image.setUrl(url)


    def paintEvent(self, ev):
        image_to_paint = self._remote_image.image()
        if not image_to_paint:
            image_to_paint = self._default_image

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawImage(0, 0, image_to_paint)


    def sizeHint(self):
        return QSize(488, 680)


    def _imageFullName(self, filename):
        app_dir = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(app_dir, "cards", filename)
