# JW8507 / JW8103A 综合控制平台

基于 `PyQt5` 的双设备桌面控制程序，合并了以下两个项目：

- `JW8507` 多通道程控光衰减器
- `JW8103A / JW8102A` 光功率计

程序启动后提供统一主窗口，使用两个 Tab 分别控制衰减器和功率计。

## 功能概览

- `JW8507`：
  - 串口连接与设备校验
  - 多通道波长、衰减值、关闭/复位控制
  - TCP 远程控制接口
  - 操作日志落盘
- `JW8103A`：
  - FTDI 串口连接
  - 4 通道功率实时显示
  - 曲线绘图与 PNG 导出
  - CSV 记录到 `Record/`
  - TCP 服务端 / 客户端
  - 局域网服务发现
  - 自动化控制接口

## 安装

```bash
pip install -r requirements.txt
```

依赖：

- `PyQt5`
- `pyserial`
- `pandas`
- `pyqtgraph`
- `numpy`
- `bitstring`

## 启动

```bash
python main.py
```

主窗口包含两个页面：

- `光衰减器 JW8507`
- `光功率计 JW8103A`

## 配置

统一配置文件为根目录下的 `config.json`。

主要字段：

```json
{
  "channel_count": 2,
  "default_baudrate": 115200,
  "serial_timeout": 0.1,
  "serial_port": "",
  "refresh_interval_ms": 500,
  "power_meter_port": "COM1",
  "tcp_server_port": 1234,
  "automation_server_address": "127.0.0.1",
  "automation_server_port": 10005,
  "tcp_client_address": "127.0.0.1",
  "tcp_client_port": 1234,
  "server_address": "127.0.0.1",
  "server_port": 10006,
  "log_retention_days": 30
}
```

字段说明：

- `serial_*` 和 `channel_count`：`JW8507` 使用
- `power_meter_port`：功率计本地串口
- `tcp_server_port`：功率计本地 TCP 服务端口
- `automation_server_*`：功率计自动化接口
- `tcp_client_*`：功率计作为客户端连接其他主机时使用
- `server_*`：`JW8507` TCP 服务地址与端口

## 目录结构

```text
JW8507/
├─ main.py
├─ config.json
├─ requirements.txt
├─ devices/
│  ├─ JW8507.py
│  └─ JW8103A.py
├─ ui/
│  ├─ MainWindow.py
│  ├─ ChannelWidget.py
│  ├─ JW8103A_Control.py
│  ├─ Ui_JW8103A_Control.py
│  └─ MyPlot.py
├─ network/
│  ├─ TCPServer.py
│  ├─ TCPClient.py
│  └─ LAN_Search.py
├─ utils/
│  ├─ config.py
│  ├─ logger.py
│  └─ LatencyTimerSet.py
├─ docs/
├─ logs/
└─ Record/
```

## TCP 说明

- `JW8507` 继续使用 JSON 命令控制，默认端口 `10006`
- `JW8103A` 本地数据服务默认端口 `1234`
- `JW8103A` 自动化接口默认端口 `10005`
- 统一的 `network/TCPServer.py` 同时兼容：
  - `JW8507` 旧的 `[bool, value, error]` 返回格式
  - `JW8103A` 原有 JSON 字符串返回格式

## 记录与日志

- 运行日志写入 `logs/JW8507.log`
- 功率计记录文件写入 `Record/`

## 协议文档

- [JW8507A 8通道衰减器 通信协议 V22.10.28.pdf](docs/JW8507A%208通道衰减器%20通信协议%20V22.10.28.pdf)
- [嘉慧功率计JW8102A_JW8103A 用户通信协议V23.05.06.pdf](docs/%E5%98%89%E6%85%A7%E5%8A%9F%E7%8E%87%E8%AE%A1JW8102A_JW8103A%20%E7%94%A8%E6%88%B7%E9%80%9A%E4%BF%A1%E5%8D%8F%E8%AE%AEV23.05.06.pdf)

## 许可证

`MPL-2.0`
