from operator import indexOf
from typing import Literal
import serial
import threading
from struct import unpack


class JW8507:
    """
    JW8507 8通道衰减器控制类
    
    帧格式：帧头(1) + 地址(1) + 长度(1) + 命令(2) + 数据(0~200) + 校验(1) + 帧尾(1)
    """
    HEADER = 0x7B  # 帧头
    FOOTER = 0x7D  # 帧尾
    waveLength_list = [1310, 1490, 1540, 1550, 1563, 1625]

    def __init__(self, ser: serial.Serial):
        self.ser = ser
        self.lock = threading.Lock()

    def connect(self):
        """打开串口连接"""
        if not self.ser.is_open:
            self.ser.open()

    def disconnect(self):
        """关闭串口连接"""
        if self.ser.is_open:
            self.ser.close()

    @staticmethod
    def calculate_checksum(data: bytes) -> int:
        """
        计算校验和
        
        校验算法: CHECK = (~(帧头+地址+长度+命令+数据)) + 1，取低字节
        
        :param data: 需要计算校验和的数据（从帧头到数据，不包含校验和帧尾）
        :return: 校验和（1字节，0-255）
        """
        # 累加所有字节
        total = sum(data)
        # 取反加1，然后取低字节
        checksum = (~total + 1) & 0xFF
        return checksum

    def make_command(self, address: int, command: int, data: bytes = b"") -> bytes:
        """
        生成完整的命令帧
        
        :param address: 设备地址（1字节，0x00-0xFF）
        :param command: 命令码（2字节，0x0000-0xFFFF）
        :param data: 数据（0-200字节）
        :return: 完整的命令帧（bytes）
        :raises ValueError: 数据长度超过200字节时抛出异常
        """

        # 长度 = 地址(1) + 长度(1) + 命令(2) + 数据(n) + 校验(1) = 5 + len(data)
        length = 5 + len(data)

        # 构建帧（不含校验和帧尾）
        frame = bytes([
            self.HEADER,                # 帧头
            address & 0xFF,             # 地址
            length & 0xFF,              # 长度
            (command >> 8) & 0xFF,      # 命令高字节
            command & 0xFF,             # 命令低字节
        ]) + data

        # 计算校验和
        checksum = self.calculate_checksum(frame)

        # 拼接完整帧：数据 + 校验 + 帧尾
        complete_frame = frame + bytes([checksum, self.FOOTER])

        return complete_frame

    def make_command_hex(self, address: str, command: str, data: str = "") -> bytes:
        """
        使用十六进制字符串生成命令帧（便捷方法）
        
        :param address: 地址的十六进制字符串，如 "01"
        :param command: 命令的十六进制字符串，如 "0003"
        :param data: 数据的十六进制字符串，如 "00FF"
        :return: 完整的命令帧（bytes）
        """
        addr = int(address, 16)
        cmd = int(command, 16)
        data_bytes = bytes.fromhex(data) if data else b""
        return self.make_command(addr, cmd, data_bytes)

    def send_command(self, address: int, command: int, data: bytes = b"", 
                     response_length: int = 0) -> bytes:
        """
        发送命令并接收响应
        
        :param address: 设备地址
        :param command: 命令码
        :param data: 数据
        :param response_length: 期望的响应长度（字节数）
        :return: 响应数据
        """
        with self.lock:
            cmd = self.make_command(address, command, data)
            self.ser.write(cmd)
            if response_length > 0:
                return self.ser.read(response_length)
            return b""

    def read_version(self, address: int = 0x01) -> tuple[bool, dict[str, int]]:
        """
        读取设备版本信息
        
        :return: 是否成功, 包含模块版本、硬件版本、软件版本的字典
        """
        result = False
        command=0x0003
        response = self.send_command(address=address, command=command, response_length=10)
        if len(response) >= 10:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                data = {
                    "模块版本": response[5],
                    "硬件版本": response[6],
                    "软件版本": response[7]
                }
                return result, data
        return result, {}

    def read_waveLength_info(self, address: int = 0x01) -> tuple[bool, dict[str, int]]:
        """
        读取波长信息
        
        :return: 是否成功, 包含波长信息的字典
        """
        result = False
        command=0x072E
        response = self.send_command(address=address, command=command, response_length=20)
        if len(response) >= 0:
            # 返回数据是不定长，需要通过第一字节的值来确定有多少个波长，数据有多长，所以需要先读取第一字节来确定有多少个波长
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                count = response[5]
                data_length = count * 2
                data = response[6:6+data_length]
                waveLength_list = []
                for i in range(0, data_length, 2):
                    waveLength_list.append(int.from_bytes(data[i:i+2], byteorder="little"))
                return True, {
                    "波长列表": waveLength_list
                }
        return result, {}

    def read_RT_info(self, address: int = 0x01) -> tuple[bool, dict[str, int]]:
        """
        读取实时信息
        
        :return: 是否成功, 包含实时信息的字典
        """
        result = False
        command=0x1436
        response = self.send_command(address=address, command=command, response_length=14)
        if len(response) >= 14:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                data = response[5:-2]
                return result, {
                    "仪表工作模式": {0:"衰减模式",1:"锁定输出模式"}[data[0]],
                    "衰减模式": data[1],
                    "波长信息": self.waveLength_list[data[2]],
                    "衰减值": int.from_bytes(data[3:5], byteorder="little") / 100,
                    "输出功率值": int.from_bytes(data[5:7], byteorder="little", signed=True) / 100
                }
        return result, {}

    def default_display(self, address: int = 0x01) -> bool:
        """
        默认显示
        
        :return: 是否成功, 包含默认显示信息的字典
        """
        result = False
        command=0x0005
        response = self.send_command(address=address, command=command, response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

    def set_waveLength(self, address: int = 0x01, waveLength: int = 0) -> bool:
        """
        设置波长
        
        :return: 是否成功
        """
        result = False
        command=0x143A
        try:
            index = self.waveLength_list.index(waveLength)
        except ValueError:
            print(f"波长{waveLength}不在波长列表中")
            return False
        response = self.send_command(address=address, command=command, data=index.to_bytes(1, byteorder="little"), response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

    def set_attenuation(self, address: int = 0x01, attenuation: float = 0.0) -> bool:
        """
        设置衰减
        :param address: 设备地址 0xFF为设置全部
        :param attenuation: 衰减值，单位：dB
        :return: 是否成功
        """
        result = False
        command=0x143C
        response = self.send_command(address=address, command=command, data=int(attenuation * 100).to_bytes(2, byteorder="little"), response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

    def set_CloseReset(self, address: int = 0x01, ctrl:str = Literal["Close", "Reset"]) -> bool:
        """
        设定关断/清零

        :return: 是否成功
        """
        result = False
        command=0x1434
        data = {"Close":bytes([0xFF, 0xFF]), "Reset":bytes([0x00, 0x00])}[ctrl]
        response = self.send_command(address=address, command=command, data=data, response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

    # V22_10及之后的无内部监控功能的设备无法使用
    def set_outputMode(self, address: int = 0x01, mode:str = Literal["Attenuation", "Lock"]) -> bool:
        """
        设定输出模式
        :param address: 设备地址
        :param mode: 输出模式 "Attenuation"为衰减模式 "Lock"为锁定输出模式
        :return: 是否成功
        """
        result = False
        command=0x1438
        data = {"Attenuation":bytes([0x00]), "Lock":bytes([0x01])}[mode]
        response = self.send_command(address=address, command=command, data=data, response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

    def set_lockPower(self, address: int = 0x01, power:float = 0.0) -> bool:
        """
        设定锁定输出功率
        :param address: 设备地址
        :param power: 锁定输出功率，单位：mW
        :return: 是否成功
        """
        result = False
        command=0x143E
        response = self.send_command(address=address, command=command, data=int(power * 100).to_bytes(2, byteorder="little", signed=True), response_length=7)
        if len(response) >= 7:
            if int.from_bytes(response[3:5], byteorder="big") == (command + 1):
                result = True
                return result
        return result

if __name__ == "__main__":
    # 创建串口对象
    ser = serial.Serial("COM8", 115200, timeout=0.1)
    jw8507 = JW8507(ser)
    
    # 连接设备
    jw8507.connect()
    
    # 读取版本
    version = jw8507.read_version()
    print(f"版本信息: {version}")

    # # 读取波长信息
    # waveLength_info = jw8507.read_waveLength_info()
    # print(f"波长信息: {waveLength_info}")

    # # 读取实时信息
    # RT_info = jw8507.read_RT_info()
    # print(f"实时信息: {RT_info}")

    # # 默认显示
    # default_display = jw8507.default_display()
    # print(f"默认显示: {default_display}")

    # # 设置波长
    # jw8507.set_waveLength(address=0x02, waveLength=1563)
    # # 设置衰减
    # jw8507.set_attenuation(address=0x02, attenuation=10.0)
    # # 设定关断/清零
    # jw8507.set_CloseReset(address=0x01, ctrl="Reset")
    # 设定输出模式
    jw8507.set_outputMode(address=0x01, mode="Lock")
    # # 设定锁定输出功率
    # jw8507.set_lockPower(address=0x01, power=0.0)
    # 断开连接
    jw8507.disconnect()
