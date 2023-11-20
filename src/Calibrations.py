from PySide6.QtCore import QRect, QPoint, QSize

class BaseCalibration(object):
    def __init__(self, resolution, x, y, w, h, spacing_x, spacing_y, rows, columns):
        self._resolution = resolution
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._spacing_x = spacing_x
        self._spacing_y = spacing_y
        self._rows = rows
        self._columns = columns

    def resolution(self):
        return self._resolution


    def getRect(self, row, column):
        x = (self._x + (column * self._spacing_x))
        y = (self._y + (row * self._spacing_y))
        return QRect(QPoint(x, y), QSize(self._w, self._h))


    def columnCount(self):
        return self._columns


    def rowCount(self):
        return self._rows

    def allRects(self):
        all = []
        for y in range(self._rows):
            for x in range(self._columns):
                all.append(self.getRect(y, x))
        return all


# This is calibration is based on a screen size 3840x2160
class Calibration_3840_2160(BaseCalibration):
    def __init__(self):
        super().__init__(resolution=QSize(3840, 2160), x=572, y=385, w=270, h=29, spacing_x=393, spacing_y=536, rows=3, columns=5)


############################
# Add more calibrations here
############################


class CalibrationList(object):
    ALL_CALIBRATIONS = {"3840x2160": Calibration_3840_2160()}

    def findCalibration(width, height):
        size_name = f"{width}x{height}"
        return CalibrationList.ALL_CALIBRATIONS.get(size_name, None)

    def findCalibrationForImage(img):
        h, w = img.shape
        return CalibrationList.findCalibration(w, h)
