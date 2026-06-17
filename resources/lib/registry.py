from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .config import RuntimePaths, load_user_config
from .models import Channel, Source, SourceType, ValidationReport, channel_from_dict
from .settings import AddonSettings
from .utils import read_json


@dataclass
class RegistryResult:
    channels: List[Channel]
    validation: ValidationReport
    user_source_count: int = 0

    def by_id(self) -> Dict[str, Channel]:
        return {channel.id: channel for channel in self.channels}

    def get(self, channel_id: str) -> Optional[Channel]:
        return self.by_id().get(channel_id)


def load_bundled_channels(paths: RuntimePaths) -> tuple[List[Channel], ValidationReport]:
    report = ValidationReport()
    channels: List[Channel] = []
    try:
        data = read_json(paths.bundled_channels)
        raw_channels = data.get("channels") if isinstance(data, dict) else None
        if not isinstance(raw_channels, list):
            raise ValueError("channels.json must contain a list named channels")
        for index, raw_channel in enumerate(raw_channels):
            try:
                channels.append(channel_from_dict(raw_channel))
            except Exception as exc:
                report.errors.append(f"channels.json item {index}: {exc}")
    except Exception as exc:
        report.errors.append(f"failed to load bundled channels: {exc}")
    return channels, report


def _replace_tvheadend_placeholder(channel: Channel, source: Source) -> None:
    replaced = False
    for index, existing in enumerate(channel.sources):
        if existing.type == SourceType.LOCAL_TVHEADEND:
            channel.sources[index] = source
            replaced = True
            break
    if not replaced:
        channel.sources.append(source)


def load_registry(paths: RuntimePaths, settings: AddonSettings) -> RegistryResult:
    channels, report = load_bundled_channels(paths)
    user_config = load_user_config(paths, settings)
    report.extend(user_config.validation)
    by_id = {channel.id: channel for channel in channels}

    for channel_id, sources in user_config.user_sources.items():
        channel = by_id.get(channel_id)
        if not channel:
            report.warnings.append(f"user_sources.json references unknown channel: {channel_id}")
            continue
        channel.sources.extend(sources)

    for channel_id, source in user_config.tvheadend_sources.items():
        channel = by_id.get(channel_id)
        if not channel:
            report.warnings.append(f"tvheadend_mapping.json references unknown channel: {channel_id}")
            continue
        _replace_tvheadend_placeholder(channel, source)

    filtered = channels if settings.show_disabled_channels else [channel for channel in channels if channel.enabled]
    return RegistryResult(filtered, report, user_config.user_source_count)


def channel_status(channel: Channel, cache_state: dict) -> str:
    if not channel.enabled:
        return "Unavailable"
    last_health = cache_state.get("last_health_status")
    if last_health == "failed":
        return "Failed"
    if last_health == "last_worked":
        return "Last worked"
    if any(source.playable for source in channel.sources):
        return "Available"
    if any(source.type == SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY for source in channel.sources):
        return "Unavailable"
    return "Unchecked"


def iter_playable_sources(channels: Iterable[Channel]) -> Iterable[tuple[Channel, Source]]:
    for channel in channels:
        for source in channel.sources:
            if source.playable:
                yield channel, source
