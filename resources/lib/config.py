from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .models import Source, SourceType, ValidationReport, source_from_dict
from .settings import AddonSettings, userdata_path
from .utils import data_dir, ensure_file, read_json


@dataclass
class RuntimePaths:
    userdata: Path
    bundled_channels: Path
    remote_channels: Path
    user_sources: Path
    tvheadend_mapping: Path
    cache: Path
    generated_m3u: Path


@dataclass
class LoadedUserConfig:
    user_sources: Dict[str, List[Source]]
    tvheadend_sources: Dict[str, Source]
    validation: ValidationReport
    user_source_count: int = 0


def default_paths(settings: AddonSettings | None = None) -> RuntimePaths:
    base = userdata_path()
    mapping_path = Path(settings.tvheadend_mapping_path).expanduser() if settings and settings.tvheadend_mapping_path else base / "tvheadend_mapping.json"
    return RuntimePaths(
        userdata=base,
        bundled_channels=data_dir() / "channels.json",
        remote_channels=base / "remote_channels.json",
        user_sources=base / "user_sources.json",
        tvheadend_mapping=mapping_path,
        cache=base / "cache.json",
        generated_m3u=base / "israeli-live-tv-stable.m3u",
    )


def ensure_user_files(paths: RuntimePaths) -> None:
    paths.userdata.mkdir(parents=True, exist_ok=True)
    ensure_file(paths.user_sources, {"channels": {}})
    ensure_file(paths.tvheadend_mapping, {"channels": {}})
    ensure_file(paths.cache, {"channels": {}, "sources": {}, "metadata": {}})


def load_user_config(paths: RuntimePaths, settings: AddonSettings) -> LoadedUserConfig:
    ensure_user_files(paths)
    report = ValidationReport()
    user_sources: Dict[str, List[Source]] = {}
    tvh_sources: Dict[str, Source] = {}

    try:
        raw_user = read_json(paths.user_sources)
        if not isinstance(raw_user, dict) or not isinstance(raw_user.get("channels", {}), dict):
            raise ValueError("user_sources.json must contain an object named channels")
        for channel_id, raw_sources in raw_user.get("channels", {}).items():
            if not isinstance(raw_sources, list):
                report.errors.append(f"user_sources.json: {channel_id} must be a list of sources")
                continue
            parsed: List[Source] = []
            for item in raw_sources:
                try:
                    parsed.append(source_from_dict(item, user_configured=True))
                except Exception as exc:
                    report.errors.append(f"user_sources.json: {channel_id}: {exc}")
            if parsed:
                user_sources[str(channel_id)] = parsed
    except Exception as exc:
        report.errors.append(f"user_sources.json is invalid: {exc}")

    try:
        raw_tvh = read_json(paths.tvheadend_mapping)
        if not isinstance(raw_tvh, dict) or not isinstance(raw_tvh.get("channels", {}), dict):
            raise ValueError("tvheadend_mapping.json must contain an object named channels")
        for channel_id, raw_mapping in raw_tvh.get("channels", {}).items():
            if not isinstance(raw_mapping, dict):
                report.errors.append(f"tvheadend_mapping.json: {channel_id} must be an object")
                continue
            enabled = bool(raw_mapping.get("enabled", True))
            url = str(raw_mapping.get("url", "") or "")
            source = Source(
                id=f"{channel_id}_local_tvheadend",
                type=SourceType.LOCAL_TVHEADEND,
                priority=int(raw_mapping.get("priority", 5)),
                enabled=enabled and settings.tvheadend_enabled,
                url=url,
                headers={},
                mime_type="application/vnd.apple.mpegurl",
                is_user_configured=True,
                notes="User-owned local TVHeadend mapping.",
            )
            if enabled and url:
                tvh_sources[str(channel_id)] = source
    except Exception as exc:
        report.errors.append(f"tvheadend_mapping.json is invalid: {exc}")

    return LoadedUserConfig(
        user_sources=user_sources,
        tvheadend_sources=tvh_sources,
        validation=report,
        user_source_count=sum(len(items) for items in user_sources.values()),
    )
