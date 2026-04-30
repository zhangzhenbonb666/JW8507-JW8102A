import serial.tools.list_ports as list_ports
import winreg

def get_port_ID(port_name):
    """
    获取端口的硬件ID
    :param port_name: 端口名
    :return: 硬件ID
    """
    ports = list_ports.comports()
    for p in ports:
        if p.device == port_name:
            return p.hwid
    return None

    # ports = list_ports.comports()
    # for p in ports:
    #     print(f"端口: {p.device}, 硬件ID: {p.hwid}")

def SetLatencyTimer(port_name, latency_timer):
    """
    设置端口的延迟时间
    :param port_name: 端口名
    :param latency_timer: 延迟时间
    :return: None
    """
    key_path = r"SYSTEM\CurrentControlSet\Control\COM Name Arbiter\Devices"
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
    ID = winreg.QueryValueEx(key, port_name)[0].split("#")[1]
    key_path = f"SYSTEM\\CurrentControlSet\\Enum\\FTDIBUS\\{ID}\\0000\\Device Parameters"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE)

        winreg.SetValueEx(key, "LatencyTimer", 0, winreg.REG_DWORD, latency_timer)
        winreg.CloseKey(key)
        print(f"设置{port_name}的延迟时间为{latency_timer}ms")
    except WindowsError as e:
        print(f"设置{port_name}的延迟时间失败: {e}")

def check_is_FTDI_port(port_name):
    """
    检查端口是否是FTDI端口
    :param port_name: 端口名
    :return: bool
    """
    key_path = r"SYSTEM\CurrentControlSet\Control\COM Name Arbiter\Devices"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        if "ftdibus" in winreg.QueryValueEx(key, port_name)[0]:
            winreg.CloseKey(key)
            return True
        else:
            winreg.CloseKey(key)
            return False
    except WindowsError:
        return False
        

if __name__ == '__main__':
    print(check_is_FTDI_port("COM46"))
    SetLatencyTimer("COM46", 1)
