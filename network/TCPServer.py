#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import socket
import threading

from PyQt5.QtCore import QThread, pyqtSignal


class TCPServer(QThread):
    cmd_send_signal = pyqtSignal(str, str)
    ready_signal = pyqtSignal(bool, str)

    def __init__(self, addr=None, port=8888, func=lambda data: data, address=None):
        super().__init__()
        self.host = address or addr or socket.gethostbyname(socket.gethostname())
        self.port = int(port)
        self.func = func
        self.server_socket = None
        self.client_threads = {}
        self.client_sockets = []
        self._lock = threading.Lock()
        self._is_running = False

    def _format_response(self, data):
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False)
        if isinstance(data, (list, tuple)) and len(data) >= 3 and isinstance(data[0], bool):
            return json.dumps(
                {
                    "IsSuccessful": data[0],
                    "Value": data[1],
                    "ErrorMessage": data[2],
                },
                ensure_ascii=False,
            )
        if isinstance(data, (list, tuple)):
            return json.dumps(data, ensure_ascii=False)
        return str(data)

    def handle_client_connection(self, client_socket, addr):
        buffer = b""
        try:
            while self._is_running:
                try:
                    client_socket.settimeout(1)
                    data = client_socket.recv(1024)
                    if not data:
                        break

                    buffer += data
                    if b"\n" not in buffer:
                        continue

                    messages = buffer.split(b"\n")
                    for message in messages[:-1]:
                        text = message.decode("utf-8").strip()
                        if not text:
                            continue
                        response = self.func(text)
                        self.send(client_socket, response)
                    buffer = messages[-1]
                except socket.timeout:
                    continue
                except OSError:
                    break
                except Exception as exc:
                    self.send(
                        client_socket,
                        {
                            "IsSuccessful": False,
                            "Value": "",
                            "ErrorMessage": str(exc),
                        },
                    )
                    break
        finally:
            if buffer:
                try:
                    text = buffer.decode("utf-8").strip()
                    if text:
                        self.send(client_socket, self.func(text))
                except Exception:
                    pass
            self.cleanup_client(client_socket, addr)

    def cleanup_client(self, client_socket, addr):
        with self._lock:
            if client_socket in self.client_sockets:
                self.client_sockets.remove(client_socket)
            self.client_threads.pop(addr, None)

        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client_socket.close()
        except OSError:
            pass

    def run(self):
        self._is_running = True
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("", self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)
        except OSError as exc:
            self.ready_signal.emit(False, f"端口 {self.port} 启动失败: {exc}")
            self.cleanup_server()
            return

        self.ready_signal.emit(True, f"服务器正在 {self.host}:{self.port} 上监听")

        try:
            while self._is_running:
                try:
                    client_socket, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with self._lock:
                    self.client_sockets.append(client_socket)

                client_thread = threading.Thread(
                    target=self.handle_client_connection,
                    args=(client_socket, addr),
                    daemon=True,
                )
                with self._lock:
                    self.client_threads[addr] = client_thread
                client_thread.start()
        finally:
            self.cleanup_server()

    def cleanup_server(self):
        with self._lock:
            sockets = list(self.client_sockets)
            self.client_sockets.clear()
            self.client_threads.clear()

        for client_socket in sockets:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client_socket.close()
            except OSError:
                pass

        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

    def close_tcp_server(self):
        self._is_running = False
        if self.server_socket is None:
            return
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_socket.settimeout(1)
            temp_socket.connect((self.host, self.port))
            temp_socket.close()
        except OSError:
            pass

    def send(self, client_socket, data):
        payload = self._format_response(data) + "\n"
        try:
            client_socket.sendall(payload.encode("utf-8"))
        except OSError:
            pass
