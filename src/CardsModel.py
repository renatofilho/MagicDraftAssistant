""" CardsModel """

import re

from PySide6.QtCore import QAbstractTableModel, Qt, QSize
from PySide6.QtGui import QImage, QPainter

from Database import CardDB, SevenTeenLandsCardDB, UserFieldsDB
from RemoteImage import RemoteImage

class CardData():
    """ Card Information """

    def __init__(self, model, card, seventeen_lands, user_fields):
        self._parent_model = model
        self._card = card
        self._seventeen_lands = seventeen_lands
        self._user_fields = user_fields
        self._mana_cost_full_image = None
        self._mana_cost_item_images = []


    def value(self, field_name):
        """
        return teh value of field_name in database
        """
        path = field_name.split('.')
        data = self._card
        if path[0] == "user_fields":
            data = self._user_fields
        elif path[0] == "seventeen_lands":
            data = self._seventeen_lands

        if data:
            return data[path[1]].value()
        return ""


    def setValue(self, field_name, value):
        """
        set field_name value in database
        """
        path = field_name.split('.')
        if path[0] != "user_fields":
            print("Table not editable", path[0])
            return False
        return self._user_fields[path[1]].setValue(value)


    def manaCostImage(self):
        """
        Create mana cost image to be used as decorator by the model
        """
        if self._mana_cost_full_image:
            return self._mana_cost_full_image

        mana_cost = self._card["mana_cost"].value().split('//')
        for cost in mana_cost:
            matches = re.finditer(r'{(\S)}', cost)
            for match in matches:
                icon_name = match.group(1)
                remote_image = RemoteImage(self._parent_model)
                remote_image.imageReady.connect(self._manaCostRemoteImageReady, Qt.QueuedConnection)
                remote_image.setUrl(f"https://svgs.scryfall.io/card-symbols/{icon_name}.svg", QSize(24, 24))
                self._mana_cost_item_images.append(remote_image)

        return None


    def _manaCostRemoteImageReady(self):
        for img in self._mana_cost_item_images:
            if not img.isReady():
                return

        images_count = len(self._mana_cost_item_images)
        if images_count == 0:
            return

        self._mana_cost_full_image = QImage(images_count * 30, 30, QImage.Format_ARGB32)
        self._mana_cost_full_image.fill(Qt.transparent)
        x = 0
        painter = QPainter(self._mana_cost_full_image)
        for img in self._mana_cost_item_images:
            scaled = img.image().scaledToHeight(24)
            painter.drawImage(x + 3, 3, scaled)
            x = x + 30

        self._mana_cost_item_images = []
        self._parent_model.notifyDecoratorChanged(self)


    def commitUserFields(self, db):
        """ Save changes on user_fields into the databased """
        return db.commit(self._user_fields)



