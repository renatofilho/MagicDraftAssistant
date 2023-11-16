from PySide6.QtCore import QSortFilterProxyModel

class CardsModelProxy(QSortFilterProxyModel):

    def __init__(self, source_model, parent = None):
        super().__init__(parent)
        self.setSourceModel(source_model)
        self._id_filter = None
        self._string_filter = None


    def applyIdFilter(self, ids):
        if self._id_filter == ids:
            return
        self._id_filter = ids
        self.invalidate()


    def applyStringFilter(self, value):
        if self._string_filter == value:
            return
        self._string_filter = value
        self.invalidate()


    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        source_index_id = source_model.index(source_row, 0, source_parent)
        source_index_name = source_model.index(source_row, 1, source_parent)

        if self._id_filter != None:
            if source_index_id.data() not in self._id_filter:
                return False

        if self._string_filter:
            return self._string_filter in source_index_name.data()

        return True
