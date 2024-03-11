""" RemoteImage.py """
import os
import base64

from PySide6.QtCore import QObject, QUrl, QStandardPaths, QFile, Signal
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

class RemoteImage(QObject):
    """ RemoteImage is a helper class to dowload remote images """
    network_manager = None

    imageReady = Signal()
    def __init__(self, parent = None):
        super().__init__(parent)

        if not RemoteImage.network_manager:
            RemoteImage.network_manager = QNetworkAccessManager()

        self._url = None
        self._current_request = None
        self._current_image = None
        self._current_size = None
        self._cache_dir = os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation), "cache")
        os.makedirs(self._cache_dir, exist_ok=True)


    def setUrl(self, url, size = None):
        """ Set Image url """
        if self._current_request:
            if self._current_request.url() == url:
                return
            self._current_request.abort()
            self._current_request = None

        cache_file = self._imageFromCache(url)
        if QFile.exists(cache_file):
            self._updateImage(QImage(cache_file))
            return

        self._current_image = None
        self._current_size = size
        self._current_request = RemoteImage.network_manager.get(QNetworkRequest(QUrl(url)))
        self._current_request.finished.connect(self._onReplyFinished)
        self._current_request.errorOccurred.connect(self._onReplyError)

    def image(self):
        """ Returns QImage or null if not dowloaded yet """
        return self._current_image


    def isReady(self):
        """ Returns true if image is dowloaded """
        return self._current_image is not None


    def _onReplyFinished(self):
        img = QImage()
        img.load(self._current_request, None)

        if not img.isNull():
            cache_file = self._imageFromCache(self._current_request.url().toString())
            if self._current_size:
                img = img.scaled(self._current_size)
            img.save(cache_file)

        self._current_request = None
        self._updateImage(img)


    def _updateImage(self, img):
        self._current_image = img
        self.imageReady.emit()


    def _onReplyError(self, error):
        print("Failed to downlod image:", self._current_request.url(), error)
        self._current_request = None


    def _imageFromCache(self, url):
        message_bytes = url.encode('ascii')
        base64_bytes = base64.urlsafe_b64encode(message_bytes)
        hash_filename = base64_bytes.decode('ascii')
        return os.path.join(self._cache_dir, f"{hash_filename}.png")
