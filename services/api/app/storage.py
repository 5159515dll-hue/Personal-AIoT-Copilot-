from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def data_dir() -> Path:
    configured = os.getenv("AIOT_DATA_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / ".local"


class JsonListStore(Generic[T]):
    def __init__(self, filename: str, model: type[T]) -> None:
        self.path = data_dir() / filename
        self.model = model
        self.lock = Lock()

    def list(self) -> list[T]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return [self.model.model_validate(item) for item in payload]

    def append(self, item: T) -> T:
        with self.lock:
            items = self.list()
            items.append(item)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(
                    [entry.model_dump(mode="json") for entry in items],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            self.path.chmod(0o600)
        return item

    def replace_all(self, items: list[T]) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(
                    [entry.model_dump(mode="json") for entry in items],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            self.path.chmod(0o600)
