"""
JW8507 单通道控制界面组件。
"""
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QLCDNumber,
    QFrame,
    QGroupBox,
    QSizePolicy,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
)

from ui.通道公式线程 import AttFormulaThread
from devices.JW8507 import JW8507


class AlarmMessageBox(QMessageBox):
    """报警解除前不允许用户手动关闭的提示框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close = False

    def allow_close(self):
        self._allow_close = True

    def prevent_close(self):
        self._allow_close = False

    def closeEvent(self, event):
        if self._allow_close:
            super().closeEvent(event)
        else:
            event.ignore()

    def reject(self):
        if self._allow_close:
            super().reject()


class ChannelWidget(QWidget):
    """JW8507 单通道控制界面组件。"""

    log_signal = pyqtSignal(str)
    alarm_signal = pyqtSignal(int, str)
    config_changed = pyqtSignal(int, str, object)

    def __init__(
        self,
        address: int,
        jw8507: JW8507,
        refresh_interval: int = 500,
        power_bridge=None,
        power_meter_channel=None,
        initial_mode: str = "output",
        target: float = -25.0,
        min_att: float = 0.0,
        formula_interval_ms: int = 1000,
        parent=None,
    ):
        super().__init__(parent)
        self.address = address
        self.jw8507 = jw8507
        self.refresh_interval = refresh_interval
        self.power_bridge = power_bridge
        self.power_meter_channel = power_meter_channel
        self.formula_interval_ms = formula_interval_ms

        self.mode = initial_mode if initial_mode in ("output", "input") else "output"
        self.target = float(target)
        self.min_att = max(0.0, float(min_att))
        self.current_attenuation = 0.0
        self.latest_opm = 0.0
        self.latest_input_power = 0.0
        self.formula_thread = None
        self.alarm_active = False
        self._alarm_dialog = None
        self._last_refresh_failed = False
        self._wavelength_missing_logged = False

        self._init_ui()
        self._connect_signals()
        self._apply_mode_to_ui()
        self._setup_refresh_timer()
        self._load_initial_data()

    def _init_ui(self):
        self.setMinimumWidth(760)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(self._style_sheet())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        main_layout.addWidget(self._create_header())
        main_layout.addWidget(self._create_mode_selector())
        self.output_group = self._create_formula_panel("output")
        self.input_group = self._create_formula_panel("input")
        main_layout.addWidget(self.output_group)
        main_layout.addWidget(self.input_group)
        main_layout.addWidget(self._create_common_controls())

    def _create_header(self):
        header = QFrame()
        header.setObjectName("channelHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)

        self.channel_label = QLabel(f"CH{self.address}")
        self.channel_label.setObjectName("channelTitle")
        layout.addWidget(self.channel_label)
        layout.addStretch()

        self.header_status_label = QLabel("● 正常")
        self.header_status_label.setObjectName("statusOk")
        layout.addWidget(self.header_status_label)
        return header

    def _create_mode_selector(self):
        group = QGroupBox("通道模式")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(12, 8, 12, 8)

        self.output_radio = QRadioButton("输出通道")
        self.input_radio = QRadioButton("输入通道")
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.addButton(self.output_radio)
        self.mode_button_group.addButton(self.input_radio)
        layout.addWidget(self.output_radio)
        layout.addWidget(self.input_radio)
        layout.addStretch()
        return group

    def _create_formula_panel(self, mode):
        title = "输出模式参数" if mode == "output" else "输入模式参数"
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        target_edit, target_btn = self._create_value_editor(self.target, -200.0, 100.0)
        min_edit, min_btn = self._create_value_editor(self.min_att, 0.0, 60.0)
        target_btn.setObjectName("primaryBtn")
        min_btn.setObjectName("primaryBtn")

        parameter_row = 0
        if mode == "input":
            parameter_row = 1
            self.pm_channel_combo = QComboBox()
            self.pm_channel_combo.setFixedWidth(140)
            self._populate_pm_channel_combo()
            self._sync_pm_channel_combo()
            grid.addWidget(QLabel("功率计通道:"), 0, 0)
            grid.addWidget(self.pm_channel_combo, 0, 1)

        grid.addWidget(QLabel("目标值(dBm):"), parameter_row, 0)
        grid.addWidget(target_edit, parameter_row, 1)
        grid.addWidget(target_btn, parameter_row, 2)
        grid.addWidget(QLabel("ATT 最小值:"), parameter_row + 1, 0)
        grid.addWidget(min_edit, parameter_row + 1, 1)
        grid.addWidget(min_btn, parameter_row + 1, 2)

        value_title = "当前 OPM:" if mode == "output" else "功率计读数(x):"
        value_label = QLabel("0.00 dBm")
        value_label.setObjectName("metricLabel")
        att_label = QLabel("0.00 dB")
        att_label.setObjectName("metricLabel")
        status_label = QLabel("○ 已停止")
        status_label.setObjectName("formulaStopped")

        grid.addWidget(QLabel(value_title), 0, 3)
        grid.addWidget(value_label, 0, 4)
        grid.addWidget(QLabel("当前 ATT:"), 1, 3)
        grid.addWidget(att_label, 1, 4)
        grid.addWidget(QLabel("公式状态:"), 2, 3)
        grid.addWidget(status_label, 2, 4)

        start_btn = QPushButton("启动公式")
        start_btn.setObjectName("startFormulaBtn")
        stop_btn = QPushButton("停止公式")
        stop_btn.setObjectName("stopFormulaBtn")
        alarm_label = QLabel("● 正常")
        alarm_label.setObjectName("alarmOk")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(alarm_label)
        btn_layout.addStretch()
        grid.addLayout(btn_layout, parameter_row + 2, 0, 1, 3)

        if mode == "output":
            self.output_target_input = target_edit
            self.output_min_att_input = min_edit
            self.output_target_btn = target_btn
            self.output_min_att_btn = min_btn
            self.output_opm_label = value_label
            self.output_att_label = att_label
            self.output_formula_status = status_label
            self.output_start_btn = start_btn
            self.output_stop_btn = stop_btn
            self.output_alarm_label = alarm_label
        else:
            self.input_target_input = target_edit
            self.input_min_att_input = min_edit
            self.input_target_btn = target_btn
            self.input_min_att_btn = min_btn
            self.input_power_label = value_label
            self.input_att_label = att_label
            self.input_formula_status = status_label
            self.input_start_btn = start_btn
            self.input_stop_btn = stop_btn
            self.input_alarm_label = alarm_label
            self.pm_channel_combo.currentIndexChanged.connect(self._on_pm_channel_changed)

        return group

    def _populate_pm_channel_combo(self):
        self.pm_channel_combo.blockSignals(True)
        self.pm_channel_combo.clear()
        self.pm_channel_combo.addItem("请选择通道", None)

        count = 4
        if self.power_bridge is not None and hasattr(self.power_bridge, "get_channel_count"):
            count = self.power_bridge.get_channel_count()

        for index in range(count):
            self.pm_channel_combo.addItem(f"功率计 CH{index + 1}", index)
        self.pm_channel_combo.blockSignals(False)

    def _sync_pm_channel_combo(self):
        if not hasattr(self, "pm_channel_combo"):
            return
        self.pm_channel_combo.blockSignals(True)
        target_index = 0
        for index in range(self.pm_channel_combo.count()):
            if self.pm_channel_combo.itemData(index) == self.power_meter_channel:
                target_index = index
                break
        self.pm_channel_combo.setCurrentIndex(target_index)
        self.pm_channel_combo.blockSignals(False)

    def _create_common_controls(self):
        group = QGroupBox("通用控制")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        layout.addWidget(QLabel("波长:"))
        self.wave_combo = QComboBox()
        self.wave_combo.setFixedWidth(110)
        for wavelength in self.jw8507.waveLength_list:
            self.wave_combo.addItem(f"{wavelength} nm", wavelength)
        layout.addWidget(self.wave_combo)

        self.set_wave_btn = QPushButton("设置")
        self.set_wave_btn.setObjectName("primaryBtn")
        layout.addWidget(self.set_wave_btn)

        self._add_separator(layout)

        layout.addWidget(QLabel("手动衰减:"))
        self.atten_input = QLineEdit()
        self.atten_input.setPlaceholderText("0.00")
        self.atten_input.setAlignment(Qt.AlignRight)
        self.atten_input.setFixedWidth(80)
        atten_validator = QDoubleValidator(0.0, 60.0, 2)
        atten_validator.setNotation(QDoubleValidator.StandardNotation)
        self.atten_input.setValidator(atten_validator)
        layout.addWidget(self.atten_input)
        layout.addWidget(QLabel("dB"))

        self.set_atten_btn = QPushButton("设置")
        self.set_atten_btn.setObjectName("setAttenBtn")
        layout.addWidget(self.set_atten_btn)

        self.close_btn = QPushButton("关断")
        self.close_btn.setObjectName("closeBtn")
        layout.addWidget(self.close_btn)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.setObjectName("resetBtn")
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        lcd_frame = QFrame()
        lcd_frame.setObjectName("lcdFrame")
        lcd_layout = QHBoxLayout(lcd_frame)
        lcd_layout.setContentsMargins(8, 4, 8, 4)
        self.lcd_display = QLCDNumber()
        self.lcd_display.setDigitCount(6)
        self.lcd_display.setSegmentStyle(QLCDNumber.Flat)
        self.lcd_display.display(0.00)
        lcd_layout.addWidget(self.lcd_display)
        lcd_unit = QLabel("dB")
        lcd_unit.setObjectName("lcdUnit")
        lcd_layout.addWidget(lcd_unit)
        layout.addWidget(lcd_frame)
        return group

    def _create_value_editor(self, value, bottom, top):
        edit = QLineEdit(f"{float(value):.2f}")
        edit.setAlignment(Qt.AlignRight)
        edit.setFixedWidth(90)
        validator = QDoubleValidator(bottom, top, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        edit.setValidator(validator)
        button = QPushButton("设置")
        return edit, button

    def _add_separator(self, layout):
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFixedWidth(1)
        separator.setObjectName("separator")
        layout.addWidget(separator)

    def _connect_signals(self):
        self.output_radio.toggled.connect(lambda checked: checked and self.set_mode("output"))
        self.input_radio.toggled.connect(lambda checked: checked and self.set_mode("input"))

        for button in (self.output_target_btn, self.input_target_btn):
            button.clicked.connect(self._on_set_target)
        for button in (self.output_min_att_btn, self.input_min_att_btn):
            button.clicked.connect(self._on_set_min_att)

        self.output_start_btn.clicked.connect(self.start_formula)
        self.input_start_btn.clicked.connect(self.start_formula)
        self.output_stop_btn.clicked.connect(self.stop_formula)
        self.input_stop_btn.clicked.connect(self.stop_formula)

        self.set_wave_btn.clicked.connect(self._on_set_wavelength)
        self.set_atten_btn.clicked.connect(self._on_set_attenuation)
        self.close_btn.clicked.connect(self._on_close_channel)
        self.reset_btn.clicked.connect(self._on_reset_channel)
        self.atten_input.returnPressed.connect(self._on_set_attenuation)

    def _setup_refresh_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(self.refresh_interval)

    def _load_initial_data(self):
        try:
            success, info = self.jw8507.read_RT_info(self.address)
            if success:
                self._sync_rt_info(info)
                self._emit_log(
                    f"通道 {self.address} 初始化: 波长={info.get('波长信息')}nm, "
                    f"衰减={self.current_attenuation:.2f}dB"
                )
        except Exception as exc:
            self._emit_log(f"通道 {self.address} 读取初始数据失败: {exc}")

    def refresh_display(self):
        if (
            self.mode == "input"
            and self.power_bridge is not None
            and self.power_meter_channel is not None
        ):
            self._update_input_power(self.power_bridge.get_power(self.power_meter_channel))

        try:
            success, info = self.jw8507.read_RT_info(self.address)
            if success:
                self._sync_wavelength(info.get("波长信息", None))
                if not self._formula_running():
                    self._sync_rt_info(info)
        except Exception as exc:
            if not self._last_refresh_failed:
                self._emit_log(f"刷新通道 {self.address} 失败: {exc}")
                self._last_refresh_failed = True
        else:
            self._last_refresh_failed = False

    def start_auto_refresh(self, interval_ms: int = 500):
        self.refresh_timer.start(interval_ms)

    def stop_auto_refresh(self):
        self.refresh_timer.stop()

    def set_mode(self, mode: str, persist: bool = True):
        if mode not in ("output", "input"):
            return False
        changed = self.mode != mode
        if self.mode != mode:
            self.stop_formula()
            self.mode = mode
            self._emit_log(f"通道 {self.address} 模式切换为 {'输出通道' if mode == 'output' else '输入通道'}")
        self._apply_mode_to_ui()
        if changed and persist:
            self.config_changed.emit(self.address, "mode", self.mode)
        return True

    def set_target(self, target: float, persist: bool = True):
        self.target = float(target)
        self._sync_parameter_inputs()
        if self.formula_thread and self.formula_thread.isRunning():
            self.formula_thread.update_target(self.target)
        self._emit_log(f"通道 {self.address} 目标值设置为 {self.target:.2f} dBm")
        if persist:
            self.config_changed.emit(self.address, "target", self.target)
        return True

    def set_min_att(self, min_att: float, persist: bool = True):
        self.min_att = max(0.0, float(min_att))
        self._sync_parameter_inputs()
        if self.formula_thread and self.formula_thread.isRunning():
            self.formula_thread.update_min_att(self.min_att)
        self._emit_log(f"通道 {self.address} ATT 最小值设置为 {self.min_att:.2f} dB")
        if persist:
            self.config_changed.emit(self.address, "min_att", self.min_att)
        return True

    def set_power_meter_channel(self, channel_index, persist: bool = True):
        if channel_index is None:
            self.power_meter_channel = None
        else:
            channel_index = int(channel_index)
            max_count = 4
            if self.power_bridge is not None and hasattr(self.power_bridge, "get_channel_count"):
                max_count = self.power_bridge.get_channel_count()
            if channel_index < 0 or channel_index >= max_count:
                return False
            self.power_meter_channel = channel_index

        self._sync_pm_channel_combo()
        if persist:
            self.config_changed.emit(self.address, "pm_channel", self.power_meter_channel)
        return True

    def start_formula(self):
        if self._formula_running():
            return True
        if self.mode == "input":
            if self.power_bridge is None:
                self._emit_log(f"通道 {self.address} 输入模式缺少功率计桥接器")
                return False
            if self.power_meter_channel is None:
                QMessageBox.warning(self, "提示", "请先选择要读取的功率计通道", QMessageBox.Ok)
                return False

        try:
            thread = AttFormulaThread(
                channel_address=self.address,
                jw8507_device=self.jw8507,
                mode=self.mode,
                target=self.target,
                min_att=self.min_att,
                power_bridge=self.power_bridge,
                power_meter_channel=self.power_meter_channel,
                interval_ms=self.formula_interval_ms,
                parent=self,
            )
        except Exception as exc:
            self._emit_log(f"通道 {self.address} 启动公式失败: {exc}")
            return False

        thread.att_updated.connect(self._on_att_updated_from_thread)
        thread.opm_updated.connect(self._update_opm)
        thread.input_power_updated.connect(self._update_input_power)
        thread.alarm_triggered.connect(self._on_alarm)
        thread.alarm_cleared.connect(self._on_alarm_clear)
        thread.log_message.connect(self._emit_log)
        thread.running_status.connect(self._update_formula_status)
        thread.finished.connect(self._on_thread_finished)
        self.formula_thread = thread
        thread.start()
        self._update_formula_status(True)
        return True

    def stop_formula(self):
        if self.formula_thread:
            if self.formula_thread.isRunning():
                self.formula_thread.stop()
                self.formula_thread.wait(2000)
            self.formula_thread = None
        if self.alarm_active or self._alarm_dialog is not None:
            self._on_alarm_clear()
        self._update_formula_status(False)
        return True

    def get_status(self):
        return {
            "CH": self.address,
            "Mode": self.mode,
            "Target": self.target,
            "MinAtt": self.min_att,
            "Attenuation": self.current_attenuation,
            "OPM": self.latest_opm,
            "InputPower": self.latest_input_power,
            "PMChannel": self.power_meter_channel,
            "FormulaRunning": self._formula_running(),
            "Alarm": self.alarm_active,
        }

    def _on_pm_channel_changed(self, _index=None):
        if not hasattr(self, "pm_channel_combo"):
            return
        self.set_power_meter_channel(self.pm_channel_combo.currentData())

    def _on_set_target(self):
        edit = self.output_target_input if self.mode == "output" else self.input_target_input
        try:
            self.set_target(float(edit.text()))
        except ValueError:
            self._emit_log("请输入有效的目标值")

    def _on_set_min_att(self):
        edit = self.output_min_att_input if self.mode == "output" else self.input_min_att_input
        try:
            self.set_min_att(float(edit.text()))
        except ValueError:
            self._emit_log("请输入有效的 ATT 最小值")

    def _on_set_wavelength(self):
        wavelength = self.wave_combo.currentData()
        try:
            if self.jw8507.set_waveLength(self.address, wavelength):
                self._emit_log(f"通道 {self.address} 波长设置成功: {wavelength} nm")
            else:
                self._emit_log(f"通道 {self.address} 波长设置失败")
        except Exception as exc:
            self._emit_log(f"设置波长异常: {exc}")

    def _on_set_attenuation(self):
        text = self.atten_input.text().strip()
        if not text:
            return
        try:
            attenuation = float(text)
        except ValueError:
            self._emit_log("请输入有效的衰减值")
            return
        if attenuation < 0 or attenuation > 60:
            QMessageBox.warning(self, "范围错误", "衰减值有效范围: 0 ~ 60 dB", QMessageBox.Ok)
            return
        try:
            if self.jw8507.set_attenuation(self.address, attenuation):
                self._emit_log(f"通道 {self.address} 衰减设置成功: {attenuation:.2f} dB")
            else:
                self._emit_log(f"通道 {self.address} 衰减设置失败")
        except Exception as exc:
            self._emit_log(f"设置衰减异常: {exc}")

    def _on_close_channel(self):
        try:
            if self.jw8507.set_CloseReset(self.address, "Close"):
                self._emit_log(f"通道 {self.address} 已关断")
            else:
                self._emit_log(f"通道 {self.address} 关断失败")
        except Exception as exc:
            self._emit_log(f"关断通道异常: {exc}")

    def _on_reset_channel(self):
        try:
            if self.jw8507.set_CloseReset(self.address, "Reset"):
                self._emit_log(f"通道 {self.address} 已重置")
            else:
                self._emit_log(f"通道 {self.address} 重置失败")
        except Exception as exc:
            self._emit_log(f"重置通道异常: {exc}")

    def _on_att_updated_from_thread(self, att_value):
        self.current_attenuation = float(att_value)
        self._update_att_display()

    def _on_thread_finished(self):
        self.formula_thread = None
        self._update_formula_status(False)

    def _on_alarm(self, att_value):
        self.alarm_active = True
        message = f"ATT={att_value:.2f} dB 低于最小值 {self.min_att:.2f} dB"
        self.alarm_signal.emit(self.address, message)
        self._block_ui_controls(True)
        self._update_alarm_indicator()
        self._show_alarm_dialog(att_value)

    def _on_alarm_clear(self):
        if not self.alarm_active and self._alarm_dialog is None:
            return
        self.alarm_active = False
        self._block_ui_controls(False)
        self._update_alarm_indicator()
        self._close_alarm_dialog()

    def _show_alarm_dialog(self, att_value):
        if self._alarm_dialog is None:
            self._alarm_dialog = AlarmMessageBox(self)
            self._alarm_dialog.setWindowTitle("ATT 过低报警")
            self._alarm_dialog.setIcon(QMessageBox.Warning)
            self._alarm_dialog.setStandardButtons(QMessageBox.NoButton)
            self._alarm_dialog.setWindowModality(Qt.ApplicationModal)
            self._alarm_dialog.setWindowFlags(
                self._alarm_dialog.windowFlags() & ~Qt.WindowCloseButtonHint
            )
        self._alarm_dialog.prevent_close()
        self._alarm_dialog.setText(
            f"通道 CH{self.address} ATT 值 ({att_value:.2f} dB) 低于预设最小值 "
            f"({self.min_att:.2f} dB)！\n\n"
            "请现场人员手动修改生产环境。\n"
            "公式检测线程仍在后台运行，恢复正常后将自动关闭此提示。"
        )
        self._alarm_dialog.show()

    def _close_alarm_dialog(self):
        if self._alarm_dialog is not None:
            self._alarm_dialog.allow_close()
            self._alarm_dialog.hide()
            self._alarm_dialog.deleteLater()
            self._alarm_dialog = None

    def _block_ui_controls(self, blocked):
        controls = [
            self.output_radio,
            self.input_radio,
            self.output_target_input,
            self.output_target_btn,
            self.output_min_att_input,
            self.output_min_att_btn,
            self.input_target_input,
            self.input_target_btn,
            self.input_min_att_input,
            self.input_min_att_btn,
            self.pm_channel_combo,
            self.set_wave_btn,
            self.set_atten_btn,
            self.close_btn,
            self.reset_btn,
            self.atten_input,
            self.wave_combo,
            self.output_start_btn,
            self.input_start_btn,
        ]
        for control in controls:
            control.setEnabled(not blocked)
        self.output_stop_btn.setEnabled(True)
        self.input_stop_btn.setEnabled(True)

    def _sync_rt_info(self, info):
        self.current_attenuation = float(info.get("衰减值", 0.0))
        self.latest_opm = float(info.get("输出功率值", 0.0))
        self._sync_wavelength(info.get("波长信息", None))
        self._update_att_display()
        self._update_opm(self.latest_opm)

    def _sync_wavelength(self, wavelength):
        if wavelength is None:
            if not self._wavelength_missing_logged:
                self._emit_log(f"通道 {self.address} 波长信息为空，跳过同步")
                self._wavelength_missing_logged = True
            return
        self._wavelength_missing_logged = False
        if self.wave_combo.currentData() == wavelength:
            return
        for index in range(self.wave_combo.count()):
            if self.wave_combo.itemData(index) == wavelength:
                self.wave_combo.setCurrentIndex(index)
                break

    def _sync_parameter_inputs(self):
        for edit in (self.output_target_input, self.input_target_input):
            edit.setText(f"{self.target:.2f}")
        for edit in (self.output_min_att_input, self.input_min_att_input):
            edit.setText(f"{self.min_att:.2f}")

    def _apply_mode_to_ui(self):
        self.output_radio.setChecked(self.mode == "output")
        self.input_radio.setChecked(self.mode == "input")
        self.output_group.setVisible(self.mode == "output")
        self.input_group.setVisible(self.mode == "input")
        self._sync_parameter_inputs()
        self._update_formula_status(self._formula_running())
        self._update_alarm_indicator()

    def _update_formula_status(self, running):
        text = "● 运行中" if running else "○ 已停止"
        object_name = "formulaRunning" if running else "formulaStopped"
        for label in (self.output_formula_status, self.input_formula_status):
            label.setText(text)
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
        self.output_start_btn.setEnabled(not running and not self.alarm_active)
        self.input_start_btn.setEnabled(not running and not self.alarm_active)
        self.output_stop_btn.setEnabled(running or self.alarm_active)
        self.input_stop_btn.setEnabled(running or self.alarm_active)

    def _update_alarm_indicator(self):
        text = "● 报警" if self.alarm_active else "● 正常"
        object_name = "alarmBad" if self.alarm_active else "alarmOk"
        for label in (self.output_alarm_label, self.input_alarm_label):
            label.setText(text)
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
        self.header_status_label.setText(text)
        self.header_status_label.setObjectName("statusBad" if self.alarm_active else "statusOk")
        self.header_status_label.style().unpolish(self.header_status_label)
        self.header_status_label.style().polish(self.header_status_label)

    def _update_att_display(self):
        self.lcd_display.display(f"{self.current_attenuation:.2f}")
        self.output_att_label.setText(f"{self.current_attenuation:.2f} dB")
        self.input_att_label.setText(f"{self.current_attenuation:.2f} dB")

    def _update_opm(self, opm):
        self.latest_opm = float(opm)
        self.output_opm_label.setText(f"{self.latest_opm:.2f} dBm")

    def _update_input_power(self, power):
        self.latest_input_power = float(power)
        self.input_power_label.setText(f"{self.latest_input_power:.2f} dBm")

    def _formula_running(self):
        return bool(self.formula_thread and self.formula_thread.isRunning())

    def _emit_log(self, message: str):
        self.log_signal.emit(message)

    def get_current_attenuation(self) -> float:
        return self.current_attenuation

    def set_channel_name(self, name: str):
        self.channel_label.setText(name)

    def _style_sheet(self):
        return """
            ChannelWidget {
                background-color: #f5f7fa;
                border: 1px solid #c9d1d9;
                border-radius: 4px;
            }
            QGroupBox {
                color: #24292f;
                font-weight: bold;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #24292f;
                font-family: "Microsoft YaHei", "SimHei";
                font-size: 13px;
                background: transparent;
            }
            QFrame#channelHeader {
                background-color: #0969da;
                border-radius: 3px;
            }
            QLabel#channelTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#statusOk, QLabel#alarmOk {
                color: #1a7f37;
                font-weight: bold;
            }
            QLabel#statusBad, QLabel#alarmBad {
                color: #cf222e;
                font-weight: bold;
            }
            QLabel#metricLabel {
                color: #0969da;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#formulaRunning {
                color: #1a7f37;
                font-weight: bold;
            }
            QLabel#formulaStopped {
                color: #6e7781;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff;
                color: #24292f;
                border: 1px solid #8c959f;
                border-radius: 3px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #f6f8fa;
                color: #24292f;
                border: 1px solid #8c959f;
                border-radius: 3px;
                padding: 5px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #eef1f4;
            }
            QPushButton:disabled {
                background-color: #eaeef2;
                color: #8c959f;
            }
            QPushButton#primaryBtn, QPushButton#startFormulaBtn {
                background-color: #2da44e;
                border-color: #1a7f37;
                color: #ffffff;
            }
            QPushButton#stopFormulaBtn {
                background-color: #6e7781;
                border-color: #57606a;
                color: #ffffff;
            }
            QPushButton#setAttenBtn {
                background-color: #0969da;
                border-color: #0550ae;
                color: #ffffff;
            }
            QPushButton#closeBtn {
                background-color: #cf222e;
                border-color: #a40e26;
                color: #ffffff;
            }
            QPushButton#resetBtn {
                background-color: #bf8700;
                border-color: #9a6700;
                color: #ffffff;
            }
            QFrame#separator {
                background-color: #d0d7de;
                border: none;
            }
            QFrame#lcdFrame {
                background-color: #1f2328;
                border: 1px solid #57606a;
                border-radius: 3px;
            }
            QLCDNumber {
                background: transparent;
                color: #3fb950;
                border: none;
            }
            QLabel#lcdUnit {
                color: #3fb950;
                font-weight: bold;
            }
        """
