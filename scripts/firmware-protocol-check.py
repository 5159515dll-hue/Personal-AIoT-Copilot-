#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "services" / "api"))

from app.ingestion import parse_mqtt_payload  # noqa: E402


REQUIRED_METRICS = {"temperature", "humidity", "co2", "light", "presence", "noise"}
REQUIRED_CONFIG_MACROS = {
    "AIOT_I2C_SDA_PIN",
    "AIOT_I2C_SCL_PIN",
    "AIOT_USE_SHT31",
    "AIOT_SHT31_ADDRESS",
    "AIOT_USE_BH1750",
    "AIOT_BH1750_ADDRESS",
    "AIOT_USE_SCD4X",
    "AIOT_SCD4X_ADDRESS",
    "AIOT_PRESENCE_PIN",
    "AIOT_USE_ANALOG_CO2",
    "AIOT_USE_ANALOG_LIGHT",
    "AIOT_USE_ANALOG_NOISE",
    "AIOT_ALLOW_DEMO_FALLBACK",
}


class FirmwareCheckFailure(AssertionError):
    pass


def main() -> int:
    failures: list[str] = []
    checks = [
        ("固件读取真实传感器且不默认伪造读数", check_firmware_source),
        ("配置模板显式声明传感器和后备开关", check_config_template),
        ("设备协议示例可被入站解析器接受", check_payload_example),
        ("文档说明真实固件和安全边界", check_docs),
        ("真实密钥配置文件被 Git 忽略", check_gitignore),
    ]

    for label, check in checks:
        try:
            check()
            print(f"通过：{label}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}：{exc}")
            print(f"失败：{label}：{exc}", file=sys.stderr)

    if failures:
        print(f"ESP32 固件协议检查失败：{len(failures)} 项未通过。", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"ESP32 固件协议检查完成：{len(checks)} 项全部通过。")
    return 0


def check_firmware_source() -> None:
    source = read_text("firmware/esp32-room-node/src/main.cpp")
    required_tokens = [
        "AIOT_USE_SHT31",
        "AIOT_USE_BH1750",
        "AIOT_USE_SCD4X",
        "AIOT_ALLOW_DEMO_FALLBACK",
        "readCrcWord",
        "skip metric=%s reason=sensor_unavailable",
        "0x2400",
        "0x21B1",
        "0xEC05",
    ]
    for token in required_tokens:
        assert_true(token in source, f"固件缺少 {token}")

    forbidden_patterns = [
        r"float\s+readTemperatureC\s*\(\)\s*\{[^}]*return\s+25\.0f\s*;",
        r"float\s+readHumidityPct\s*\(\)\s*\{[^}]*return\s+48\.0f\s*;",
    ]
    for pattern in forbidden_patterns:
        assert_true(re.search(pattern, source, flags=re.S) is None, "固件仍存在直接返回固定环境值的占位读取函数")


def check_config_template() -> None:
    config = read_text("firmware/esp32-room-node/include/config.example.h")
    for macro in REQUIRED_CONFIG_MACROS:
        assert_true(f"#define {macro}" in config, f"配置模板缺少 {macro}")
    assert_true("#define AIOT_USE_SHT31 1" in config, "配置模板应默认展示 SHT31 真实读取")
    assert_true("#define AIOT_USE_BH1750 1" in config, "配置模板应默认展示 BH1750 真实读取")
    assert_true("#define AIOT_USE_SCD4X 1" in config, "配置模板应默认展示 SCD4x 真实读取")
    assert_true("#define AIOT_ALLOW_DEMO_FALLBACK 0" in config, "演示后备值必须默认关闭")


def check_payload_example() -> None:
    example = ROOT_DIR / "services/mqtt-ingestor/examples/room-node-message.json"
    payload = example.read_text(encoding="utf-8")
    request = parse_mqtt_payload(payload)
    metrics = {reading.metric.value for reading in request.readings}
    assert_equal(request.device_id, "room_node_01", "示例 device_id 不正确")
    assert_equal(metrics, REQUIRED_METRICS, "示例 payload 指标不完整")

    raw = json.loads(payload)
    assert_true(isinstance(raw.get("readings"), list), "示例 payload 必须使用 batch readings")
    assert_true(all("metric" in item and "value" in item for item in raw["readings"]), "示例 reading 必须包含 metric/value")


def check_docs() -> None:
    firmware_readme = read_text("firmware/esp32-room-node/README.md")
    protocol_doc = read_text("docs/device-protocol.md")
    architecture_doc = read_text("docs/architecture.md")
    combined = "\n".join([firmware_readme, protocol_doc, architecture_doc])

    for token in ("SHT31", "BH1750", "SCD40", "SCD41", "AIOT_ALLOW_DEMO_FALLBACK", "不会伪造成正常读数"):
        assert_true(token in combined, f"文档缺少真实固件边界说明：{token}")
    for stale_phrase in ("占位读取", "固件骨架", "当前版本不接入真实 ESP32"):
        assert_true(stale_phrase not in combined, f"文档仍包含过期描述：{stale_phrase}")


def check_gitignore() -> None:
    gitignore = read_text(".gitignore")
    assert_true("firmware/esp32-room-node/include/config.h" in gitignore, "真实固件密钥配置 config.h 必须被 Git 忽略")


def read_text(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise FirmwareCheckFailure(message)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise FirmwareCheckFailure(f"{message}：expected={expected!r} actual={actual!r}")


if __name__ == "__main__":
    sys.exit(main())
