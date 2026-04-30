"""
JW8507 程控衰减器控制主界面
"""
import socket
import sys
import json
from datetime import datetime
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QPushButton, QScrollArea, QFrame,
    QGroupBox, QTextEdit, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5 import QtCore
import pandas as pd
from devices.JW8507 import JW8507
from network.TCPServer import TCPServer
from ui.ChannelWidget import ChannelWidget
from utils.config import load_app_config, save_app_config
from utils.logger import setup_file_logger

def read_version() -> str:
    """读取版本信息"""
    try:
        df = pd.read_csv("更新内容.csv", encoding="utf-8", header=None)
        return df.iloc[-1, 0]
    except Exception as e:
        return "未知"

class MainWindow(QMainWindow):
    """JW8507 程控衰减器控制主界面"""
    
    # 定义信号用于处理TCP远程连接请求（在主线程中执行）
    tcp_connect_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.version = read_version()
        self.ser = None
        self.jw8507 = None
        self.channel_widgets = []
        self.config = self._load_config()
        self.sidebar_expanded = True  # 侧边栏展开状态
        self.sidebar_width = 280  # 侧边栏宽度
        self.connected = False
        # 初始化文件日志记录器
        self.file_logger = setup_file_logger(
            name="JW8507",
            backup_count=int(self.config.get("log_retention_days", 30)),
        )
        
        # 用于TCP远程调用的结果存储
        self._tcp_result_container = None
        self._tcp_result_event = None
        
        self._init_ui()
        self._connect_signals()
        self._refresh_ports()

        self.port_combo.setCurrentText(self.config["serial_port"])
        
        # 启动TCP服务器（在所有UI初始化完成后）
        self.tcp_server = TCPServer(
            addr=self.config["server_address"] if self.config["server_address"] else socket.gethostbyname(socket.gethostname()),
            port=self.config["server_port"],
            func=self._handle_tcp_request,
        )
        self.tcp_server.start()

    def _handle_tcp_request(self, request: str) -> str:
        """处理TCP请求（在TCP服务器线程中调用）"""
        try:
            cmd = json.loads(request)
        except (json.JSONDecodeError, ValueError) as e:
            return [False, "", "Invalid JSON command"]

        # 对于需要GUI操作的命令，使用线程安全的方式调用
        opcode = cmd.get("opcode", "")
        
        # 这些命令不需要GUI操作，可以直接在当前线程执行
        if opcode == "check":
            return self._check()
        elif opcode in ["SetWavelength", "SetAttenuation", "SetCloseReset", "AdjustAttenuation"]:
            # 这些命令只操作串口，不涉及GUI，可以直接调用
            if opcode == "SetWavelength":
                return self._set_wavelength(cmd["parameter"]["CH"], cmd["parameter"]["Wavelength"])
            elif opcode == "SetAttenuation":
                return self._set_attenuation(cmd["parameter"]["CH"], cmd["parameter"]["Attenuation"])
            elif opcode == "SetCloseReset":
                return self._set_close_reset(cmd["parameter"]["CH"], cmd["parameter"]["Set"])
            elif opcode == "AdjustAttenuation":
                return self._adjust_attenuation(cmd["parameter"]["CH"], cmd["parameter"]["Delta"])
        elif opcode == "ConnectDevice":
            # 连接设备需要在主线程中执行（会创建GUI组件）
            # 使用信号-槽机制和事件来实现线程间同步
            import threading
            
            # 创建结果容器和同步事件
            self._tcp_result_container = {"result": None}
            self._tcp_result_event = threading.Event()
            
            # 发射信号，让主线程处理连接
            self.tcp_connect_signal.emit()
            
            # 等待主线程执行完成（最多等待10秒）
            if self._tcp_result_event.wait(timeout=10.0):
                result = self._tcp_result_container["result"]
                # 清理
                self._tcp_result_container = None
                self._tcp_result_event = None
                return result
            else:
                # 清理
                self._tcp_result_container = None
                self._tcp_result_event = None
                return [False, "", "Command execution timeout"]
        
        return [False, "", "Unknown command"]

    def _connect_device(self) -> tuple[bool, str, str]:
        """连接设备（用于TCP远程调用的旧接口，保持兼容）"""
        return self._connect(message=False)
    
    def _connect_device_for_tcp(self) -> tuple[bool, str, str]:
        """连接设备（专门用于TCP远程调用，在主线程中执行）"""
        if self.connected:
            return [True, "", "Device already connected"]
        return self._connect(message=False)
    
    def _handle_tcp_connect_in_main_thread(self):
        """在主线程中处理TCP远程连接请求"""
        try:
            # 执行连接操作
            result = self._connect_device_for_tcp()
            
            # 将结果存储到容器中
            if self._tcp_result_container is not None:
                self._tcp_result_container["result"] = result
            
            # 设置事件，通知TCP线程完成
            if self._tcp_result_event is not None:
                self._tcp_result_event.set()
                
        except Exception as e:
            # 发生异常时也要通知TCP线程
            if self._tcp_result_container is not None:
                self._tcp_result_container["result"] = [False, "", f"Command execution error: {e}"]
            if self._tcp_result_event is not None:
                self._tcp_result_event.set()
    
    def _check(self) -> tuple[bool, str, str]:
        """检查设备"""
        return [True, self.version, ""]
    
    def _set_wavelength(self, CH:int, wavelength:int) -> tuple[bool, str, str]:
        """设置波长"""
        if CH < 1 or CH > self.config["channel_count"]:
            return [False, "", "Out of range"]
        if wavelength not in self.jw8507.waveLength_list:
            return [False, "", "Wavelength not in list"]
        if self.jw8507.set_waveLength(CH, wavelength):
            return [True, "", "Wavelength set successfully"]
        else:
            return [False, "", "Wavelength set failed"]

    def _set_attenuation(self, CH:int, attenuation:float) -> tuple[bool, str, str]:
        """设置衰减"""
        if CH < 1 or CH > self.config["channel_count"]:
            return [False, "", "Out of range"]
        if attenuation < 0 or attenuation > 60:
            return [False, "", "Out of range"]
        if self.jw8507.set_attenuation(CH, attenuation):
            return [True, "", "Attenuation set successfully"]
        else:
            return [False, "", "Attenuation set failed"]

    def _set_close_reset(self, CH:int, ctrl:str) -> tuple[bool, str, str]:
        """设置关断/清零"""
        if CH < 1 or CH > self.config["channel_count"]:
            return [False, "", "Out of range"]
        if ctrl not in ["Close", "Reset"]:
            return [False, "", "Invalid control instruction"]
        if self.jw8507.set_CloseReset(CH, ctrl):
            return [True, "", "Close/Reset set successfully"]
        else:
            return [False, "", "Close/Reset set failed"]

    def _adjust_attenuation(self, CH:int, delta:float) -> tuple[bool, str, str]:
        """调整衰减"""
        if CH < 1 or CH > self.config["channel_count"]:
            return [False, "", "Out of range"]
        result, info = self.jw8507.read_RT_info(CH)
        if not result:
            return [False, "", "Read attenuation failed"]
        now_attenuation = info.get("衰减值", 0.0)
        new_attenuation = now_attenuation + delta
        if new_attenuation < 0 or new_attenuation > 60:
            return [False, "", "Out of range"]
        if self.jw8507.set_attenuation(CH, new_attenuation):
            return [True, "", f"Attenuation adjusted to {new_attenuation:.2f}dB successfully"]
        else:
            return [False, "", f"Attenuation adjustment to {new_attenuation:.2f}dB failed"]

    def _load_config(self) -> dict:
        """加载配置文件"""
        return load_app_config()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"JW8507 程控衰减器控制 - {self.version}")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)
        
        # 主窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QWidget {
                font-family: "Microsoft YaHei", "微软雅黑", "SimHei";
            }
        """)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局 - 水平分割
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ===== 左侧面板容器（包含切换按钮和侧边栏）=====
        left_container = QWidget()
        left_container.setStyleSheet("background: transparent;")
        left_container_layout = QHBoxLayout(left_container)
        left_container_layout.setContentsMargins(0, 0, 0, 0)
        left_container_layout.setSpacing(0)
        
        # 侧边栏内容
        self.left_panel = self._create_left_panel()
        left_container_layout.addWidget(self.left_panel)
        
        # 切换按钮
        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setFixedSize(20, 60)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #666666;
                border: none;
                border-radius: 0 4px 4px 0;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
                color: #333333;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        left_container_layout.addWidget(self.toggle_btn, 0, Qt.AlignVCenter)
        
        main_layout.addWidget(left_container)
        
        # ===== 右侧面板（通道显示区）=====
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 1)  # 右侧占据剩余空间
        
    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        panel.setFixedWidth(self.sidebar_width)
        panel.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # ===== 串口设置组 =====
        serial_group = QGroupBox("串口设置")
        serial_group.setStyleSheet("""
            QGroupBox {
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        serial_layout = QVBoxLayout(serial_group)
        serial_layout.setSpacing(8)
        
        # 串口选择
        port_layout = QHBoxLayout()
        port_label = QLabel("串口:")
        port_label.setFixedWidth(50)
        port_label.setStyleSheet("color: #333333; font-size: 13px; border: none;")
        self.port_combo = QComboBox()
        self.port_combo.setStyleSheet(self._get_combo_style())
        self.port_combo.setMinimumHeight(30)
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_combo, 1)
        serial_layout.addLayout(port_layout)
        
        # 波特率选择
        baud_layout = QHBoxLayout()
        baud_label = QLabel("波特率:")
        baud_label.setFixedWidth(50)
        baud_label.setStyleSheet("color: #333333; font-size: 13px; border: none;")
        self.baud_combo = QComboBox()
        self.baud_combo.setStyleSheet(self._get_combo_style())
        self.baud_combo.setMinimumHeight(30)
        bauds = ["9600", "19200", "38400", "57600", "115200", "230400"]
        self.baud_combo.addItems(bauds)
        self.baud_combo.setCurrentText(str(self.config.get("default_baudrate", 115200)))
        baud_layout.addWidget(baud_label)
        baud_layout.addWidget(self.baud_combo, 1)
        serial_layout.addLayout(baud_layout)
        
        # 刷新和连接按钮
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet(self._get_button_style("#4a9eff", "#3d8ae6"))
        self.refresh_btn.setMinimumHeight(34)
        btn_layout.addWidget(self.refresh_btn)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setStyleSheet(self._get_button_style("#28a745", "#218838"))
        self.connect_btn.setMinimumHeight(34)
        btn_layout.addWidget(self.connect_btn)
        serial_layout.addLayout(btn_layout)
        
        layout.addWidget(serial_group)
        
        # ===== 设备信息组 =====
        info_group = QGroupBox("设备信息")
        info_group.setStyleSheet("""
            QGroupBox {
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)
        
        # 读取版本按钮
        self.read_version_btn = QPushButton("读取版本信息")
        self.read_version_btn.setStyleSheet(self._get_button_style("#17a2b8", "#138496"))
        self.read_version_btn.setMinimumHeight(36)
        self.read_version_btn.setEnabled(False)
        info_layout.addWidget(self.read_version_btn)
        
        # 读取波长按钮
        self.read_wavelength_btn = QPushButton("读取波长信息")
        self.read_wavelength_btn.setStyleSheet(self._get_button_style("#6f42c1", "#5e35b1"))
        self.read_wavelength_btn.setMinimumHeight(36)
        self.read_wavelength_btn.setEnabled(False)
        info_layout.addWidget(self.read_wavelength_btn)
        
        layout.addWidget(info_group)
        
        # ===== 信息显示区 =====
        log_group = QGroupBox("日志输出")
        log_group.setStyleSheet("""
            QGroupBox {
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                font-family: "Microsoft YaHei", "微软雅黑", "Consolas";
                font-size: 13px;
                padding: 6px;
            }
        """)
        self.log_text.setMinimumHeight(150)
        self.max_log_lines = 50  # 限制日志最大行数
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # 弹性空间
        layout.addStretch()
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧通道显示面板"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("通道控制")
        title_label.setStyleSheet("""
            QLabel {
                color: #333333;
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """)
        layout.addWidget(title_label)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background-color: #f0f0f0;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background-color: #c0c0c0;
                border-radius: 4px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)
        
        # 滚动区域内的容器
        self.channel_container = QWidget()
        self.channel_container.setStyleSheet("background-color: #f5f5f5;")
        self.channel_container.setMinimumWidth(740)  # 确保水平方向可以完整显示通道控件
        self.channel_layout = QVBoxLayout(self.channel_container)
        self.channel_layout.setContentsMargins(8, 8, 8, 8)
        self.channel_layout.setSpacing(6)
        self.channel_layout.addStretch()
        
        self.scroll_area.setWidget(self.channel_container)
        layout.addWidget(self.scroll_area)
        
        # 提示标签（连接前显示）
        self.hint_label = QLabel("请先连接串口以显示通道控制")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 14px;
                border: none;
            }
        """)
        self.channel_layout.insertWidget(0, self.hint_label)
        
        return panel
    
    def _get_combo_style(self) -> str:
        """获取下拉框样式"""
        return """
            QComboBox {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #0078d4;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #666666;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #333333;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
                border: 1px solid #e0e0e0;
                outline: none;
            }
        """
    
    def _get_button_style(self, bg_color: str, hover_color: str) -> str:
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #e0e0e0;
                color: #999999;
            }}
        """
    
    def _connect_signals(self):
        """连接信号槽"""
        self.refresh_btn.clicked.connect(self._refresh_ports)
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.read_version_btn.clicked.connect(self._read_version)
        self.read_wavelength_btn.clicked.connect(self._read_wavelength)
        # 连接TCP远程连接信号（用于在主线程中执行GUI操作）
        self.tcp_connect_signal.connect(self._handle_tcp_connect_in_main_thread)
    
    def _toggle_sidebar(self):
        """切换侧边栏展开/收起状态"""
        self.sidebar_expanded = not self.sidebar_expanded
        
        # 创建动画
        self.animation = QPropertyAnimation(self.left_panel, b"maximumWidth")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        if self.sidebar_expanded:
            # 展开
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.sidebar_width)
            self.toggle_btn.setText("◀")
            self.left_panel.show()
        else:
            # 收起
            self.animation.setStartValue(self.sidebar_width)
            self.animation.setEndValue(0)
            self.toggle_btn.setText("▶")
            self.animation.finished.connect(lambda: self.left_panel.hide() if not self.sidebar_expanded else None)
        
        self.animation.start()
    
    def _refresh_ports(self):
        """刷新串口列表"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device, port.device)
        
        if self.port_combo.count() == 0:
            self.port_combo.addItem("无串口", "")
            self._log("未检测到可用串口")
        else:
            self._log(f"检测到 {self.port_combo.count()} 个串口")
    
    def _toggle_connection(self):
        """切换连接状态"""
        if self.connected:
            self._disconnect()
        else:
            self._connect()
    
    def _connect(self, message:bool=True):
        """连接串口"""
        port = self.port_combo.currentData()
        if not port:
            if message:
                QMessageBox.warning(self, "警告", "请选择有效的串口")
            else:
                self._log("请选择有效的串口")
            return [False, "", "Port not selected"]
        
        try:
            baudrate = int(self.baud_combo.currentText())
            timeout = self.config.get("serial_timeout", 0.1)
            
            self.ser = serial.Serial(port, baudrate, timeout=timeout, write_timeout=timeout)
            self.jw8507 = JW8507(self.ser)
            self.jw8507.connect()
            
            self._log(f"已连接到 {port}，波特率: {baudrate}")
            
            # 连接后首先尝试读取版本号验证设备
            self._log("正在验证设备...")
            try:
                success, data = self.jw8507.read_version()
                if not success:
                    # 读取失败，可能是错误的串口
                    self._log("设备验证失败：未收到有效响应")
                    self._force_disconnect()
                    if message:
                        QMessageBox.warning(self, "设备验证失败", 
                            "未能读取到设备版本信息，请确认：\n"
                            "1. 是否选择了正确的串口\n"
                            "2. 波特率设置是否正确\n"
                            "3. 设备是否已正确连接")
                    else:
                        self._log("设备验证失败：未收到有效响应")
                    return [False, "", "Device verification failed: no valid response"]
                else:
                    self._log("设备验证成功")
                    self._log("=== 版本信息 ===")
                    for key, value in data.items():
                        self._log(f"  {key}: {value}")
            except serial.SerialTimeoutException as e:
                # 写超时或读超时
                self._log(f"设备验证超时: {e}")
                self._force_disconnect()
                if message:
                    QMessageBox.warning(self, "连接超时", 
                        "串口通信超时，请确认：\n"
                        "1. 是否选择了正确的串口\n"
                        "2. 波特率设置是否正确\n"
                        "3. 设备是否已正确连接")
                else:
                    self._log("串口通信超时")
                return [False, "", "Device verification timeout"]
            except Exception as e:
                # 其他异常
                self._log(f"设备验证异常: {e}")
                self._force_disconnect()
                if message:
                    QMessageBox.warning(self, "连接错误", 
                        f"设备验证时发生错误：{e}\n\n请确认串口和设备设置是否正确")
                else:
                    self._log(f"设备验证异常: {e}")
                return [False, "", f"Device verification exception: {e}"]
            
            # 更新UI状态
            self.connect_btn.setText("断开")
            self.connect_btn.setStyleSheet(self._get_button_style("#dc3545", "#c82333"))
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.read_version_btn.setEnabled(True)
            self.read_wavelength_btn.setEnabled(True)

            # 读取波长信息
            QTimer.singleShot(100, self._read_wavelength)
            
            # 添加通道界面
            self._add_channel_widgets()
            
        except serial.SerialException as e:
            if message:
                QMessageBox.critical(self, "连接失败", f"无法连接到串口: {e}")
            else:
                self._log(f"连接失败: {e}")
            return [False, "", f"Connection failed: {e}"]

        self.connected = True
        self.config["serial_port"] = port
        return [True, "", "Connection successful"]
    
    def _disconnect(self):
        """断开连接"""
        self.connected = False
        if self.jw8507:
            self.jw8507.default_display()
            self.jw8507.disconnect()
        
        if self.ser:
            self.ser.close()
            self.ser = None
        
        self.jw8507 = None
        
        # 移除通道界面
        self._remove_channel_widgets()
        
        # 更新UI状态
        self.connect_btn.setText("连接")
        self.connect_btn.setStyleSheet(self._get_button_style("#28a745", "#218838"))
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.read_version_btn.setEnabled(False)
        self.read_wavelength_btn.setEnabled(False)
        
        self._log("已断开连接")
    
    def _force_disconnect(self):
        """强制断开连接（不与设备通信，用于连接验证失败时）"""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        
        self.jw8507 = None
        
        # 更新UI状态
        self.connect_btn.setText("连接")
        self.connect_btn.setStyleSheet(self._get_button_style("#28a745", "#218838"))
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.read_version_btn.setEnabled(False)
        self.read_wavelength_btn.setEnabled(False)
    
    def _add_channel_widgets(self):
        """添加通道控件"""
        # 隐藏提示
        self.hint_label.hide()
        
        # 获取配置的通道数量和刷新间隔
        channel_count = self.config.get("channel_count", 8)
        refresh_interval = self.config.get("refresh_interval_ms", 500)
        
        # 添加通道控件
        for i in range(1, channel_count + 1):
            channel_widget = ChannelWidget(address=i, jw8507=self.jw8507, refresh_interval=refresh_interval)
            # 连接通道日志信号到主界面日志
            channel_widget.log_signal.connect(self._log)
            self.channel_widgets.append(channel_widget)
            # 在 stretch 之前插入
            self.channel_layout.insertWidget(self.channel_layout.count() - 1, channel_widget)
        
        self._log(f"已添加 {channel_count} 个通道控制界面（刷新间隔: {refresh_interval}ms）")
    
    def _remove_channel_widgets(self):
        """移除所有通道控件"""
        for widget in self.channel_widgets:
            widget.stop_auto_refresh()
            widget.setParent(None)
            widget.deleteLater()
        
        self.channel_widgets.clear()
        
        # 显示提示
        self.hint_label.show()
    
    def _auto_read_info(self):
        """自动读取设备信息（连接后自动触发）"""
        self._read_version()
        QTimer.singleShot(200, self._read_wavelength)
    
    def _read_version(self):
        """读取版本信息"""
        if not self.jw8507:
            return
        
        try:
            success, data = self.jw8507.read_version()
            if success:
                self._log("=== 版本信息 ===")
                for key, value in data.items():
                    self._log(f"  {key}: {value}")
            else:
                self._log("读取版本信息失败")
        except Exception as e:
            self._log(f"读取版本信息异常: {e}")
    
    def _read_wavelength(self):
        """读取波长信息"""
        if not self.jw8507:
            return
        
        try:
            success, data = self.jw8507.read_waveLength_info()
            if success:
                self._log("=== 波长信息 ===")
                wavelengths = data.get("波长列表", [])
                self._log(f"  支持波长: {wavelengths}")
                
                # 更新JW8507的波长列表
                if wavelengths:
                    self.jw8507.waveLength_list = wavelengths
                    # 更新通道界面的波长下拉框
                    for channel_widget in self.channel_widgets:
                        channel_widget.wave_combo.clear()
                        for wavelength in wavelengths:
                            channel_widget.wave_combo.addItem(f"{wavelength} nm", wavelength)
                    self._log(f"  已更新波长列表")
            else:
                self._log("读取波长信息失败")
        except Exception as e:
            self._log(f"读取波长信息异常: {e}")
    
    def _log(self, message: str):
        """输出日志"""
        # 获取当前时间戳
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 输出到UI
        self.log_text.append(formatted_message)
        
        # 写入文件日志
        self.file_logger.info(message)
        
        # 限制日志行数
        text = self.log_text.toPlainText()
        lines = text.split('\n')
        if len(lines) > self.max_log_lines:
            # 保留最新的日志
            self.log_text.setPlainText('\n'.join(lines[-self.max_log_lines:]))
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def shutdown(self):
        """关闭串口、TCP服务并保存配置。"""
        if self.ser and self.ser.is_open:
            self._disconnect()
        if getattr(self, "tcp_server", None) is not None:
            self.tcp_server.close_tcp_server()
            self.tcp_server.wait(2000)
        save_app_config(self.config)

    def closeEvent(self, event):
        """关闭窗口事件"""
        self.shutdown()
        event.accept()


def main():
    """主函数"""
    # 启用高DPI缩放
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

