"""
通道 ATT 公式计算线程。

输出模式: new_att - old_att = opm - target
输入模式: new_att - old_att = x - target
"""
import threading

from PyQt5.QtCore import QThread, pyqtSignal


class AttFormulaThread(QThread):
    """以固定周期计算并设置 ATT。"""

    att_updated = pyqtSignal(float)
    opm_updated = pyqtSignal(float)
    input_power_updated = pyqtSignal(float)
    alarm_triggered = pyqtSignal(float)
    alarm_cleared = pyqtSignal()
    log_message = pyqtSignal(str)
    running_status = pyqtSignal(bool)

    def __init__(
        self,
        channel_address,
        jw8507_device,
        mode,
        target,
        min_att,
        power_bridge=None,
        power_meter_channel=None,
        interval_ms=1000,
        parent=None,
    ):
        super().__init__(parent)
        if mode not in ("output", "input"):
            raise ValueError("mode 必须是 output 或 input")
        if mode == "input" and (power_bridge is None or power_meter_channel is None):
            raise ValueError("输入模式必须提供 power_bridge 和 power_meter_channel")

        self.channel_address = channel_address
        self.jw8507 = jw8507_device
        self.mode = mode
        self.target = float(target)
        self.min_att = max(0.0, float(min_att))
        self.power_bridge = power_bridge
        self.power_meter_channel = power_meter_channel
        self.old_att = 0.0
        self._interval = max(0.1, float(interval_ms) / 1000.0)
        self._stop_event = threading.Event()
        self._alarm_active = False

    def run(self):
        self.running_status.emit(True)
        self.log_message.emit(
            f"CH{self.channel_address} 公式线程启动，模式={self.mode}，目标={self.target:.2f} dBm"
        )

        self._load_initial_att()

        while not self._stop_event.is_set():
            try:
                delta = self._read_delta()
                if delta is None:
                    self._stop_event.wait(self._interval)
                    continue

                new_att = self.old_att + delta
                if new_att < 0:
                    new_att = 0.0
                    self.log_message.emit(f"CH{self.channel_address} 计算 ATT 小于 0，已限制为 0 dB")

                if new_att < self.min_att:
                    self._emit_alarm(new_att)
                    self._stop_event.wait(self._interval)
                    continue

                self._clear_alarm_if_needed(new_att)

                if abs(new_att - self.old_att) > 0.01:
                    if self._device_disconnected():
                        self.log_message.emit(f"CH{self.channel_address} 设备未连接，跳过 ATT 设置")
                        self._stop_event.wait(self._interval)
                        continue

                    if self.jw8507.set_attenuation(self.channel_address, new_att):
                        self.log_message.emit(
                            f"CH{self.channel_address} ATT: {self.old_att:.2f} -> {new_att:.2f} dB"
                        )
                        self.att_updated.emit(new_att)
                        self.old_att = new_att
                    else:
                        self.log_message.emit(f"CH{self.channel_address} 设置 ATT 失败")
                else:
                    self.old_att = new_att
                    self.att_updated.emit(new_att)

            except Exception as exc:
                self.log_message.emit(f"CH{self.channel_address} 公式线程异常: {exc}")

            self._stop_event.wait(self._interval)

        self.running_status.emit(False)
        self.log_message.emit(f"CH{self.channel_address} 公式线程已停止")

    def stop(self):
        """请求停止线程。"""
        self._stop_event.set()

    def update_target(self, new_target):
        self.target = float(new_target)
        self.log_message.emit(f"CH{self.channel_address} 目标值更新为 {self.target:.2f} dBm")

    def update_min_att(self, new_min):
        self.min_att = max(0.0, float(new_min))
        self.log_message.emit(f"CH{self.channel_address} ATT 最小值更新为 {self.min_att:.2f} dB")

    def _load_initial_att(self):
        try:
            success, info = self.jw8507.read_RT_info(self.channel_address)
            if success:
                self.old_att = float(info.get("衰减值", 0.0))
                self.att_updated.emit(self.old_att)
        except Exception as exc:
            self.log_message.emit(f"CH{self.channel_address} 读取初始 ATT 失败: {exc}")

    def _read_delta(self):
        if self.mode == "output":
            success, info = self.jw8507.read_RT_info(self.channel_address)
            if not success:
                self.log_message.emit(f"CH{self.channel_address} 读取 OPM 失败")
                return None
            opm = float(info.get("输出功率值", 0.0))
            self.opm_updated.emit(opm)
            return opm - self.target

        power = float(self.power_bridge.get_power(self.power_meter_channel))
        self.input_power_updated.emit(power)
        return power - self.target

    def _emit_alarm(self, new_att):
        if not self._alarm_active:
            self._alarm_active = True
            self.alarm_triggered.emit(new_att)
        self.log_message.emit(
            f"CH{self.channel_address} 报警: ATT={new_att:.2f} dB < 最小值 {self.min_att:.2f} dB，跳过设置"
        )

    def _clear_alarm_if_needed(self, new_att):
        if self._alarm_active:
            self._alarm_active = False
            self.alarm_cleared.emit()
            self.log_message.emit(
                f"CH{self.channel_address} 报警解除: ATT={new_att:.2f} dB >= 最小值 {self.min_att:.2f} dB"
            )

    def _device_disconnected(self):
        ser = getattr(self.jw8507, "ser", None)
        if ser is None:
            return True
        return hasattr(ser, "is_open") and not ser.is_open
