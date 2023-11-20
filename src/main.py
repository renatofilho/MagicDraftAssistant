""" Magic Draft Assistant """

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QStandardPaths

from MainWindow import MainWindow
from Database import createDatabase

def main():
    """ main """
    app = QApplication(sys.argv)
    app.setOrganizationName("Magic")
    app.setApplicationName("Draft4Magic")

    db_basedir = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    os.makedirs(db_basedir, exist_ok=True)
    db = createDatabase(os.path.join(db_basedir, "cards.db"))
    if not db:
        print("Fail to create database")
        return -1

    win = MainWindow(db)
    win.setMinimumSize(1280, 780)
    win.show()
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
