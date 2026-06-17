from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .cache import CacheStore
from .config import RuntimePaths
from .models import ValidationReport, channel_from_dict
from .settings import AddonSettings
from .utils import now_iso, read_json, write_json


@dataclass
class RemoteConfigResult:
    updated: bool
    message: str
    validation: ValidationReport


def _validate_channels_payload(data: object) -> ValidationReport:
    report = ValidationReport()
    raw_channels = data.get("channels") if isinstance(data, dict) else None
    if not isinstance(raw_channels, list):
        report.errors.append("remote channels.json must contain a list named channels")
        return report
    for index, raw_channel in enumerate(raw_channels):
        try:
            channel_from_dict(raw_channel)
        except Exception as exc:
            report.errors.append(f"remote channels.json item {index}: {exc}")
    return report


def remote_cache_fresh(cache: CacheStore, ttl_seconds: int) -> bool:
    metadata = cache.load().get("metadata", {})
    checked = float(metadata.get("remote_channels_checked_at_epoch") or 0)
    return bool(checked and time.time() - checked < ttl_seconds)


def mark_remote_check(cache: CacheStore, *, success: bool, message: str) -> None:
    data = cache.load()
    data.setdefault("metadata", {}).update(
        {
            "remote_channels_checked_at_epoch": time.time(),
            "remote_channels_checked_at": now_iso(),
            "remote_channels_status": "ok" if success else "failed",
            "remote_channels_message": message,
        }
    )
    cache.save(data)


def update_remote_channels(paths: RuntimePaths, settings: AddonSettings, cache: CacheStore, *, force: bool = False) -> RemoteConfigResult:
    if not settings.remote_config_enabled:
        return RemoteConfigResult(False, "Remote channel updates are disabled.", ValidationReport())
    if not settings.remote_config_url:
        return RemoteConfigResult(False, "Remote channel URL is empty.", ValidationReport(errors=["remote_config_url is empty"]))
    if not force and remote_cache_fresh(cache, settings.remote_config_ttl_seconds):
        return RemoteConfigResult(False, "Remote channel cache is still fresh.", ValidationReport())

    request = urllib.request.Request(settings.remote_config_url, headers={"User-Agent": "IsraeliLiveTVStable/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=max(4, settings.network_timeout_seconds)) as response:
            raw = response.read(1024 * 512)
    except (urllib.error.URLError, TimeoutError) as exc:
        message = f"Remote channel update failed: {exc}"
        mark_remote_check(cache, success=False, message=message)
        return RemoteConfigResult(False, message, ValidationReport(errors=[message]))

    try:
        import json

        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        message = f"Remote channel JSON is invalid: {exc}"
        mark_remote_check(cache, success=False, message=message)
        return RemoteConfigResult(False, message, ValidationReport(errors=[message]))

    validation = _validate_channels_payload(payload)
    if validation.errors:
        message = "Remote channel JSON failed validation."
        mark_remote_check(cache, success=False, message=message)
        return RemoteConfigResult(False, message, validation)

    write_json(paths.remote_channels, payload)
    message = f"Remote channels updated from {settings.remote_config_url}"
    mark_remote_check(cache, success=True, message=message)
    return RemoteConfigResult(True, message, validation)


def load_remote_channels_if_valid(paths: RuntimePaths) -> tuple[object | None, ValidationReport]:
    if not paths.remote_channels.exists():
        return None, ValidationReport()
    try:
        payload = read_json(paths.remote_channels)
    except Exception as exc:
        return None, ValidationReport(errors=[f"cached remote channels.json is invalid: {exc}"])
    report = _validate_channels_payload(payload)
    if report.errors:
        return None, report
    return payload, report