class CardsModel(QAbstractTableModel):
    """ The main cards model with all tables linked """

    COLUMNS  = ["cards.id",
         "cards.name",
         "cards.uri",
         "cards.mana_cost",
         "user_fields.limited_tier",
         "user_fields.constructed_tier",
         "seventeen_lands.seen",
         "seventeen_lands.alsa",
         "seventeen_lands.picked",
         "seventeen_lands.ata",
         "seventeen_lands.gp",
         "seventeen_lands.gp_p",
         "seventeen_lands.gp_wr",
         "seventeen_lands.oh",
         "seventeen_lands.oh_wr",
         "seventeen_lands.gd",
         "seventeen_lands.gd_wr",
         "seventeen_lands.gih",
         "seventeen_lands.gih_wr",
         "seventeen_lands.gns",
         "seventeen_lands.gns_wr",
         "seventeen_lands.iwd"]

    EDIABLE_COLUMNS = [
         "user_fields.limited_tier",
         "user_fields.constructed_tier"
    ]

    def __init__(self, db, parent = None):
        super().__init__(parent)
        self._card_set = None
        self._data = []
        self._filter = None
        self._cards_db = CardDB(db)
        self._seventee_lands_db = SevenTeenLandsCardDB(db)
        self._user_fields_db = UserFieldsDB(db)

        # load titles
        self._titles = []
        for field_name in self.COLUMNS:
            path = field_name.split('.')
            table = self._cards_db
            if path[0] == "user_fields":
                table = self._user_fields_db
            elif path[0] == "seventeen_lands":
                table = self._seventee_lands_db
            self._titles.append(table.fieldByFieldName(path[1]).title())


    def setCardSet(self, set_name):
        """
        Set the card set used
        """
        if self._card_set == set_name:
            return
        self._card_set = set_name
        self.reload()


    def reload(self):
        """
        Reload data from database
        """
        if not self._card_set:
            return

        self.beginResetModel()
        self._data = []
        self._loadFromDatabase()
        self.endResetModel()


    def rowCount(self, parent):
        if parent.isValid():
            return 0

        return len(self._data)


    def columnCount(self, parent):
        if parent.isValid():
            return 0

        return len(self.COLUMNS)


    def headerData(self, section, orientation, role = Qt.DisplayRole):
        if (orientation == Qt.Horizontal) and (role == Qt.DisplayRole):
            return self._titles[section]

        return super().headerData(section, orientation, role)


    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        flag = super().flags(index)
        field_name = self.COLUMNS[index.column()]
        if field_name in self.EDIABLE_COLUMNS:
            return Qt.ItemIsEditable | flag
        return flag


    def data(self, index, role = Qt.DisplayRole):
        if not self.hasIndex(index.row(), index.column(), index.parent()):
            return None

        if role not in [Qt.DisplayRole, Qt.EditRole, Qt.DecorationRole]:
            return None


        data = self._data[index.row()]
        if index.column() == self.COLUMNS.index("cards.mana_cost"):
            if role == Qt.DecorationRole:
                img = data.manaCostImage()
                if img and not img.isNull():
                    return img
            return None

        return data.value(self.COLUMNS[index.column()])


    def setData(self, index, value, role):
        if not self.hasIndex(index.row(), index.column(), index.parent()):
            return False

        if role != Qt.EditRole:
            return False

        data = self._data[index.row()]
        if not self._commitData(data, index.column(), value):
            print("Failed to save data")
            return False

        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        return True


    def cardImage(self, index):
        """ Returns the url for the card image """
        if not self.hasIndex(index.row(), index.column(), index.parent()):
            return None

        data = self._data[index.row()]
        img = data.value("cards.image_uris")
        if img:
            return img["normal"]
        return ""


    def _commitData(self, data, column, value):
        field_name = self.COLUMNS[column]
        if not data.setValue(field_name, value):
            print("Fail to set data", field_name, value)
            return False

        if not data.commitUserFields(self._user_fields_db):
            print("Failed to commit dat", field_name, value)
            return False

        return True


    def _loadFromDatabase(self):
        where = None
        if self._card_set:
            where = f"set_ = '{self._card_set}'"

        lst = self._cards_db.list(where)
        if not lst:
            return

        for card in lst:
            card_id = card["id"].sqlValue()
            stl = self._seventee_lands_db.list(f"card_id = {card_id}")
            stl_data = None
            if stl and len(stl) == 1:
                stl_data = stl[0]

            userf = self._user_fields_db.list(f"card_id = {card_id}")
            user_data = None
            if not userf or len(userf) == 0:
                user_data = self._user_fields_db.addRow()
                user_data['card_id'].setSqlValue(card_id)
            else:
                user_data = userf[0]

            self._data.append(CardData(self, card, stl_data, user_data))


    def notifyDecoratorChanged(self, data):
        """ Used by CardData when the decoration mana image is ready """
        row = self._data.index(data)
        index = self.createIndex(row, self.COLUMNS.index("cards.mana_cost"))
        self.dataChanged.emit(index, index, [Qt.DecorationRole])
