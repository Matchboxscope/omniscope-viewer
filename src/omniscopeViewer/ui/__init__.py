from napari.viewer import Viewer
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QTabWidget,
    QWidget,
    QScrollArea,
    QFrame,
    QVBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QFileDialog
)
from superqt import QCollapsible
from omniscopeViewer.common import (
    THIRTY_FPS,
    WriterInfo,
    RecordType,
    FileFormat
)
from omniscopeViewer.control.devices import devicesDict, ICamera
from omniscopeViewer.control.devices.interface import NumberParameter
from omniscopeViewer.control import MainController
from omniscopeViewer.common import THIRTY_FPS, WriterInfo, RecordType, FileFormat
from omniscopeViewer.ui.widgets import (
    QFormLayout,
    QGroupBox,
    QPushButton,
    LabeledSlider,
    ComboBox,
    RecordHandling,
    CameraSelection,
    HardwareControl,
    ROIHandling,
    TimeLapseHandling
)
import numpy as np


class ViewerAnchor:
    """Class which handles the UI elements of the plugin."""

    def __init__(self, napari_viewer: Viewer, mainController: MainController) -> None:
        self.viewer = napari_viewer
        self.mainController = mainController
        self.mainLayout = QVBoxLayout()
        self.selectionWidget = CameraSelection()
        self.selectionWidget.setDeviceSelectionWidget(list(devicesDict.keys()))
        self.selectionWidget.setAvailableCameras(list(devicesDict.keys()))
        self.recordingWidget = RecordHandling()
        self.hwcontrolWidget = HardwareControl()
        self.timelapseWidget = TimeLapseHandling()

        self.mainLayout.addRow(self.selectionWidget.group)
        self.mainLayout.addRow(self.recordingWidget.group)
        self.mainLayout.addRow(self.hwcontrolWidget.group)
        self.mainLayout.addRow(self.timelapseWidget.group)
        verticalSpacer = QSpacerItem(0, 1, QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.mainLayout.setAlignment(
            self.selectionWidget.group, Qt.AlignmentFlag.AlignTop
        )

        self.cameraWidgetGroups = {}
        self.selectionWidget.newCameraRequested.connect(self.addCameraUI)
        self.recordingWidget.signals["snapRequested"].connect(self.snap)
        self.recordingWidget.signals["liveRequested"].connect(self.live)
        self.recordingWidget.signals["recordRequested"].connect(self.record)
        self.mainController.recordFinished.connect(
            lambda: self.recordingWidget.record.setChecked(False)
        )

        self.liveTimer = QTimer()
        self.liveTimer.timeout.connect(self._updateLiveLayers)
        self.liveTimer.setInterval(THIRTY_FPS)
        self.isFirstTab = True
        self.mainLayout.addItem(verticalSpacer)

    def addTabWidget(self, isFirstTab: bool):
        if isFirstTab:
            self.tabs = QTabWidget()
            self.mainLayout.insertWidget(self.mainLayout.count() - 1, self.tabs)
            self.isFirstTab = False
        else:
            pass

    def addCameraUI(self, interface: str, name: str, idx: int):
        self.addTabWidget(self.isFirstTab)
        camera: ICamera = devicesDict[interface](name, idx)
        cameraKey = f"{camera.name}:{camera.__class__.__name__}:{str(idx)}"

        cameraTab = QWidget()
        cameraTabLayout = QVBoxLayout()

        settingsLayout = QFormLayout()
        settingsGroup = QGroupBox()

        self.mainController.addCamera(cameraKey, camera)

        roiWidget = ROIHandling(camera.fullShape)
        roiWidget.signals["changeROIRequested"].connect(
            lambda roi: camera.changeROI(roi)
        )
        roiWidget.signals["fullROIRequested"].connect(lambda roi: camera.changeROI(roi))

        if interface == "MicroManager":
            cameraTabLayout.addWidget(camera.settingsWidget)

        else:
            scrollArea = QScrollArea()
            specificSettingsGroup = QWidget()
            specificSettingsLayout = QFormLayout()
            for name, parameter in camera.parameters.items():
                if len(name) > 15:
                    name = name[:15]
                if type(parameter) == NumberParameter:
                    widget = LabeledSlider(
                        (*parameter.valueLimits, parameter.value), name, parameter.unit
                    )
                    widget.signals["valueChanged"].connect(
                        lambda value, name=name: camera.changeParameter(name, value)
                    )
                else:  # ListParameter
                    widget = ComboBox(parameter.options, name)
                    widget.signals["currentTextChanged"].connect(
                        lambda text, name=name: camera.changeParameter(name, text)
                    )
                specificSettingsLayout.addRow(widget.label, widget.widget)

            specificSettingsGroup.setLayout(specificSettingsLayout)
            scrollArea.setWidget(specificSettingsGroup)
            scrollArea.setWidgetResizable(True)
            scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cameraTabLayout.addWidget(scrollArea)

        deleteButton = QPushButton("Delete camera")
        deleteButton.clicked.connect(lambda: self.deleteCameraUI(cameraKey))
        settingsLayout.addRow(deleteButton)
        settingsLayout.addRow(roiWidget)
        settingsGroup.setLayout(settingsLayout)
        cameraTabLayout.addWidget(settingsGroup)
        cameraTab.setLayout(cameraTabLayout)

        self.cameraWidgetGroups[cameraKey] = cameraTab
        self.tabs.addTab(cameraTab, cameraKey)

    def deleteCameraUI(self, cameraKey: str) -> None:
        self.mainController.deleteCamera(cameraKey)
        self.mainLayout.removeRow(self.cameraWidgetGroups[cameraKey])
        self.tabs.removeTab(self.tabs.currentIndex())
        if self.tabs.count() == 0:
            self.mainLayout.removeWidget(self.tabs)
            self.tabs.setParent(None)
            self.isFirstTab = True


    def timelapse(self, status: bool, period: int, zStackParams: list = (-100, 100, 20) ) -> None:
        if status:
            cameraKeys = list(self.cameraWidgetGroups.keys())
            writerInfo = WriterInfo(
                folder=self.recordingWidget.folderTextEdit.text(),
                filename=self.recordingWidget.filenameTextEdit.text(),
                fileFormat=self.recordingWidget.formatComboBox.currentEnum(),
                recordType=self.recordingWidget.recordComboBox.currentEnum(),
                stackSize=self.recordingWidget.recordSize,
                acquisitionTime=self.recordingWidget.recordSize
            )
            self.mainController.timelapse(cameraKeys, writerInfo, period, zStackParams)

    def record(self, status: bool) -> None:
        if status:
            # todo: add dynamic control
            cameraKeys = list(self.cameraWidgetGroups.keys())
            writerInfo = WriterInfo(
                folder=self.recordingWidget.folderTextEdit.text(),
                filename=self.recordingWidget.filenameTextEdit.text(),
                fileFormat=self.recordingWidget.formatComboBox.currentEnum(),
                recordType=self.recordingWidget.recordComboBox.currentEnum(),
                stackSize=self.recordingWidget.recordSize,
                acquisitionTime=self.recordingWidget.recordSize,
            )
            self.mainController.record(cameraKeys, writerInfo)
        else:
            self.mainController.stopRecord()

    def snap(self) -> None:
        for key in self.mainController.deviceControllers.keys():
            self._updateLayer(f"Snap {key}", self.mainController.snap(key))

    def live(self, status: bool) -> None:
        self.mainController.live(status)
        if status:
            self.liveTimer.start()
        else:
            self.liveTimer.stop()

    def _updateLiveLayers(self):
        for key, buffer in self.mainController.deviceLiveBuffer.items():
            # this copy may not be truly necessary
            # but it does not impact performance too much
            # so we keep it to avoid possible data corruption
            self._updateLayer(f"Live {key}", np.copy(buffer))

    def _updateLayer(self, layerKey: str, data: np.ndarray) -> None:
        try:
            # layer is recreated in case the image changes type (i.e. grayscale -> RGB and viceversa)
            if data.ndim != self.viewer.layers[layerKey].data.ndim:
                self.viewer.layers.remove(layerKey)
                self.viewer.add_image(data, name=layerKey)
            else:
                self.viewer.layers[layerKey].data = data
        except KeyError:
            # needed in case the layer of that live recording does not exist
            self.viewer.add_image(data, name=layerKey)
        except AttributeError:
            # list is coming, we want to display it as layers
            for index, iImage in enumerate(data):
                self.viewer.add_image(iImage, name=layerKey+str(index))
