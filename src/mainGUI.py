import sys
import cv2
from PyQt5.QtGui import QImage, QPixmap
from qtpy import QtCore, QtGui, QtWidgets

from imageoperations import scale_image, draw_contours, print_stats, match_contours, get_contours
from objectdetection import create_subtractor
from tracking import create_tracker

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget, QLabel, QMainWindow, QAction, QFileDialog, QMessageBox, QPushButton, QApplication,\
    QSlider


class VideoCapture(QWidget):
    def __init__(self, filename, subtraction, scale, tracker_method, parentLayout):
        super(QWidget, self).__init__()
        self.videoFrame = QLabel()

        # Init timer
        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.nextFrameSlot)

        # Opencv capture and stats
        self.cap = cv2.VideoCapture(str(filename[0]))
        self.length = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_rate = self.cap.get(cv2.CAP_PROP_FPS)
        self.duration = self.length / self.cap.get(cv2.CAP_PROP_FPS)
        self.trackerMethod = tracker_method
        self.scale = scale

        # Program variables
        self.positionSlider = QSlider(Qt.Horizontal)
        self.positionSlider.setRange(0, self.duration)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        self.rawFrame = None
        self.trackers = []
        self.subtractor = create_subtractor(self.scale, subtraction)

        self.trackersB = QPushButton('Trackers', self)
        self.trackersB.setFixedWidth(50)
        self.trackersB.clicked.connect(self.init_trackers)

        self.last_ids = []
        self.last_contours = []

        parentLayout.addWidget(self.positionSlider, 1, 1, 1, 4)
        parentLayout.addWidget(self.trackersB, 1, 0, 1, 1)
        # parentLayout.addRow(self.positionSlider, self.trackersB)
        parentLayout.addWidget(self.videoFrame, 2, 0, 2, 4)
        # parentLayout.addRow(self.videoFrame)

    def setPosition(self, position):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000)

    def init_trackers(self):
        self.timer.stop()
        winname = "Roi selection"
        rois = cv2.selectROIs(winname, img=self.rawFrame, fromCenter=False)
        cv2.destroyWindow(winname)
        for roi in rois:
            tracker = create_tracker(self.trackerMethod, roi, self.rawFrame)
            self.trackers.append(tracker)
        self.timer.start()

    def nextFrameSlot(self):
        start = cv2.getTickCount()

        # read frame
        ret, frame = self.cap.read()

        if ret:
            # scale image
            frame, width, height = scale_image(frame, self.scale)
            self.rawFrame = frame.copy()

            # operate with frame (tracking and subtraction)
            if len(self.trackers) > 0:
                for t in self.trackers:
                    t.update(self.rawFrame, frame)

            processed = self.subtractor.apply(self.rawFrame)

            contours = get_contours(processed)
            cont_ids = match_contours(self.last_contours, contours, self.last_ids)
            draw_contours(frame, cont_ids, contours)

            # add stats
            frame = print_stats(frame, width, height, start, self.cap.get(cv2.CAP_PROP_POS_MSEC), self.duration)
            self.last_ids = cont_ids
            self.last_contours = contours

            w = self.videoFrame.width()
            h = self.videoFrame.height()

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_CUBIC)
            img = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
            pix = QPixmap.fromImage(img)
            self.positionSlider.setValue(int(round(self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)))
            self.videoFrame.setPixmap(pix)

    def start(self):
        # Start timer with timeout of 1000/fps ms
        self.timer.start(1000.0/self.frame_rate)

    def pause(self):
        self.timer.stop()

    def deleteLater(self):
        self.cap.release()
        super(QWidget, self).deleteLater()


