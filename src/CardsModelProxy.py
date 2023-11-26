""" CardsModelProxy """

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal

class CardsModelProxy(QSortFilterProxyModel):
    """ Sort model used to filter cards """

    sortChanged = Signal(int, Qt.SortOrder)
    filterChanged = Signal()

    def __init__(self, source_model, parent = None):
        super().__init__(parent)
        self.setSourceModel(source_model)
        self._id_filter = None
        self._string_filter = None


    def applyIdFilter(self, ids):
        """
        Filter cards based on a list of ids
        """
        if self._id_filter == ids:
            return
        self._id_filter = ids
        self.invalidate()
        self.filterChanged.emit()


    def applyStringFilter(self, value):
        """
        Filter cards based on name
        """
        if self._string_filter == value:
            return
        self._string_filter = value
        self.invalidate()
        self.filterChanged.emit()


    def rowOfCard(self, card_id):
        """
        Return the current row for the card_id
        """
        for r in range(self.rowCount()):
            if self.data(self.index(r, 0)) == card_id:
                return r
        return None


    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        source_index_id = source_model.index(source_row, 0, source_parent)
        source_index_name = source_model.index(source_row, 1, source_parent)

        if self._id_filter is not None:
            if source_index_id.data() not in self._id_filter:
                return False

        if self._string_filter:
            return self._string_filter in source_index_name.data()

        return True


    def sort(self, column, order = Qt.AscendingOrder):
        super().sort(column, order)
        self.sortChanged.emit(column, order)
