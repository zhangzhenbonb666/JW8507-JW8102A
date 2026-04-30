"""
功率计数据桥接器。

在 JW8103A_Control 和 JW8507 通道公式线程之间共享最新功率计读数。
"""
import threading


class PowerMeterBridge:
    """线程安全的功率计数据桥接器（单例）。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()
        self._power_values = [0.0, 0.0, 0.0, 0.0]

    @classmethod
    def get_instance(cls):
        """获取单例实例。"""
        return cls()

    def update_power(self, channel_index: int, value_dbm: float) -> None:
        """更新指定功率计通道的功率值。"""
        with self._data_lock:
            if 0 <= channel_index < len(self._power_values):
                self._power_values[channel_index] = float(value_dbm)

    def update_all_powers(self, values) -> None:
        """批量更新功率值，最多取前 4 个通道。"""
        with self._data_lock:
            for index, value in enumerate(values[: len(self._power_values)]):
                self._power_values[index] = float(value)

    def get_power(self, channel_index: int) -> float:
        """获取指定功率计通道的最新功率值。"""
        with self._data_lock:
            if 0 <= channel_index < len(self._power_values):
                return self._power_values[channel_index]
            return 0.0

    def get_all_powers(self) -> list[float]:
        """获取全部 4 个通道的最新功率值。"""
        with self._data_lock:
            return list(self._power_values)

    def get_channel_count(self) -> int:
        """Return the number of power-meter channels available to the UI."""
        with self._data_lock:
            return len(self._power_values)

    def set_channel_count(self, count: int) -> None:
        """Set the power-meter channel count for future model variants."""
        count = max(0, int(count))
        with self._data_lock:
            if count != len(self._power_values):
                self._power_values = [0.0] * count
