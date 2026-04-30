import multiprocessing
import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QTabWidget

from ui.JW8103A_Control import JW8103A_Control
from ui.MainWindow import MainWindow as JW8507MainWindow


class CombinedMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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

        self.attenuator_window = JW8507MainWindow(self)
        self.attenuator_window.setWindowFlags(Qt.Widget)

        self.power_meter_window = JW8103A_Control(self, embedded=True)
        self.power_meter_window.setWindowFlags(Qt.Widget)

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

    window = CombinedMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
