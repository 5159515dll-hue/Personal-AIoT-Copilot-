from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from app.models import DeviceCredentialPublic, DeviceCredentialRecord
from app.storage import JsonListStore
from app.time_utils import now

DEVICE_TOKEN_HEADER = "x-aiot-device-token"

credential_store = JsonListStore("device_credentials.json", DeviceCredentialRecord)


def issue_device_token(device_id: str) -> tuple[DeviceCredentialRecord, str]:
    token = f"aiot_{device_id}_{secrets.token_urlsafe(32)}"
    timestamp = now()
    record = DeviceCredentialRecord(
        device_id=device_id,
        token_hash=_token_hash(device_id, token),
        token_preview=_preview_token(token),
        issued_at=timestamp,
        expires_at=None,
        last_used_at=None,
    )
    records = [item for item in credential_store.list() if item.device_id != device_id]
    records.append(record)
    credential_store.replace_all(records)
    return record, token


def list_device_credentials() -> list[DeviceCredentialPublic]:
    return [_public_record(item) for item in credential_store.list()]


def get_device_credential(device_id: str) -> DeviceCredentialPublic | None:
    record = _find_record(device_id)
    return _public_record(record) if record else None


def verify_device_token(device_id: str, token: str | None) -> bool:
    if not token:
        return False
    record = _find_record(device_id)
    if record is None:
        return False
    expected = _token_hash(device_id, token)
    if not hmac.compare_digest(record.token_hash, expected):
        return False
    updated = record.model_copy(update={"last_used_at": now()})
    credential_store.replace_all([updated if item.device_id == device_id else item for item in credential_store.list()])
    return True


def _find_record(device_id: str) -> DeviceCredentialRecord | None:
    return next((item for item in credential_store.list() if item.device_id == device_id), None)


def _public_record(record: DeviceCredentialRecord) -> DeviceCredentialPublic:
    return DeviceCredentialPublic(
        device_id=record.device_id,
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        token_preview=record.token_preview,
    )


def _token_hash(device_id: str, token: str) -> str:
    secret = os.getenv("AIOT_DEVICE_TOKEN_SECRET", "").strip() or "personal-aiot-copilot-device-token"
    payload = f"{device_id}:{token}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _preview_token(token: str) -> str:
    return f"{token[:10]}...{token[-6:]}"
