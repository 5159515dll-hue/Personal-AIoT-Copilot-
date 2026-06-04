from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from app.mock_data import get_device_catalog
from app.models import Device
from app.storage import data_dir


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
    devices = get_device_catalog()
    states = device_state_store.list_states()
    for device in devices:
        saved_state = states.get(device.id)
        if saved_state:
            device.current_state = {**device.current_state, **saved_state}
    return devices


def get_mock_device(device_id: str) -> Device | None:
    return next((device for device in list_mock_devices() if device.id == device_id), None)


def execute_mock_control(device: Device, state: Literal["on", "off"]) -> Device:
    updated = device.model_copy(deep=True)
    updated.current_state["power"] = state
    device_state_store.save_state(updated.id, updated.current_state)
    return updated
