from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"

DEFAULT_CHANNEL_ROLES = {str(index): "output" for index in range(1, 9)}
DEFAULT_CHANNEL_ROLES["2"] = "input"

DEFAULT_CHANNEL_TARGETS = {str(index): -25.0 for index in range(1, 9)}
DEFAULT_CHANNEL_TARGETS["2"] = -47.0

DEFAULT_CHANNEL_MIN_ATT = {str(index): 0.0 for index in range(1, 9)}

DEFAULT_CHANNEL_PM_MAPPING = {str(index): None for index in range(1, 9)}
DEFAULT_CHANNEL_PM_MAPPING["1"] = 0
DEFAULT_CHANNEL_PM_MAPPING["2"] = 1

DEFAULT_CONFIG = {
    "_comment": "===== JW8507 衰减器配置 =====",
    "channel_count": 2,
    "default_baudrate": 115200,
    "serial_timeout": 0.1,
    "serial_port": "",
    "refresh_interval_ms": 500,
    "_comment_channel_config": "===== 通道公式配置 =====",
    "channel_roles": DEFAULT_CHANNEL_ROLES,
    "channel_targets": DEFAULT_CHANNEL_TARGETS,
    "channel_min_att": DEFAULT_CHANNEL_MIN_ATT,
    "channel_pm_mapping": DEFAULT_CHANNEL_PM_MAPPING,
    "formula_interval_ms": 1000,
    "_comment2": "===== JW8103A 功率计配置 =====",
    "power_meter_port": "COM1",
    "tcp_server_port": 1234,
    "automation_server_address": "127.0.0.1",
    "automation_server_port": 10005,
    "tcp_client_address": "127.0.0.1",
    "tcp_client_port": 1234,
    "_comment3": "===== 通用配置 =====",
    "server_address": "127.0.0.1",
    "server_port": 10006,
    "log_retention_days": 30,
}

_SECTION_KEY_MAP = {
    ("Port", "name"): "power_meter_port",
    ("TCP", "address"): "tcp_client_address",
    ("TCP", "port"): "tcp_client_port",
    ("Auto", "address"): "automation_server_address",
    ("Auto", "port"): "automation_server_port",
}


def _merge_defaults(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    if config:
        for key, value in config.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value
    return merged


def save_app_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = _merge_defaults(config)
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(merged, file, ensure_ascii=False, indent=4)
    return merged


def load_app_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    merged = _merge_defaults(data)
    if merged != data:
        save_app_config(merged)
    return merged


def ensure_config_defaults() -> dict[str, Any]:
    return load_app_config()


def read_config() -> dict[str, dict[str, str]]:
    config = load_app_config()
    return {
        "Port": {
            "name": str(config.get("power_meter_port", DEFAULT_CONFIG["power_meter_port"])),
        },
        "TCP": {
            "address": str(config.get("tcp_client_address", DEFAULT_CONFIG["tcp_client_address"])),
            "port": str(config.get("tcp_client_port", DEFAULT_CONFIG["tcp_client_port"])),
        },
        "Auto": {
            "address": str(
                config.get(
                    "automation_server_address",
                    DEFAULT_CONFIG["automation_server_address"],
                )
            ),
            "port": str(config.get("automation_server_port", DEFAULT_CONFIG["automation_server_port"])),
        },
    }


def edit_config(section: str, key: str, value: Any) -> bool:
    config = load_app_config()
    config_key = _SECTION_KEY_MAP.get((section, key))
    if config_key is None:
        return False

    if config_key.endswith("_port") and value not in (None, ""):
        try:
            config[config_key] = int(value)
        except (TypeError, ValueError):
            config[config_key] = value
    else:
        config[config_key] = value

    save_app_config(config)
    return True


def get_device_config(device_type: str) -> dict[str, Any]:
    config = load_app_config()
    if device_type.lower() in {"jw8507", "attenuator"}:
        keys = (
            "channel_count",
            "default_baudrate",
            "serial_timeout",
            "serial_port",
            "refresh_interval_ms",
            "channel_roles",
            "channel_targets",
            "channel_min_att",
            "channel_pm_mapping",
            "formula_interval_ms",
            "server_address",
            "server_port",
            "log_retention_days",
        )
    elif device_type.lower() in {"jw8103a", "power_meter"}:
        keys = (
            "power_meter_port",
            "tcp_server_port",
            "automation_server_address",
            "automation_server_port",
            "tcp_client_address",
            "tcp_client_port",
            "log_retention_days",
        )
    else:
        return config

    return {key: config[key] for key in keys if key in config}
