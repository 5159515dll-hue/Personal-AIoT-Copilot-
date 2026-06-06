from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from app.database import (
    database_url,
    get_device_registry_db,
    list_device_registry_db,
    update_device_registry_state_db,
)
from app.mock_data import get_device_catalog
from app.models import Device
from app.storage import data_dir

DeviceSource = Literal["auto", "mock", "database"]


class DeviceRegistryUnavailable(RuntimeError):
    pass


class MockDeviceStateStore:
    def __init__(self, filename: str = "device_states.json") -> None:
        self.path = data_dir() / filename
        self.lock = Lock()

    def list_states(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            return {}
        return {
            str(device_id): state
            for device_id, state in payload.items()
            if isinstance(state, dict)
        }

    def save_state(self, device_id: str, state: dict[str, Any]) -> None:
        with self.lock:
            states = self.list_states()
            states[device_id] = state
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(states, file, ensure_ascii=False, indent=2)
            self.path.chmod(0o600)

    def reset(self) -> None:
        with self.lock:
            if self.path.exists():
                self.path.unlink()


device_state_store = MockDeviceStateStore()


def list_mock_devices() -> list[Device]:
    return _overlay_saved_states(get_device_catalog())


def get_mock_device(device_id: str) -> Device | None:
    return next((device for device in list_mock_devices() if device.id == device_id), None)


def list_devices(source: DeviceSource = "auto") -> list[Device]:
    if source in {"auto", "database"}:
        if not database_url():
            if source == "database":
                raise DeviceRegistryUnavailable("未配置 DATABASE_URL，无法访问设备注册表。")
        else:
            try:
                devices = list_device_registry_db(seed_devices=get_device_catalog())
                return _overlay_saved_states(devices)
            except RuntimeError as exc:
                if source == "database":
                    raise DeviceRegistryUnavailable(_clean_registry_error(exc)) from exc
            except Exception as exc:
                if source == "database":
                    raise DeviceRegistryUnavailable("设备注册表数据库连接或查询失败，请检查 DATABASE_URL 和数据库服务状态。") from exc
    return list_mock_devices()


def get_device(device_id: str, source: DeviceSource = "auto") -> Device | None:
    if source in {"auto", "database"}:
        if not database_url():
            if source == "database":
                raise DeviceRegistryUnavailable("未配置 DATABASE_URL，无法访问设备注册表。")
        else:
            try:
                device = get_device_registry_db(device_id, seed_devices=get_device_catalog())
                if device is None:
                    return None
                return _overlay_saved_states([device])[0]
            except RuntimeError as exc:
                if source == "database":
                    raise DeviceRegistryUnavailable(_clean_registry_error(exc)) from exc
            except Exception as exc:
                if source == "database":
                    raise DeviceRegistryUnavailable("设备注册表数据库连接或查询失败，请检查 DATABASE_URL 和数据库服务状态。") from exc
    return get_mock_device(device_id)


def execute_device_control(device: Device, state: Literal["on", "off"], source: DeviceSource = "auto") -> Device:
    updated = execute_mock_control(device, state)
    if source in {"auto", "database"} and database_url():
        try:
            registry_device = update_device_registry_state_db(updated.id, updated.current_state)
            if registry_device is not None:
                return registry_device
        except Exception:
            pass
    return updated


def execute_mock_control(device: Device, state: Literal["on", "off"]) -> Device:
    updated = device.model_copy(deep=True)
    updated.current_state["power"] = state
    device_state_store.save_state(updated.id, updated.current_state)
    return updated


def _overlay_saved_states(devices: list[Device]) -> list[Device]:
    result = [device.model_copy(deep=True) for device in devices]
    states = device_state_store.list_states()
    for device in result:
        saved_state = states.get(device.id)
        if saved_state:
            device.current_state = {**device.current_state, **saved_state}
    return result


def _clean_registry_error(exc: Exception) -> str:
    return str(exc).strip().rstrip("。.") + "。"
