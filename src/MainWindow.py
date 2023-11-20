import os
import tempfile

from PySide6.QtWidgets import QMainWindow, QFileDialog, QStyledItemDelegate, QComboBox, QLabel
from PySide6.QtWidgets import QTabWidget, QTableView, QAbstractItemView, QWidget, QFormLayout
from PySide6.QtWidgets import QLineEdit, QCheckBox, QProgressBar
from PySide6.QtCore import QStandardPaths, QFileSystemWatcher, Qt, QSize
from PySide6.QtCore import QDirIterator, QSettings, QFileInfo, QEvent
from PySide6.QtGui import QPixmap, QIcon, QActionGroup, QCursor

from ImageReader import ImageReader
from CardsModel import CardsModel
from CardsModelProxy import CardsModelProxy
from CardWidget import CardWidget
from Database import CardDB, SevenTeenLandsCardDB


class ComboBoxTierEditor(QStyledItemDelegate):
    """Custom delegate that uses a combo-box with pre-defined list of tiers values"""
    def __init__(self, parent = None):
        super().__init__(parent)


    def createEditor(self, parent, _option, _index):
        combo = QComboBox(parent)
        combo.addItems(["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"])
        return combo


    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data())


    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def displayText(self, value, _locale):
        return value


class MainWindow(QMainWindow):
    """Application main window"""

    def __init__(self, database, parent = None):
        super().__init__(parent)
        self._db = database
        self._source_image_filename = ""
        self._card_set = None
        self._track_dir = None
        self._show_card_images = False

        self._dir_watcher = QFileSystemWatcher(self)
        self._dir_watcher.directoryChanged.connect(self.refresh)

        self._img_reader = ImageReader(database, self)
        self._img_reader.progress.connect(self._onImageReaderProgressChanged)
        self._img_reader.finished.connect(self._onImageReaderFinished)

        self._cards_model = CardsModel(database, self)

        self._setupUi()
        self._loadSettings()


    def _setupMenu(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("Configure images dir", self._configImageSourceDir)
        file_menu.addAction("Download database", self._donwloadDatabase)
        file_menu.addAction("Import 17lands info", self._importSeventeenLandsInfo)


    def _setupToolBar(self):
        tool_bar = self.addToolBar("Sets")
        tool_bar.setObjectName("Sets")
        tool_bar.setIconSize(QSize(36, 36))

        act_group = QActionGroup(self)
        act_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        self._addCollectionAction(tool_bar, act_group, "Wilds of Eldraine.svg", "woe")
        self._addCollectionAction(tool_bar, act_group, "The Lost Caverns of Ixalan.svg", "lci")


    def _setupUi(self):
        self._setupMenu()
        self._setupToolBar()
        self._result_image = QLabel(self)
        self._result_image.setScaledContents(True)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._result_image, "Source Image")

        widget = QWidget(self)
        self._result_list = QTableView(widget)
        self._result_list.installEventFilter(self)
        self._result_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._result_list.setItemDelegateForColumn(3, ComboBoxTierEditor(self))
        self._result_list.setItemDelegateForColumn(4, ComboBoxTierEditor(self))
        self._result_list.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._result_list.setSortingEnabled(True)

        sort_model = CardsModelProxy(self._cards_model, self)
        self._result_list.setModel(sort_model)
        self._result_list.setColumnHidden(0, True)
        self._result_list.setColumnHidden(2, True)
        self._result_list.setColumnWidth(1, 400)
        self._result_list.setMinimumWidth(600)

        form_layout = QFormLayout(widget)

        self._search_field = QLineEdit(widget)
        form_layout.addRow("Search:", self._search_field)
        self._search_field.textChanged.connect(self._updateFilterByText)

        self._use_image_filter = QCheckBox(widget)
        self._use_image_filter.setChecked(True)
        self._use_image_filter.stateChanged.connect(self._updateFilterByImage)
        form_layout.addRow("Use image as filter:", self._use_image_filter)

        form_layout.addRow(self._result_list)

        self._tabs.addTab(widget, "Results")
        self.setCentralWidget(self._tabs)
        self._tabs.setCurrentIndex(1)

        self._card_widget = CardWidget(self)
        self._card_widget.setVisible(False)


        status_bar = self.statusBar()
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        status_bar.addWidget(QWidget(self), 1.0)
        status_bar.addPermanentWidget(self._progress_bar)

        self._result_list.entered.connect(self._onResultListMouseEntered)


    def setTrackDir(self, dirname):
        print("Try set trackDir", dirname)
        if self._track_dir == dirname:
            return

        if self._track_dir:
            self._dir_watcher.removePath(self._track_dir)

        self._track_dir = dirname
        if self._track_dir:
            self._dir_watcher.addPath(self._track_dir)

        print("Track dir set:", self._track_dir)
        self.refresh()


    def setCardSet(self, set_name):
        if self._card_set == set_name:
            return

        self._card_set = set_name
        self._cards_model.setCardSet(self._card_set)
        self.setWindowTitle(f"Card set:{set_name.upper()}")
        self.refresh()


    def refresh(self):
        if not self._track_dir:
            print("Track dir not set yet")
            return

        it  = QDirIterator(self._track_dir, QDirIterator.NoIteratorFlags)
        last_modified = None
        recent_file = None
        while it.hasNext():
            info = QFileInfo(it.next())
            if not info.isFile():
                continue
            last_update = info.lastModified()
            if not last_modified or (last_modified < last_update):
                last_modified = last_update
                recent_file = info.absoluteFilePath()

        if not recent_file:
            return

        self._source_image_filename = recent_file
        self._img_reader.reload(self._card_set, recent_file)


    def closeEvent(self, event):
        self._saveSettings()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        ret = super().eventFilter(watched, event)
        if watched != self._result_list:
            return ret

        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Alt:
            self._show_card_images = True
        elif event.type() == QEvent.KeyRelease and event.key() == Qt.Key_Alt:
            self._show_card_images = False
        elif event.type() == QEvent.Leave:
            self._show_card_images = False
        else:
            return ret

        if self._show_card_images:
            pos = self._result_list.viewport().mapFromGlobal(QCursor.pos())
            self._result_list.setMouseTracking(True)
            self._onResultListMouseEntered(self._result_list.indexAt(pos))
        else:
            self._onResultListMouseEntered(None)
            self._result_list.setMouseTracking(False)
        return ret



    def _saveSettings(self):
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("trackDir", self._track_dir)
        settings.setValue("collection", self._card_set)
        settings.setValue("sortColumn", self._result_list.model().sortColumn())


    def _loadSettings(self):
        settings = QSettings()
        self.restoreGeometry(settings.value("geometry"))
        self.restoreState(settings.value("windowState"))
        self.setTrackDir(settings.value("trackDir", QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)[0]))
        self.setCardSet(settings.value("collection", "woe"))


    def _donwloadDatabase(self):
        card = CardDB(self._db)
        card.downloadSet(self._card_set)
        self._cards_model.reload()


    def _importSeventeenLandsInfo(self):
        desired_file,_ = QFileDialog.getOpenFileName(self, "Import 17lands info", QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)[0])
        if not desired_file:
            return

        db = SevenTeenLandsCardDB(self._db)
        db.importFromFile(self._card_set, desired_file)
        self._cards_model.reload()


    def _configImageSourceDir(self):
        desired_dir = QFileDialog.getExistingDirectory(self, "Select directory with screenshots", self._track_dir)
        if not desired_dir:
            return

        self.setTrackDir(desired_dir)


    def _updateFilterByImage(self, _state):
        if self._use_image_filter.checkState() == Qt.Checked:
            self._result_list.model().applyIdFilter(self._img_reader.cardsId())
        else:
            self._result_list.model().applyIdFilter(None)


    def _updateFilterByText(self):
        self._result_list.model().applyStringFilter(self._search_field.text())


    def _addCollectionAction(self, tool_bar, act_group, img, name):
        app_dir = os.path.dirname(os.path.realpath(__file__))
        icon_pixmap = QPixmap(os.path.join(app_dir, "icons", img))

        def onActionToggled(checked):
            if checked:
                self.setCardSet(name)

        act = tool_bar.addAction(QIcon(icon_pixmap), name)
        act.setActionGroup(act_group)
        act.setCheckable(True)
        act.toggled.connect(onActionToggled)
        return act


    def _onImageReaderFinished(self):
        self._img_reader.writeOutputImage(self._imgResultFilename())

        pic = QPixmap(self._imgResultFilename())
        self._result_image.setPixmap(pic)
        self._updateFilterByImage(self._use_image_filter.checkState())


    def _onImageReaderProgressChanged(self, progress):
        self._progress_bar.setValue(100 * progress)


    def _onResultListMouseEntered(self, index):
        if not self._show_card_images:
            self._card_widget.hide()
            return

        if not index.isValid():
            self._card_widget.hide()
            return

        if index.column() != 1:
            self._card_widget.hide()
            return

        target_index = self._result_list.model().mapToSource(index)
        image_url = self._cards_model.cardImage(target_index)
        if image_url:
            self._card_widget.setUrl(image_url)
            self._card_widget.show()
            self._card_widget.move(QCursor.pos(self._card_widget.screen()))


    def _imgResultFilename(self):
        return os.path.join(tempfile.gettempdir(), "mda_result_image.png")