class ControlWindow(QMainWindow):
    def __init__(self):
        super(ControlWindow, self).__init__()
        self.setGeometry(50, 50, 800, 600)
        self.setWindowTitle("PyTrack")

        self.capture = None

        self.isVideoFileLoaded = False
        self.videoFileName = None

        self.quitAction = QAction("Salir", self)
        self.quitAction.setShortcut("Ctrl+Q")
        self.quitAction.triggered.connect(self.closeApplication)

        self.openVideoFile = QAction("Abrir vídeo", self)
        self.openVideoFile.setShortcut("Ctrl+Shift+V")
        self.openVideoFile.triggered.connect(self.loadVideoFile)

        self.mainMenu = self.menuBar()
        self.fileMenu = self.mainMenu.addMenu('Archivo')
        self.fileMenu.addAction(self.openVideoFile)
        self.fileMenu.addAction(self.quitAction)

        self.wid = QWidget()
        self.setCentralWidget(self.wid)
        self.buildGUI()

    def keyPressEvent(self, a0: QtGui.QKeyEvent):
        if a0.key() == QtCore.Qt.Key_T:
            if self.capture is not None and self.isVideoFileLoaded:
                self.capture.init_trackers()

    def setPosition(self, position):
        self.capture.setPosition(position)

    def startCapture(self):
        if self.videoFileName is not None:
            if not self.capture and self.isVideoFileLoaded:
                if self.meanshift.isChecked():
                    self.capture = VideoCapture(self.videoFileName, self.comboBox.currentText(),
                                                self.scaleFactor.value(), 'meanshift', self.gridLayout)
                else:
                    self.capture = VideoCapture(self.videoFileName, self.comboBox.currentText(),
                                                self.scaleFactor.value(), 'camshift', self.gridLayout)
                self.pauseButton.clicked.connect(self.capture.pause)
            self.capture.start()

    def endCapture(self):
        self.capture.deleteLater()
        self.capture = None

    def loadVideoFile(self):
        self.videoFileName = QFileDialog.getOpenFileName(self, 'Select a Video File', filter="Video (*.avi *.mp4)")
        self.isVideoFileLoaded = True

    def closeApplication(self):
        choice = QMessageBox.question(self, 'Message', 'Do you really want to exit?', QMessageBox.Yes | QMessageBox.No)
        if choice == QMessageBox.Yes:
            print("Closing....")
            sys.exit()
        else:
            pass

    # noinspection PyAttributeOutsideInit
    def buildGUI(self):
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setContentsMargins(10, 25, 10, 10)
        self.gridLayout.setSpacing(10)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label_2 = QtWidgets.QLabel(self)
        self.label_2.setText("Método de sustracción de fondo:")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_3.addWidget(self.label_2)
        self.comboBox = QtWidgets.QComboBox(self)
        self.comboBox.setObjectName("comboBox")
        self.comboBox.addItem("MOG2")
        self.comboBox.addItem("MOG")
        self.comboBox.addItem("KNN")
        self.comboBox.addItem("resta")
        self.verticalLayout_3.addWidget(self.comboBox)
        self.gridLayout.addLayout(self.verticalLayout_3, 0, 3, 1, 1)
        self.scaleForm = QtWidgets.QVBoxLayout()
        self.scaleForm.setSpacing(0)
        self.scaleForm.setObjectName("scaleForm")
        self.scaleLabel = QtWidgets.QLabel(self)
        self.scaleLabel.setText("Escalado de imagen:")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.scaleLabel.sizePolicy().hasHeightForWidth())
        self.scaleLabel.setSizePolicy(sizePolicy)
        self.scaleLabel.setObjectName("scaleLabel")
        self.scaleForm.addWidget(self.scaleLabel)
        self.scaleFactor = QtWidgets.QDoubleSpinBox(self)
        self.scaleFactor.setMaximum(1.0)
        self.scaleFactor.setSingleStep(0.1)
        self.scaleFactor.setObjectName("scaleFactor")
        self.scaleFactor.setValue(1.0)
        self.scaleForm.addWidget(self.scaleFactor)
        self.gridLayout.addLayout(self.scaleForm, 0, 2, 1, 1)
        self.pauseButton = QtWidgets.QPushButton(self)
        self.pauseButton.setText("Pause")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pauseButton.sizePolicy().hasHeightForWidth())
        self.pauseButton.setSizePolicy(sizePolicy)
        self.pauseButton.setMaximumSize(QtCore.QSize(16777215, 50))
        self.pauseButton.setObjectName("pauseButton")
        self.gridLayout.addWidget(self.pauseButton, 0, 1, 1, 1)
        self.startButton = QtWidgets.QPushButton(self)
        self.startButton.setText("Play")
        self.startButton.clicked.connect(self.startCapture)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.startButton.sizePolicy().hasHeightForWidth())
        self.startButton.setSizePolicy(sizePolicy)
        self.startButton.setMaximumSize(QtCore.QSize(16777215, 50))
        self.startButton.setObjectName("startButton")
        self.gridLayout.addWidget(self.startButton, 0, 0, 1, 1)
        self.groupBox = QtWidgets.QGroupBox(self)
        self.groupBox.setTitle("Método de tracking")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMinimumSize(QtCore.QSize(0, 65))
        self.groupBox.setObjectName("groupBox")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.groupBox)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(0, 10, 141, 50))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.trackerForm = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.trackerForm.setContentsMargins(9, 0, 0, 0)
        self.trackerForm.setObjectName("trackerForm")
        self.meanshift = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.meanshift.setText("Meanshift")
        self.meanshift.click()
        self.trackerForm.addWidget(self.meanshift)
        self.camshift = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.camshift.setText("Camshift")
        self.trackerForm.addWidget(self.camshift)
        self.gridLayout.addWidget(self.groupBox, 0, 4, 1, 1)

        self.wid.setLayout(self.gridLayout)


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == '__main__':
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    window = ControlWindow()
    window.show()
    sys.exit(app.exec_())
