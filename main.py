import multiprocessing
import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QTabWidget

from ui.JW8103A_Control import JW8103A_Control
from ui.MainWindow import MainWindow as JW8507MainWindow
from utils.config import load_app_config
from utils.数据桥接器 import PowerMeterBridge


class CombinedMainWindow(QMainWindow):
    def __init__(self, config=None, power_bridge=None):
        super().__init__()
        self.config = config or load_app_config()
        self.power_bridge = power_bridge or PowerMeterBridge.get_instance()
        self.setWindowTitle("嘉慧光电综合控制平台")
        self.setMinimumSize(1200, 760)
        self.resize(1440, 900)

        icon_path = Path("logo_llgt.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(False)
        self.setCentralWidget(self.tab_widget)

        self.power_meter_window = JW8103A_Control(
            parent=self,
            embedded=True,
            power_bridge=self.power_bridge,
        )
        self.power_meter_window.setWindowFlags(Qt.Widget)

        self.attenuator_window = JW8507MainWindow(
            power_meter_instance=self.power_meter_window,
            parent=self,
        )
        self.attenuator_window.setWindowFlags(Qt.Widget)

        self.tab_widget.addTab(self.attenuator_window, "光衰减器 JW8507")
        self.tab_widget.addTab(self.power_meter_window, "光功率计 JW8103A")

    def closeEvent(self, event):
        self.attenuator_window.shutdown()
        self.power_meter_window.shutdown()
        event.accept()


def main():
    multiprocessing.freeze_support()
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    config = load_app_config()
    power_bridge = PowerMeterBridge.get_instance()
    window = CombinedMainWindow(config=config, power_bridge=power_bridge)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
