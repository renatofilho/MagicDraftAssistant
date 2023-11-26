""" ImageViewer """

import os

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt, QRect, QPoint, QSize, QMargins, QTimer


class ImageViewer(QWidget):
    """ Show Pick screenshot with an overlay layer that shows card status """

    IMAGE_CACHE = {}
    def __init__(self, parent = None):
        super().__init__(parent)
        self._source_image = None
        self._pixmap = None
        self._scaled = None
        self._cards = []
        self._cards_model = None
        self._rank_column = None
        self._cards_model_connections = []
        self._model_change_timer = QTimer(self)
        self._model_change_timer.setSingleShot(True)
        self._model_change_timer.timeout.connect(self._updatePixmap)


    def setImage(self, filename):
        """ Set source image """
        if self._source_image == filename:
            return
        self._source_image = filename
        self._updatePixmap()


    def setCardsModel(self, cards_model, rank_column):
        """
        Set model used to extract card info
        This model will also be used to rank cards:
            - The rank will be based on the card row
            - The displayed info will be the sorted column
        """
        changed = self._setCardsModel(cards_model)
        if self._rank_column != rank_column:
            self._rank_column = rank_column
            changed = True

        print("Set new cards model", self._rank_column, self._cards_model, changed)
        if changed:
            self._updatePixmap()


    def setCards(self, cards):
        """
        Set card postions as a list of ImageReader.CardArea
        """
        if self._cards == cards:
            return

        self._cards = cards
        self._updatePixmap()


    def paintEvent(self, event):
        if not self._pixmap:
            super().paintEvent(event)
            return

        if not self._scaled:
            self._scaled = self._pixmap.scaledToHeight(self.height(), Qt.SmoothTransformation)

        p = QPainter(self)
        x = (self.width() - self._scaled.width()) / 2
        y = (self.height() - self._scaled.height()) / 2
        p.drawPixmap(x, y, self._scaled)


    def resizeEvent(self, event):
        self._scaled = None
        super().resizeEvent(event)


    def _updatePixmap(self):
        self._pixmap = None
        self._scaled = None
        if not self._source_image:
            return

        pixmap = QPixmap(self._source_image)
        painter = QPainter(pixmap)

        pen = painter.pen()

        found = 0
        not_found = 0

        for data in self._cards:
            r = data.rect()

            if self._cards_model:
                row = None
                card_id = data.valueFromDatabase('id')
                if card_id:
                    found = found + 1
                    row = self._cards_model.rowOfCard(card_id)
                else:
                    not_found = not_found + 1

                #rank icon
                rank_img = self._getRankImage(row).scaledToWidth(96)
                rank_rect = QRect(QPoint(0, 0), rank_img.size())
                rank_rect.moveCenter(QPoint(r.center().x(), r.bottom() - 20))
                painter.drawPixmap(rank_rect, rank_img)

                if not row is None:
                    #rank text
                    if row < 3:
                        pen.setColor(Qt.black)
                        painter.setPen(pen)
                    else:
                        pen.setColor(Qt.white)
                        painter.setPen(pen)

                    txt = self._cards_model.data(self._cards_model.index(row, self._rank_column))
                    self._drawText(painter, rank_rect, row + 1, txt)

        print("Total found:", found)
        print("Total not found:", not_found)

        self._pixmap = pixmap
        self.update()


    def _drawText(self, painter, rect, rank, value):
        rect = rect.marginsRemoved(QMargins(6, 6, 6, 20))
        text_rect = QRect(rect.topLeft(), QSize(rect.width(), rect.height() / 2))

        font = painter.font()
        font.setPixelSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(text_rect, int(Qt.AlignTop | Qt.AlignHCenter), str(rank))

        text_rect = QRect(QPoint(rect.left(), rect.center().y()), QSize(rect.width(), rect.height() / 2))

        font.setBold(False)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, str(value))


    def _iconFilename(self, icon_name):
        app_dir = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(app_dir, "icons", icon_name)


    def _onModelChanged(self):
        self._model_change_timer.start(300)


    def _setCardsModel(self, model):
        if self._cards_model == model:
            return False

        if self._cards_model:
            for conn in self._cards_model_connections:
                self.disconnect(conn)
            self._cards_model_connections = []

        self._cards_model = model
        if self._cards_model:
            self._cards_model_connections.append(self._cards_model.rowsInserted.connect(self._onModelChanged))
            self._cards_model_connections.append(self._cards_model.rowsRemoved.connect(self._onModelChanged))
            self._cards_model_connections.append(self._cards_model.rowsMoved.connect(self._onModelChanged))
            self._cards_model_connections.append(self._cards_model.modelReset.connect(self._onModelChanged))
            self._cards_model_connections.append(self._cards_model.sortChanged.connect(self._onModelChanged))
            self._cards_model_connections.append(self._cards_model.filterChanged.connect(self._onModelChanged))

        return True


    def _getRankImage(self, rank):
        image_name = None
        if rank is None:
            image_name = 'rank_notfound.png'
        elif rank == 0:
            image_name = 'rank_gold.png'
        elif rank == 1:
            image_name = 'rank_silver.png'
        elif rank == 2:
            image_name = 'rank_bronze.png'
        else:
            image_name = 'rank_undefined.png'


        return self._loadImage(image_name)


    def _loadImage(self, image_name):
        if not image_name in self.IMAGE_CACHE:
            self.IMAGE_CACHE[image_name] = QPixmap(self._iconFilename(image_name))
        return self.IMAGE_CACHE[image_name]
