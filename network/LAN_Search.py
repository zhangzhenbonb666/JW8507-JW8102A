#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
局域网服务发现模块

本模块实现了基于UDP广播的局域网服务发现机制。
允许客户端自动发现局域网内运行的功率计控制服务器。

工作原理:
    1. 服务端在固定UDP端口(44444)监听发现请求
    2. 客户端发送广播消息"DISCOVER"到255.255.255.255:44444
    3. 服务端收到请求后回复服务名称和TCP端口
    4. 客户端收集所有响应，建立可用服务列表

类:
    LAN_Search: 局域网服务发现工具类

使用示例:
    # 服务端
    >>> LAN_Search.start_discovery_server(1234, "JW8103A_Control")
    
    # 客户端
    >>> servers = LAN_Search.discover_services(timeout=5)
    >>> print(servers)  # [("JW8103A_Control", "192.168.1.100", 1234)]
"""

import socket
import threading
import time


class LAN_Search:
    """
    局域网服务发现工具类
    
    提供UDP广播的服务发现功能，包含服务端监听和客户端发现两个静态方法。
    """
    
    def __init__(self):
        pass
    
    @staticmethod
    def start_discovery_server(port, service_name="MyService"):
        """
        启动发现服务，响应客户端的发现请求
        :param port: 服务实际监听的TCP端口
        :param service_name: 服务名称标识
        """
        # 创建UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # 绑定到所有接口的指定端口
        sock.bind(('0.0.0.0', 44444))  # 使用固定端口用于发现
        
        print(f"Discovery server started, listening for clients...")
        
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                if data.decode() == "DISCOVER":
                    # 发送响应，包含服务名称和实际端口
                    response = f"{service_name}:{port}"
                    sock.sendto(response.encode(), addr)
                    print(f"Responded to discovery request from {addr}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Discovery error: {e}")
                continue

    @staticmethod
    def discover_services(timeout=5):
        """
        发现局域网内的服务
        :param timeout: 超时时间(秒)
        :return: 发现的服务器列表 [(service_name, ip, port), ...]
        """
        # 创建UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        
        # 发送发现请求
        message = "DISCOVER"
        sock.sendto(message.encode(), ('255.255.255.255', 44444))
        print("Sent discovery request")
        
        servers = []
        start_time = time.time()
        
        # 等待响应
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                response = data.decode()
                if ':' in response:
                    service_name, port = response.split(':')
                    servers.append((service_name, addr[0], int(port)))
                    print(f"Discovered service: {service_name} at {addr[0]}:{port}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Discovery error: {e}")
                continue
        
        return servers