#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
嘉慧功率计设备通信协议模块

本模块实现了与嘉慧光电JW8103A/JW8102A功率计的串口通信协议。
协议格式参考《嘉慧功率计JW8102A_JW8103A 用户通信协议V23.05.06.pdf》

协议帧格式:
    帧头(1字节) + 地址(1字节) + 长度(1字节) + 命令(2字节) + 数据(N字节) + 校验(1字节) + 帧尾(1字节)
    - 帧头固定为 0x7B ('{')
    - 帧尾固定为 0x7D ('}')
    - 校验为除帧尾和校验本身外所有字节的补码和

主要功能:
    - 连接/断开设备
    - 读取4通道功率值（dBm和mW）
    - 设置/读取用户波长
    - 屏幕数据读取
    - 校准功能

类:
    JW8103A: 功率计设备控制类

辅助函数:
    ToI32: 16进制字符串转32位有符号整数
    ToI16: 16进制字符串转16位有符号整数
    ToFloat: 16进制字符串转浮点数
    ToHex: 整数转16进制字符串
"""

import struct
import bitstring
from typing import Literal
import time
import threading


def ToI32(hex_str:str) -> int:
    """
    16进制字符串转换为32位无符号整数\n"""
    hex_str = hex_str.upper()
    # 按字节反序
    temp = ""
    for i in range(len(hex_str), 0, -2):
        temp += hex_str[i-2:i]
    hex_str = temp
    # 转换为有符号32位整数
    unsigned_num = int(hex_str, 16)
    if unsigned_num & 0x80000000:
        signed_num = unsigned_num - 0x100000000
    else:
        signed_num = unsigned_num
    return signed_num


def ToI16(hex_str:str) -> int:
    """
    4字节16进制字符串转换为16位有符号整数\n"""
    hex_str = hex_str.upper()
    # 按字节反序
    temp = ""
    for i in range(len(hex_str), 0, -2):
        temp += hex_str[i-2:i]
    hex_str = temp
    # 转换为有符号16位整数
    unsigned_num = int(hex_str, 16)
    if unsigned_num & 0x8000:
        signed_num = unsigned_num - 0x10000
    else:
        signed_num = unsigned_num
    return signed_num


def ToFloat(hex_str:str) -> float:
    """
    4字节16进制字符串转换为浮点数\n"""
    hex_str = hex_str.upper()
    bytes_data = bytes.fromhex(hex_str)
    float_data = struct.unpack('<f', bytes_data)[0]
    return float_data


def ToHex(num:int, size:int) -> str:
    hex_str = num.to_bytes(size, byteorder='little', signed=True).hex().upper()
    return hex_str


class JW8103A:
    """
    嘉慧JW8103A/JW8102A光功率计控制类
    
    通过串口与功率计设备通信，实现功率读取、波长设置等功能。
    支持4通道同时测量，波长范围850nm-1625nm。
    
    协议常量:
        header: 帧头 0x7B
        footer: 帧尾 0x7D
        ID: 设备地址 0xFF（广播地址）
        
    属性:
        ser: 串口对象
        ser_lock: 串口操作锁，确保线程安全
        WaveToIndex: 波长到索引的映射字典
        IndexToWave: 索引到波长的映射字典
        
    使用示例:
        >>> import serial
        >>> ser = serial.Serial("COM1", 115200, timeout=1)
        >>> jw = JW8103A(ser)
        >>> jw.Connect()
        True
        >>> jw.Read_User_Power()
        [-15.234, -16.789, -14.567, -18.901]
    """
    
    # 协议常量定义
    header = "7B"  # 帧头 '{'
    footer = "7D"  # 帧尾 '}'
    ID = "FF"      # 广播地址
    # 协议帧模板
    protocol = {"帧头":header, "地址":ID, "长度":None, "命令":None, "数据":None, "校验":None, "帧尾":footer}
    
    # 标准波长与索引的映射（设备内置6个标准波长）
    WaveToIndex = {"850":1, "1300":2, "1310":3, "1490":4, "1550":5, "1625":6}
    IndexToWave = {1:"850", 2:"1300", 3:"1310", 4:"1490", 5:"1550", 6:"1625"}

    def __init__(self, ser):
        """
        JW8103A类初始化\n
        :param ser: 串口对象，用于与硬件通信\n"""
        self.ser = ser
        self.ser_lock = threading.Lock()  # 串口操作锁，确保实例级线程安全

    def Connect(self):
        """"连接"""
        with self.ser_lock:
            cmd = self.make_cmd("0140", "")
            self.ser.write(cmd)
            result = self.ser.read(11).hex()
            if result:
                return True
            else:
                return False
    
    
    def Calibration_Power(self) -> list:
        """读取校准功率功率值\n
        返回4个通道的功率值"""
        with self.ser_lock:
            cmd = self.make_cmd("0142", "")
            self.ser.write(cmd)
            bytes = self.ser.read(15).hex()
            result = []
            if len(bytes) != 0:
                for i in range(10, len(bytes)-4, 4):
                    result.append(ToI32(bytes[i:i+4])/1000)
            return result


    def Calibration_Wavelength(self, CH:Literal[1,2,3,4], Wavelength:int):
        """校准波长切换波长及通道\n
        :param CH: 通道号，1~4\n
        :param Wavelength: 波长，单位nm
        可以使用标准波长索引850,1300,1310，1490,1550,1625 一共6个波长对应索引1到6"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0144", f"{ToHex(CH, 1)}{ToHex(Wavelength, 1)}"))
            result = self.ser.read(7).hex()
            if result:
                return True
            else:
                return False
        

    def User_Wavelength(self, CH:Literal[1,2,3,4], Wavelength:int):
        """切换用户波长\n
        :param CH: 通道号，1~4\n
        :param Wavelength: 波长，单位nm
        可以使用标准波长索引850,1300,1310，1490,1550,1625 一共6个波长对应索引1到6"""
        with self.ser_lock:
            if Wavelength in self.IndexToWave.keys():
                Wavelength = Wavelength
            elif Wavelength in self.WaveToIndex.keys():
                Wavelength = self.WaveToIndex[Wavelength]
            else:
                return False
            self.ser.write(self.make_cmd("0160", f"{ToHex(CH, 1)}{ToHex(Wavelength, 1)}"))
            result = self.ser.read(7).hex()
            if result:
                # print(result)
                return True
            else:
                return False
        

    def Read_User_Power(self) -> list:
        """读取用户功率值\n
        返回4个通道的功率值"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0162", ""))
            bytes = self.ser.read(23).hex()
            result = []
            if len(bytes) != 0:
                for i in range(10, len(bytes)-4, 8):
                    result.append(ToI32(bytes[i:i+8])/1000)
            return result
    

    def Absolute_PowerDeviationValue(self, Value:float):
        """设置绝对功率偏差值\n
        :param Value: 偏差值，单位dBm"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0166", ToHex(int(Value*1000), 4)))
            result = self.ser.read(7).hex()
            if result:
                return True
            else:
                return False
    

    def Read_User_Power_mw(self) -> list:
        """读取用户mw数据\n
        返回4个通道的mw数据"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0164", ""))
            bytes = self.ser.read(23).hex()
            print(bytes)
            result = []
            if len(bytes) != 0:
                for i in range(10, len(bytes)-4, 8):
                    result.append(ToFloat(bytes[i:i+8]))
            return result
    

    def Write_Wavelength(self, Wavelength:float):
        """设置测量波长\n
        :param Wavelength: 测量波长，单位nm
        写入波长范围850.00---1625.00"""
        with self.ser_lock:
            if Wavelength < 850.00 or Wavelength > 1625.00:
                return False
            self.ser.write(self.make_cmd("0146", ToHex(int(Wavelength*100), 4)))
            result = self.ser.read(7).hex()
            if result:
                return True
            else:
                return False
        

    def Write_REF(self, CH:Literal[1,2,3,4], REF:float):
        """设置参考电压\n
        :param CH: 通道号，1~4\n
        :param REF: 参考电压，单位V"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0148", f"{ToHex(CH, 1)}{ToHex(int(REF*1000), 4)}"))
            result = self.ser.read(7).hex()
            if result:
                return True
            else:
                return False
        

    def Read_Screen_Data(self) -> dict:
        """读取屏幕数据\n
        返回4个通道的屏幕数据"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("014A", ""))
            bytes = self.ser.read(43).hex()
            channels = None
            if len(bytes) != 0:
                channels = {"CH1":{"Wavelength":None, "Power":None, "REF":None}, 
                            "CH2":{"Wavelength":None, "Power":None, "REF":None}, 
                            "CH3":{"Wavelength":None, "Power":None, "REF":None}, 
                            "CH4":{"Wavelength":None, "Power":None, "REF":None}}
                channels_num = 1
                for i in range(10, len(bytes)-4, 18):
                    channels[f"CH{channels_num}"]["Wavelength"] = self.IndexToWave[int(bytes[i:i+2], 16)]
                    channels[f"CH{channels_num}"]["Power"] = ToI32(bytes[i+2:i+10])/1000
                    channels[f"CH{channels_num}"]["REF"] = ToI32(bytes[i+10:i+18])/1000
                    channels_num += 1
            return channels
        

    def Set_User_Wavelength(self, Count:int, Wavelengths:list[int]):
        """设置用户波长\n
        :param Count:波长总数，最大32波长,默认占用前六个，使用该指令时只需输入新增个数\n
        :param Wavelength: 波长，单位nm, 850---1625, 两字节十六进制字符串整型，只需输入新增波长个数的波长值即可\n"""
        with self.ser_lock:
            if Count > 28:
                return False
            data = ""
            for wavelength in Wavelengths:
                if wavelength < 850 or wavelength > 1625:
                    return False
                data = data + ToHex(wavelength, 2)
            self.ser.write(self.make_cmd("0732", f"{ToHex((Count+6), 1)}520314051E05D2050E065906{data}"))
            result = self.ser.read(7).hex()
            if result:
                return True
            else:
                return False
        
    
    def Read_User_Wavelength(self) -> list:
        """读取用户波长\n
        返回用户波长列表"""
        with self.ser_lock:
            self.ser.write(self.make_cmd("0730", ""))
            bytes = b''
            # time.sleep(0.01)
            while not self.ser.in_waiting:
                pass
            while self.ser.in_waiting:
                bytes += self.ser.read()
            bytes = bytes.hex().upper()
            result = []
            if len(bytes) != 0:
                for i in range(12, len(bytes)-4, 4):
                    result.append(ToI16(bytes[i:i+4]))
            for i in range(int(bytes[10:12])):
                self.IndexToWave[i+1] = f"{result[i]:.2f}"
                self.WaveToIndex[f"{result[i]:.2f}"] = i+1
            return result


    def make_cmd(self, cmd:str, data:str) -> bytes:
        """
        组装命令\n
        :param cmd: 2字节的十六进制字符串，命令码\n
        :param data: 0~200字节的十六进制字符串，命令数据\n"""
        self.protocol["命令"] = cmd.upper().zfill(4)
        self.protocol["数据"] = data.upper() + '0' * (len(data) % 2)
        self.protocol["长度"] = hex(len(data)//2 + 5)[2:].upper().zfill(2)
        self.protocol["校验"] = self.check_sum(self.protocol).zfill(2)
        cmd_str = ""
        for key in self.protocol:
            cmd_str += self.protocol[key]
        return bitstring.BitArray(hex=cmd_str).bytes
        

    def check_sum(self, cmd_dict:dict) -> str:
        """
        计算校验和\n
        :param cmd_dict: 字典，包含命令各字段的十六进制字符串\n"""
        sum = 0
        for key in cmd_dict:
            if key!= "帧尾" and key!= "校验":
                for i in range(0, len(cmd_dict[key]), 2):
                    sum += int(cmd_dict[key][i:i+2], 16)
        sum = ~sum
        sum += 1
        return hex(sum & 0xFF)[2:].upper().zfill(2)
    
    

if __name__ == "__main__":
    import serial
    ser = serial.Serial("COM32", 115200, timeout=1)
    jw = JW8103A(ser)
    # ser.write(jw.make_cmd("0732", "07520314051e05d2050e0659060406"))
    # ser.write(jw.make_cmd("0730", ""))
    # ser.write(jw.make_cmd("0160", "0107"))
    # print(jw.Read_User_Wavelength())
    # print(jw.Read_Screen_Data())
    # a = jw.User_Wavelength(1, 5)
    # print(ToFloat("8BED3640"))
    # while True:
    #     print(jw.Read_User_Power())
    #     time.sleep(0.5)
    print(jw.make_cmd("0162", "").hex())
