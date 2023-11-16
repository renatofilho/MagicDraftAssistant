from PIL import Image
import pytesseract
import cv2 
import numpy as np
import re

from PySide6.QtCore import QObject, Signal, QFile, QThread, QRect
from Database import CardDB
from Calibrations import CalibrationList

class TextExtractTask(QThread):
    progress = Signal(float)

    def __init__(self, card_set, img, calibration, parent = None):
        super().__init__(parent)
        self._source_img = img
        self._result = []
        self._card_set = card_set
        self._calibration = CalibrationList.findCalibrationForImage(img)


    def _applyFilters(self, img):
        kernel = np.ones((6,6),np.uint8)
        return cv2.erode(img, kernel, iterations = 1)


    def _extractText(self, img, idx):
        cv2.imwrite(f"/tmp/text{idx}.png",img)
        img = Image.open(f"/tmp/text{idx}.png")
        custom_config = r'--oem 3 --psm 7'
        txt = pytesseract.image_to_string(img, config=custom_config)
        txt = "".join([x for x in txt if x.isprintable()]).strip()
        txt = re.sub(r'[§)(\@‘\d{|’:]', ' ', txt).strip()

        words = txt.split(' ')
        if len(words[0]) < 3:
            words = words[1:]

        if words and len(words[-1]) < 3:
            words = words[0:-1]
        return " ".join(words).strip()


    def run(self):
        if self._calibration:
            self._runWithCalibration()
            return

        img = self._applyFilters(self._source_img)
        _, threshold = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        self._result = []

        p = 0.0
        max_p = len(contours)
        for contour in contours:
            p = p+1.0
            self.progress.emit(p/max_p)

            approx = cv2.approxPolyDP(contour, 0.01 * cv2.arcLength(contour, True), True)
            M = cv2.moments(contour)
            if M['m00'] != 0.0:
                x = int(M['m10']/M['m00'])
                y = int(M['m01']/M['m00'])


            if self.isInterruptionRequested():
                return

            if len(approx) < ImageReader.MAX_VERTICES:
                rect = cv2.minAreaRect(contour)
                if (rect[2] != 90):
                    continue
                (height, width) = rect[1]
                if width < ImageReader.MIN_WIDTH:
                    continue
                if height < ImageReader.MIN_HEIGHT:
                    continue
                if height > ImageReader.MAX_HEIGHT:
                    continue
                if height > width:
                    continue
                box = cv2.boxPoints(rect)
                box = np.int0(box)

                (x, y) = box[0]
                x1 = box[1][0]
                y1 = box[2][1]

                #i = len(self._result)
                #crop_img = self._source_img[y:y1, x+ImageReader.LEFT_MARGIN:x1-ImageReader.RIGHT_MARGIN]
                #txt = self._extractText(crop_img, i)
                #if not txt:
                #    continue
                txt = ""

                self._result.append(ImageArea(QRect(x, y, x1-x, y1-y), txt))

                if self.isInterruptionRequested():
                    return

    def _transformation1(self, img):
        return img

    def _transformation2(self, img):
        _, result = cv2.threshold(img, 100, 255, cv2.THRESH_BINARY)
        return result

    def _runWithCalibration(self):
        p = 0
        rects = self._calibration.allRects()
        max_p = len(rects)
        img = self._source_img

        for rect in rects:
            texts = []
            for transform in [self._transformation1, self._transformation2]:
                img = transform(self._source_img)
                crop_img = img[rect.top():rect.bottom(), rect.left():rect.right()]
                txt = self._extractText(crop_img, p)
                if txt:
                    texts.append(txt)

            self._result.append(ImageArea(rect, texts))

            p = p +1
            self.progress.emit(p/max_p)


class ImageArea(object):
    def __init__(self, rect, texts):
        self._rect = rect
        self._texts = texts
        self._card = None


class ImageReader(QObject):
    MAX_VERTICES = 50
    MIN_WIDTH = 100
    MIN_HEIGHT = 5
    MAX_HEIGHT = 50
    LEFT_MARGIN = 0
    RIGHT_MARGIN = 45
    
    started = Signal()
    finished = Signal()
    progress = Signal(float)

    def __init__(self, db, parent = None):
        super().__init__(parent)
        self._data = []
        self._db = db
        self._current_thread = None
        self._calibration = []


    def reload(self, card_set, filename):
        self.started.emit()
        self.progress.emit(0.0)

        if QFile.exists(filename):
            self._rgb = cv2.imread(filename)
            self._gray = cv2.cvtColor(self._rgb, cv2.COLOR_BGR2GRAY)
        else:
            print(f"Source image does not exists: {filename}")

        if self._current_thread:
            self._current_thread.requestInterruption()
            self._current_thread.wait()
            del self._current_thread

        self._current_thread = TextExtractTask(card_set, self._gray, self)
        self._current_thread.progress.connect(self.progress)
        self._current_thread.finished.connect(self._onThreadFinished)
        self._current_thread.start()


    def _onThreadFinished(self):
        card_db = CardDB(self._db)
        card_set = self._current_thread._card_set
        for data in self._current_thread._result:
            for text in data._texts:
                data._card = self._findCard(card_db, card_set, text)
                if data._card:
                    break

        self._data = self._current_thread._result
        self.progress.emit(1.0)
        self.finished.emit()


    def _findCard(self, card_db, card_set, name):
        if not name:
            return None
        if len(name) < 5:
            return None
        card_name = name
        row = card_db.list("set_ = \"{}\" AND name LIKE \"%{}%\"".format(card_set, card_name))
        if not row:
            return None

        return row[0]


    def writeOutputImage(self, outputFileName):
        output_image = self._rgb.copy()
        found = 0
        notFound = 0

        for data in self._data:
            if not data._card:
                continue

            card_name = data._card.get('name').value()
            print("Text: [{}] Uri: [{}]".format(card_name, data._card.get('scryfall_uri', '')))
            cv2.rectangle(output_image, (data._rect.left(), data._rect.top()),  (data._rect.right(), data._rect.bottom()), (0,255,0), 2)
            cv2.putText(output_image, '{}'.format(card_name), (data._rect.left(), data._rect.top()), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            found = found + 1
            
        print("Total found:", found)

        print("Not found:")
        for data in self._data:
            if not data._card:
                print("Text: [{}]".format(",".join(data._texts)))

                notFound += notFound + 1
                cv2.rectangle(output_image, (data._rect.left(), data._rect.top()),  (data._rect.right(), data._rect.bottom()), (0,0,255), 2)

        cv2.imwrite(outputFileName, output_image)


    def cardsId(self):
        ids = []
        for data in self._data:
            if data._card:
                ids.append(data._card["id"].value())

        return ids
