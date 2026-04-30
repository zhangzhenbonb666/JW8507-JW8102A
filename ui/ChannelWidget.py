"""
JW8507 单通道控制界面组件
"""
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QComboBox, QPushButton, QLineEdit, QLCDNumber,
    QFrame, QGroupBox, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QDoubleValidator, QPalette, QColor
from devices.JW8507 import JW8507


class ChannelWidget(QWidget):
    """
    JW8507 单通道控制界面组件
    
    可复制使用，每个实例控制一个通道
    
    :param address: 通道地址 (0x01 - 0x08)
    :param jw8507: JW8507控制类实例
    :param parent: 父窗口
    """
    
    # 日志信号，用于将操作日志发送到主界面
    log_signal = pyqtSignal(str)
    
    def __init__(self, address: int, jw8507: JW8507, refresh_interval: int = 500, parent=None):
        """
        初始化通道控件
        
        :param address: 通道地址
        :param jw8507: JW8507控制类实例
        :param refresh_interval: 刷新间隔（毫秒），默认500ms
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.address = address
        self.jw8507 = jw8507
        self.current_attenuation = 0.0
        self.refresh_interval = refresh_interval
        self._last_refresh_failed = False  # 用于避免频繁输出错误日志
        
        self._init_ui()
        self._connect_signals()
        self._setup_refresh_timer()
        self._load_initial_data()
        
    def _init_ui(self):
        """初始化UI"""
        # 设置固定高度，防止垂直方向缩放
        self.setFixedHeight(62)
        self.setMinimumWidth(720)
        
        # 设置 SizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 主布局 - 水平布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(8)
        
        # 设置整体样式 - 工程软件风格
        self.setStyleSheet("""
            ChannelWidget {
                background-color: #f5f5f5;
                border: 1px solid #c0c0c0;
                border-radius: 2px;
            }
            QLabel {
                color: #333333;
                font-family: "SimHei", "黑体";
                font-size: 14px;
                border: none;
                background: transparent;
            }
            QComboBox {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #a0a0a0;
                border-radius: 2px;
                padding: 4px 8px;
                font-family: "SimHei", "黑体";
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #0078d4;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #666666;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #333333;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
                border: 1px solid #a0a0a0;
                outline: none;
                font-family: "SimHei", "黑体";
                font-size: 14px;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #a0a0a0;
                border-radius: 2px;
                padding: 4px 6px;
                font-family: "SimHei", "黑体";
                font-size: 14px;
            }
            QLineEdit:hover {
                border-color: #0078d4;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #e1e1e1;
                color: #333333;
                border: 1px solid #a0a0a0;
                border-radius: 2px;
                padding: 4px 12px;
                font-family: "SimHei", "黑体";
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
                border-color: #808080;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QPushButton#setWaveBtn {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #005a9e;
            }
            QPushButton#setWaveBtn:hover {
                background-color: #006cc1;
            }
            QPushButton#setWaveBtn:pressed {
                background-color: #005a9e;
            }
            QPushButton#setAttenBtn {
                background-color: #107c10;
                color: #ffffff;
                border: 1px solid #0b5c0b;
            }
            QPushButton#setAttenBtn:hover {
                background-color: #0e6b0e;
            }
            QPushButton#setAttenBtn:pressed {
                background-color: #0b5c0b;
            }
            QPushButton#closeBtn {
                background-color: #d83b01;
                color: #ffffff;
                border: 1px solid #a52c00;
            }
            QPushButton#closeBtn:hover {
                background-color: #c43400;
            }
            QPushButton#closeBtn:pressed {
                background-color: #a52c00;
            }
            QPushButton#resetBtn {
                background-color: #ffb900;
                color: #333333;
                border: 1px solid #cc9400;
            }
            QPushButton#resetBtn:hover {
                background-color: #e6a700;
            }
            QPushButton#resetBtn:pressed {
                background-color: #cc9400;
            }
        """)
        
        # ===== 左侧：通道标识 =====
        self.channel_label = QLabel(f"CH{self.address}")
        self.channel_label.setFixedSize(54, 38)
        self.channel_label.setAlignment(Qt.AlignCenter)
        self.channel_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-family: "SimHei", "黑体";
                font-size: 16px;
                font-weight: bold;
                background-color: #0078d4;
                border: 1px solid #005a9e;
                border-radius: 2px;
            }
        """)
        main_layout.addWidget(self.channel_label)
        
        # ===== 波长选择区域 =====
        wave_label = QLabel("波长:")
        wave_label.setFixedWidth(45)
        main_layout.addWidget(wave_label)
        
        self.wave_combo = QComboBox()
        self.wave_combo.setFixedSize(100, 30)
        for wl in self.jw8507.waveLength_list:
            self.wave_combo.addItem(f"{wl} nm", wl)
        main_layout.addWidget(self.wave_combo)
        
        self.set_wave_btn = QPushButton("设置")
        self.set_wave_btn.setObjectName("setWaveBtn")
        self.set_wave_btn.setFixedSize(56, 30)
        main_layout.addWidget(self.set_wave_btn)
        
        # ===== 分隔线 =====
        self._add_separator(main_layout)
        
        # ===== 衰减值设置区域 =====
        atten_label = QLabel("衰减:")
        atten_label.setFixedWidth(45)
        main_layout.addWidget(atten_label)
        
        self.atten_input = QLineEdit()
        self.atten_input.setPlaceholderText("0.00")
        self.atten_input.setFixedSize(75, 30)
        self.atten_input.setAlignment(Qt.AlignRight)
        # 设置输入验证器，允许0-60的浮点数
        validator = QDoubleValidator(0.0, 60.0, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.atten_input.setValidator(validator)
        main_layout.addWidget(self.atten_input)
        
        atten_unit = QLabel("dB")
        atten_unit.setFixedWidth(28)
        atten_unit.setStyleSheet("color: #333333; font-family: 'SimHei', '黑体'; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(atten_unit)
        
        self.set_atten_btn = QPushButton("设置")
        self.set_atten_btn.setObjectName("setAttenBtn")
        self.set_atten_btn.setFixedSize(56, 30)
        main_layout.addWidget(self.set_atten_btn)
        
        # ===== 分隔线 =====
        self._add_separator(main_layout)
        
        # ===== 控制按钮区域 =====
        self.close_btn = QPushButton("关断")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(56, 30)
        main_layout.addWidget(self.close_btn)
        
        self.reset_btn = QPushButton("重置")
        self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.setFixedSize(56, 30)
        main_layout.addWidget(self.reset_btn)
        
        # ===== 分隔线 =====
        self._add_separator(main_layout)
        
        # ===== 弹性空间 =====
        main_layout.addStretch(1)
        
        # ===== 右侧：LCD显示区域 =====
        lcd_frame = QFrame()
        lcd_frame.setFixedSize(160, 46)
        lcd_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #404040;
                border-radius: 3px;
            }
        """)
        lcd_layout = QHBoxLayout(lcd_frame)
        lcd_layout.setContentsMargins(8, 4, 8, 4)
        lcd_layout.setSpacing(4)
        
        self.lcd_display = QLCDNumber()
        self.lcd_display.setDigitCount(6)
        self.lcd_display.setSegmentStyle(QLCDNumber.Flat)
        self.lcd_display.setFixedSize(108, 34)
        self.lcd_display.display(0.00)
        self.lcd_display.setStyleSheet("""
            QLCDNumber {
                background-color: transparent;
                color: #00ff00;
                border: none;
            }
        """)
        lcd_layout.addWidget(self.lcd_display)
        
        lcd_unit = QLabel("dB")
        lcd_unit.setFixedWidth(28)
        lcd_unit.setAlignment(Qt.AlignCenter)
        lcd_unit.setStyleSheet("""
            QLabel {
                color: #00ff00;
                font-family: "SimHei", "黑体";
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        lcd_layout.addWidget(lcd_unit)
        
        main_layout.addWidget(lcd_frame)
        
    def _add_separator(self, layout):
        """添加垂直分隔线"""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFixedWidth(1)
        separator.setStyleSheet("""
            QFrame {
                background-color: #b0b0b0;
                border: none;
            }
        """)
        layout.addWidget(separator)
        
    def _connect_signals(self):
        """连接信号槽"""
        self.set_wave_btn.clicked.connect(self._on_set_wavelength)
        self.set_atten_btn.clicked.connect(self._on_set_attenuation)
        self.close_btn.clicked.connect(self._on_close_channel)
        self.reset_btn.clicked.connect(self._on_reset_channel)
        self.atten_input.returnPressed.connect(self._on_set_attenuation)
        
    def _setup_refresh_timer(self):
        """设置刷新定时器"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_display)
        # 启动自动刷新，使用配置的刷新间隔
        self.refresh_timer.start(self.refresh_interval)
    
    def _load_initial_data(self):
        """
        加载通道初始数据
        
        在通道创建时读取一次实时数据，设置初始值
        """
        try:
            success, info = self.jw8507.read_RT_info(self.address)
            if success:
                # 设置衰减值
                self.current_attenuation = info.get("衰减值", 0.0)
                self.lcd_display.display(f"{self.current_attenuation:.2f}")
                
                # 设置波长下拉框
                wavelength = info.get("波长信息", None)
                if wavelength is not None:
                    # 在下拉框中查找对应的波长并选中
                    for i in range(self.wave_combo.count()):
                        if self.wave_combo.itemData(i) == wavelength:
                            self.wave_combo.setCurrentIndex(i)
                            break
                
                self._emit_log(f"通道 {self.address} 初始化: 波长={wavelength}nm, 衰减={self.current_attenuation:.2f}dB")
        except Exception as e:
            self._emit_log(f"通道 {self.address} 读取初始数据失败: {e}")
        
    def start_auto_refresh(self, interval_ms: int = 500):
        """
        启动自动刷新
        
        :param interval_ms: 刷新间隔（毫秒）
        """
        self.refresh_timer.start(interval_ms)
        
    def stop_auto_refresh(self):
        """停止自动刷新"""
        self.refresh_timer.stop()
        
    def refresh_display(self):
        """
        刷新LCD显示
        
        从设备读取实际的衰减值和波长信息，更新UI显示
        这样无论是本地设置还是远程控制，都能正确反映设备实际状态
        """
        try:
            success, info = self.jw8507.read_RT_info(self.address)
            if success:
                # 更新衰减值显示
                self.current_attenuation = info.get("衰减值", 0.0)
                self.lcd_display.display(f"{self.current_attenuation:.2f}")
                
                # 更新波长下拉框（仅当波长发生变化时）
                wavelength = info.get("波长信息", None)
                if wavelength is not None:
                    current_wavelength = self.wave_combo.currentData()
                    if current_wavelength != wavelength:
                        # 在下拉框中查找对应的波长并选中
                        for i in range(self.wave_combo.count()):
                            if self.wave_combo.itemData(i) == wavelength:
                                self.wave_combo.setCurrentIndex(i)
                                break
        except Exception as e:
            # 避免频繁输出错误日志，只在第一次失败时输出
            if not hasattr(self, '_last_refresh_failed') or not self._last_refresh_failed:
                self._emit_log(f"刷新通道 {self.address} 失败: {e}")
                self._last_refresh_failed = True
        else:
            self._last_refresh_failed = False
            
    def _on_set_wavelength(self):
        """设置波长"""
        wavelength = self.wave_combo.currentData()
        try:
            success = self.jw8507.set_waveLength(self.address, wavelength)
            if success:
                self._emit_log(f"通道 {self.address} 波长设置成功: {wavelength} nm")
            else:
                self._emit_log(f"通道 {self.address} 波长设置失败")
        except Exception as e:
            self._emit_log(f"设置波长异常: {e}")
            
    def _on_set_attenuation(self):
        """设置衰减值"""
        text = self.atten_input.text().strip()
        if not text:
            return
            
        try:
            attenuation = float(text)
            
            # 检查衰减值范围 0-60 dB
            if attenuation < 0 or attenuation > 60:
                QMessageBox.warning(
                    self, 
                    "范围错误", 
                    f"衰减值超出范围！\n\n有效范围: 0 ~ 60 dB\n当前输入: {attenuation} dB",
                    QMessageBox.Ok
                )
                self.atten_input.selectAll()
                self.atten_input.setFocus()
                return
            
            success = self.jw8507.set_attenuation(self.address, attenuation)
            if success:
                self._emit_log(f"通道 {self.address} 衰减设置成功: {attenuation} dB")
                # 不再立即更新LCD显示，而是让定时器自动刷新实际值
                # 这样可以确保显示的是设备实际的衰减值
            else:
                self._emit_log(f"通道 {self.address} 衰减设置失败")
        except ValueError:
            self._emit_log("请输入有效的衰减值")
        except Exception as e:
            self._emit_log(f"设置衰减异常: {e}")
            
    def _on_close_channel(self):
        """关断通道"""
        try:
            success = self.jw8507.set_CloseReset(self.address, "Close")
            if success:
                self._emit_log(f"通道 {self.address} 已关断")
                # LCD颜色会在下次刷新时根据实际读取的值自动更新
                # 关断后衰减值通常为最大值（60dB或更大）
            else:
                self._emit_log(f"通道 {self.address} 关断失败")
        except Exception as e:
            self._emit_log(f"关断通道异常: {e}")
            
    def _on_reset_channel(self):
        """重置通道"""
        try:
            success = self.jw8507.set_CloseReset(self.address, "Reset")
            if success:
                self.lcd_display.setStyleSheet("""
                    QLCDNumber {
                        background-color: transparent;
                        color: #00ff00;
                        border: none;
                    }
                """)
                self._emit_log(f"通道 {self.address} 已重置")
                # 不再立即更新显示值，让定时器自动刷新实际值
            else:
                self._emit_log(f"通道 {self.address} 重置失败")
        except Exception as e:
            self._emit_log(f"重置通道异常: {e}")
            
    def _emit_log(self, message: str):
        """
        发送日志信号
        
        :param message: 日志消息
        """
        self.log_signal.emit(message)
    
    def get_current_attenuation(self) -> float:
        """获取当前衰减值"""
        return self.current_attenuation
    
    def set_channel_name(self, name: str):
        """
        设置通道显示名称
        
        :param name: 自定义名称
        """
        self.channel_label.setText(name)


# ===== 测试代码 =====
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QScrollArea
    from PyQt5 import QtCore
    import serial

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("JW8507 通道控制")
    window.setStyleSheet("""
        QMainWindow {
            background-color: #e0e0e0;
        }
    """)
    window.setMinimumSize(720, 300)
    window.resize(750, 380)
    
    # 滚动区域
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet("""
        QScrollArea {
            background-color: #e0e0e0;
            border: none;
        }
    """)
    window.setCentralWidget(scroll)
    
    # 中央部件
    central = QWidget()
    central.setStyleSheet("background-color: #e0e0e0;")
    scroll.setWidget(central)
    
    layout = QVBoxLayout(central)
    layout.setSpacing(6)
    layout.setContentsMargins(10, 10, 10, 10)
    
    # 创建串口（测试时可能连接失败，仅用于演示）
    try:
        ser = serial.Serial("COM8", 115200, timeout=0.1)
        jw8507 = JW8507(ser)
        jw8507.connect()
    except:
        # 如果无法连接，创建一个模拟对象用于UI测试
        class MockSerial:
            is_open = True
            def open(self): pass
            def close(self): pass
            def write(self, data): pass
            def read(self, length): return b'\x00' * length
        
        ser = MockSerial()
        jw8507 = JW8507(ser)
    
    # 添加多个通道控件
    for i in range(1, 9):
        channel_widget = ChannelWidget(address=i, jw8507=jw8507)
        layout.addWidget(channel_widget)
    
    layout.addStretch()
    
    window.show()
    sys.exit(app.exec_())

