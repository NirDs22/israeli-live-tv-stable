from __future__ import annotations

from pathlib import Path
from typing import List
from urllib.parse import urlencode

from .cache import CacheStore
from .models import Channel, PlayableResult, Source, SourceType
from .resolver import SourceResolver
from .utils import ADDON_ID, resolve_addon_asset


def _escape(value: str) -> str:
    return value.replace('"', "'")


def _select_source(channel: Channel, resolver: SourceResolver) -> Source | None:
    result = resolver.resolve(channel)
    if isinstance(result, PlayableResult):
        return result.source
    return None


def _channel_playback_url(channel: Channel, resolver: SourceResolver) -> str:
    if channel.id == "keshet12":
        query = urlencode({"action": "play", "channel_id": channel.id})
        return f"plugin://{ADDON_ID}/?{query}"
    source = _select_source(channel, resolver)
    if not source:
        return ""
    if source.type in {SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY, SourceType.DISABLED}:
        return ""
    return source.url


def generate_m3u(channels: List[Channel], resolver: SourceResolver, output_path: Path) -> int:
    lines = ["#EXTM3U"]
    count = 0
    for channel in channels:
        if not channel.enabled:
            continue
        playback_url = _channel_playback_url(channel, resolver)
        if not playback_url:
            continue
        attrs = (
            f'tvg-id="{_escape(channel.tvg_id or channel.id)}" '
            f'tvg-name="{_escape(channel.name)}" '
            f'tvg-logo="{_escape(resolve_addon_asset(channel.logo))}" '
            f'group-title="{_escape(channel.category)}"'
        )
        lines.append(f"#EXTINF:-1 {attrs},{channel.name}")
        lines.append(playback_url)
        count += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count
