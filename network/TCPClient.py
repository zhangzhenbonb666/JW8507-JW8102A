#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TCP客户端模块

本模块实现了一个基于PyQt5 QThread的TCP客户端，用于连接远程功率计控制服务器。
支持异步数据收发，通过Qt信号通知连接状态变化。

主要功能:
    - 异步TCP连接管理
    - 基于换行符的消息分帧
    - 自动重连和断线检测
    - 自定义数据处理回调

类:
    TCPClient: TCP客户端线程类
    
使用示例:
    >>> client = TCPClient("192.168.1.100", 1234, func=handle_data)
    >>> client.connectedSignal.connect(on_connect)
    >>> client.start()
    >>> client.send('{"cmd": "GetPower"}')
"""

import sys
import socket
import time

from PyQt5.QtCore import QThread, pyqtSignal


class TCPClient(QThread):
    """
    TCP客户端线程类
    
    基于PyQt5 QThread实现的异步TCP客户端，支持自动重连和数据处理回调。
    
    信号:
        connectedSignal: 连接状态变化信号，参数为("YES"/"NO", 信息描述)
        infoSignal: 信息通知信号，参数为(客户端名称, 消息内容)
        
    属性:
        host: 服务器IP地址
        port: 服务器端口
        running: 运行状态标志
        isconnected: 连接状态标志
        func: 数据处理回调函数
    """
    
    # Qt信号定义
    connectedSignal = pyqtSignal([str, str])  # 连接状态信号
    infoSignal = pyqtSignal([str, str])        # 信息通知信号

    def __init__(self, host, port, name=None, func=lambda x: x):
        """
        初始化TCP客户端
        
        Args:
            host: 服务器IP地址
            port: 服务器端口号
            name: 客户端名称标识（可选）
            func: 接收数据后的处理回调函数
        """
        super().__init__()
        self.host = host
        self.port = int(port)
        self.running = False
        self.isconnected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(2)  # 设置连接超时时间为2秒
        self.func = func  # 数据处理回调函数
        self.name = name 


    def start(self):
        """使用qt线程进行socket通信"""
        self.running = True
        super().start()

    def run(self):
        """线程运行函数"""
        try:
            self.socket.connect((self.host, self.port))
            # logging.info("Connected to server")
            print(f"Connected to server:{self.host},{self.port}\n")
            self.connectedSignal.emit("YES", "链接成功！") # 发送信号，连接成功
            self.socket.settimeout(None) # 取消超时时间，保持链接状态
            self.isconnected = True
            buffer = ""
            while self.running:
                data = self.socket.recv(1024).decode('utf-8')  # Buffer size is 1024 bytes
                # print(f"收到来自{self.socket.getpeername()}的数据:{data}\n")
                # print("received:"+data)
                if not data:
                    # logging.info("Connection closed by server")
                    print("Connection closed by server")
                    self.connectedSignal.emit("NO", "连接断开！")
                    break
                buffer += data
                if "\n" in buffer:
                    messages = buffer.split("\n")
                    for message in messages[:-1]:
                        if message:
                            self.func(message)
                            self.infoSignal.emit(self.name, "received:"+message)
                    buffer = messages[-1]
        except (ConnectionRefusedError, TimeoutError):
            # logging.error("Connection refused")
            print("Connection filed\n")
            self.connectedSignal.emit("NO", "连接失败！")
            self.isconnected = False
        except Exception as e:
            # logging.error(f"Error: {str(e)}")
            print(f"Error: {str(e)}\n")
            self.connectedSignal.emit("NO", "连接失败！")
            self.isconnected = False

    def send(self, data):
        """发送数据\n
        :param data: 要发送的数据"""
        try:
            while not self.running:
                time.sleep(0.1)
            data = data + "\n"
            self.infoSignal.emit(self.name, "send:"+data)
            self.socket.sendall(data.encode('utf-8'))
            # print("send:"+data)
        except Exception as e:
            # logging.error(f"Error: {str(e)}")
            print(f"Error: {str(e)}")
            self.connectedSignal.emit("NO", "发送失败！")

    def stop(self):
        """关闭连接"""
        if self.isconnected:
            if self.socket:
                print(f"{self.name} shutdown and close socket")
                self.socket.shutdown(socket.SHUT_RDWR)
                # self.socket.close()
            self.running = False
            self.isconnected = False
            self.connectedSignal.emit("NO", "关闭连接！")
            # super().terminate()
        else:
            self.connectedSignal.emit("NO", "未连接！")

if __name__ == '__main__':
    import json
    from PyQt5.QtWidgets import QApplication

    def fun(data):
        print("func:",data)

    app = QApplication(sys.argv)
    client = TCPClient("127.0.0.1", 10003, func=fun)
    client.start()
    time.sleep(1)
    # str = json.dumps({"opcode":"StartAnalyzing", "parameter":{"FilePath":"D:\文件\工程数据\指向差标校.17下午中国标准时间", "IfUseSheet":True, "Sheet":"ElectricMachinery", "Variable":{"fw":1, "fy":0.1}}})
    str = json.dumps({"opcode":"PortOpen", "parameter":{"FilePath":"", "AutoAnalysis":True, "IfUseSheet":True, "Sheet":"ElectricMachinery", "Variable":{"fw":1, "fy":0.1}}})
    client.send(str)
    sys.exit(app.exec_())
