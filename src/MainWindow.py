import os

from PySide6.QtWidgets import QMainWindow, QFileDialog, QStyledItemDelegate, QComboBox, QLabel
from PySide6.QtWidgets import QTabWidget, QTableView, QScrollArea, QAbstractItemView, QWidget, QFormLayout
from PySide6.QtWidgets import QLineEdit, QCheckBox, QProgressBar
from PySide6.QtCore import QStandardPaths, QFileSystemWatcher, Qt, QSize
from PySide6.QtCore import QDirIterator, QSettings, QFileInfo
from PySide6.QtGui import QPixmap, QIcon, QActionGroup, QCursor

from ImageReader import ImageReader
from CardsModel import CardsModel
from CardsModelProxy import CardsModelProxy
from CardWidget import CardWidget
from Database import CardDB, SevenTeenLandsCardDB


class ComboBoxTierEditor(QStyledItemDelegate):
    def __init__(self, parent = None):
        super().__init__(parent)


    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"])
        return combo


    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data())


    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def displayText(self, value, locale):
        return value


class MainWindow(QMainWindow):
    IMG_RESULT_FILENAME = "/tmp/result.png"

    def __init__(self, database, parent = None):
        super().__init__(parent)
        self._db = database
        self._sourceImageFilename = ""
        self._card_set = None
        self._track_dir = None
        self._show_card_images = False

        self._dir_watcher = QFileSystemWatcher(self)
        self._dir_watcher.directoryChanged.connect(self.refresh)

        self._imgReader = ImageReader(database, self)
        self._imgReader.progress.connect(self._onImageReaderProgressChanged)
        self._imgReader.finished.connect(self._onImageReaderFinished)

        self._cardsModel = CardsModel(database, self)

        self.setupUi()
        self._loadSettings()


    def setupUi(self):
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction("Configure images dir", self._configImageSourceDir)
        fileMenu.addAction("Download database", self._donwloadDatabase)
        fileMenu.addAction("Import 17lands info", self._importSeventeenLandsInfo)

        toolBar = self.addToolBar("Sets")
        toolBar.setObjectName("Sets")
        toolBar.setIconSize(QSize(36, 36))

        act_group = QActionGroup(self)
        act_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        act = self._addCollectionAction(toolBar, act_group, "Wilds of Eldraine.svg", "woe")
        act.setChecked(True)

        act = self._addCollectionAction(toolBar, act_group, "The Lost Caverns of Ixalan.svg", "lci")

        self._resultImage = QLabel(self)

        self._tabs = QTabWidget(self)

        scrollArea = QScrollArea(self)
        scrollArea.setWidget(self._resultImage)
        self._tabs.addTab(scrollArea, "Source Image")

        widget = QWidget(self)
        self._resultList = QTableView(widget)
        self._resultList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._resultList.setItemDelegateForColumn(3, ComboBoxTierEditor(self))
        self._resultList.setItemDelegateForColumn(4, ComboBoxTierEditor(self))
        self._resultList.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._resultList.setSortingEnabled(True)

        sortModel = CardsModelProxy(self._cardsModel, self)
        self._resultList.setModel(sortModel)
        self._resultList.setColumnHidden(0, True)
        self._resultList.setColumnHidden(2, True)
        self._resultList.setColumnWidth(1, 400)
        self._resultList.setMinimumWidth(600)

        formLayout = QFormLayout(widget)

        self._search_field = QLineEdit(widget)
        formLayout.addRow("Search:", self._search_field)
        self._search_field.textChanged.connect(self._updateFilterByText)

        self._use_image_filter = QCheckBox(widget)
        self._use_image_filter.setChecked(True)
        self._use_image_filter.stateChanged.connect(self._updateFilterByImage)
        formLayout.addRow("Use image as filter:", self._use_image_filter)

        formLayout.addRow(self._resultList)

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

        self._resultList.entered.connect(self._onResultListMouseEntered)


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
        self._cardsModel.setCardSet(self._card_set)
        self.setWindowTitle("Card set:{}".format(set_name.upper()))

        print("card set set:",set_name)
        self.refresh()


    def refresh(self):
        if not self._track_dir:
            print("Track dir not set yet")
            return

        it  = QDirIterator(self._track_dir, QDirIterator.NoIteratorFlags)
        lastModified = None
        recentFile = None
        while (it.hasNext()):
            info = QFileInfo(it.next())
            if not info.isFile():
                continue
            lastUpdate = info.lastModified()
            if not lastModified or (lastModified < lastUpdate):
                lastModified = lastUpdate
                recentFile = info.absoluteFilePath()

        if not recentFile:
            return

        self._sourceImageFilename = recentFile
        self._imgReader.reload(self._card_set, recentFile)


    def closeEvent(self, event):
        self._saveSettings()
        super().closeEvent(event)


    def keyPressEvent(self, event):
        self._show_card_images = event.key() == Qt.Key_Shift
        self._resultList.setMouseTracking(self._show_card_images)
        if self._show_card_images:
            pos = self._resultList.viewport().mapFromGlobal(QCursor.pos())
            self._onResultListMouseEntered(self._resultList.indexAt(pos))
        return super().keyPressEvent(event)


    def keyReleaseEvent(self, event):
        if self._show_card_images and event.key() == Qt.Key_Shift:
            self._show_card_images = False
            self._onResultListMouseEntered(None)
        self._resultList.setMouseTracking(self._show_card_images)
        return super().keyReleaseEvent(event)


    def _saveSettings(self):
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("trackDir", self._track_dir)
        settings.setValue("collection", self._card_set)
        settings.setValue("sortColumn", self._resultList.model().sortColumn())


    def _loadSettings(self):
        settings = QSettings()
        self.restoreGeometry(settings.value("geometry"))
        self.restoreState(settings.value("windowState"))
        self.setTrackDir(settings.value("trackDir", QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)[0]))
        self.setCardSet(settings.value("collection", "woe"))


    def _donwloadDatabase(self):
        card = CardDB(self._db)
        card.downloadSet(self._card_set)
        self._cardsModel.reload()


    def _importSeventeenLandsInfo(self):
        desired_file,_ = QFileDialog.getOpenFileName(self, "Import 17lands info", QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)[0])
        if not desired_file:
            return

        db = SevenTeenLandsCardDB(self._db)
        db.importFromFile(self._card_set, desired_file)
        self._cardsModel.reload()


    def _configImageSourceDir(self):
        desired_dir = QFileDialog.getExistingDirectory(self, "Select directory with screenshots", self._track_dir)
        if not desired_dir:
            return

        self.setTrackDir(desired_dir)


    def _updateFilterByImage(self, state):
        if self._use_image_filter.checkState() == Qt.Checked:
            self._resultList.model().applyIdFilter(self._imgReader.cardsId())
        else:
            self._resultList.model().applyIdFilter(None)


    def _updateFilterByText(self):
        self._resultList.model().applyStringFilter(self._search_field.text())


    def _addCollectionAction(self, toolbar, act_group, img, name):
        app_dir = os.path.dirname(os.path.realpath(__file__))
        icon_pixmap = QPixmap(os.path.join(app_dir, "icons", img))

        def onActionToggled(checked):
            if checked:
                self.setCardSet(name)

        act = toolbar.addAction(QIcon(icon_pixmap), name)
        act.setActionGroup(act_group)
        act.setCheckable(True)
        act.toggled.connect(onActionToggled)
        return act


    def _onImageReaderFinished(self):
        self._imgReader.writeOutputImage(MainWindow.IMG_RESULT_FILENAME)

        pic = QPixmap(MainWindow.IMG_RESULT_FILENAME)
        self._resultImage.setPixmap(pic)
        self._resultImage.setMinimumSize(pic.size())
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

        target_index = self._resultList.model().mapToSource(index)
        image_url = self._cardsModel.cardImage(target_index)
        if image_url:
            self._card_widget.setUrl(image_url)
            self._card_widget.show()
            self._card_widget.move(QCursor.pos())
