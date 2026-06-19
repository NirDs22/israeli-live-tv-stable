from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from typing import Dict, List

from .cache import CacheStore
from .config import RuntimePaths
from .models import Channel
from .playlist_server import playlist_server_status, playlist_url
from .settings import AddonSettings


@dataclass
class DiagnosticsReport:
    lines: List[str]

    def as_text(self) -> str:
        return "\n".join(self.lines)


def _addon_version() -> str:
    try:
        import xbmcaddon  # type: ignore

        return xbmcaddon.Addon().getAddonInfo("version")
    except Exception:
        return "0.1.0"


def _kodi_version() -> str:
    try:
        import xbmc  # type: ignore

        return xbmc.getInfoLabel("System.BuildVersion") or "unknown"
    except Exception:
        return "outside Kodi"


def addon_enabled(addon_id: str) -> str:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=addon_id)
        version = addon.getAddonInfo("version")
        return f"installed ({version})"
    except Exception:
        return "not detected"


def inputstream_adaptive_available() -> bool:
    return addon_enabled("inputstream.adaptive").startswith("installed")


def build_diagnostics(
    paths: RuntimePaths,
    settings: AddonSettings,
    channels: List[Channel],
    validation_errors: List[str],
    cache: CacheStore,
    user_source_count: int,
) -> DiagnosticsReport:
    data = cache.load()
    cache_summary = cache.summary()
    lines = [
        "Israeli Live TV Stable Diagnostics",
        f"Kodi version: {_kodi_version()}",
        f"Python version: {sys.version.split()[0]}",
        f"Platform: {platform.platform()}",
        f"Addon version: {_addon_version()}",
        f"Addon userdata path: {paths.userdata}",
        f"user_sources.json path: {paths.user_sources}",
        f"tvheadend_mapping.json path: {paths.tvheadend_mapping}",
        f"remote_channels.json path: {paths.remote_channels}",
        f"Generated M3U path: {paths.generated_m3u}",
        f"Local playlist URL: {playlist_url(settings.playlist_server_port)}",
        f"Local playlist server: {playlist_server_status(settings.playlist_server_port)[1] if settings.playlist_server_enabled else 'disabled'}",
        f"inputstream.adaptive: {addon_enabled('inputstream.adaptive')}",
        f"IPTV Simple Client: {addon_enabled('pvr.iptvsimple')}",
        f"Channels loaded: {len(channels)}",
        f"User sources loaded: {user_source_count}",
        f"Cache status: {cache_summary['channels']} channel entries, {cache_summary['sources']} source entries",
        f"Preferred source mode: {settings.preferred_source_mode}",
        f"TVHeadend enabled: {settings.tvheadend_enabled}",
        f"Prefer TVHeadend: {settings.prefer_tvheadend}",
        f"Remote channel updates enabled: {settings.remote_config_enabled}",
        f"Remote channel URL: {settings.remote_config_url}",
    ]
    metadata = data.get("metadata", {})
    lines.append(f"Remote channel status: {metadata.get('remote_channels_status', '-')}")
    lines.append(f"Remote channel last checked: {metadata.get('remote_channels_checked_at', '-')}")
    lines.append(f"Remote channel message: {metadata.get('remote_channels_message', '-')}")
    lines.append(f"IPTV Simple setup mode: {metadata.get('pvr_setup_mode', 'unknown')}")
    lines.append(f"IPTV Simple setup status: {metadata.get('pvr_setup_message', '-')}")
    lines.append(f"Generated M3U exists: {'yes' if paths.generated_m3u.exists() else 'no'}")
    if validation_errors:
        lines.append("Config validation errors:")
        lines.extend(f"- {error}" for error in validation_errors)
    else:
        lines.append("Config validation errors: none")

    lines.append("Last known channel state:")
    channel_state: Dict[str, dict] = data.get("channels", {})
    if not channel_state:
        lines.append("- none")
    else:
        for channel_id, state in sorted(channel_state.items()):
            source = state.get("last_successful_source_id", "")
            failure = state.get("last_failure_reason", "")
            health = state.get("last_health_status", "")
            lines.append(f"- {channel_id}: source={source or '-'} health={health or '-'} failure={failure or '-'}")

    lines.append("Per-source failure categories:")
    source_state: Dict[str, dict] = data.get("sources", {})
    if not source_state:
        lines.append("- none")
    else:
        for source_id, state in sorted(source_state.items()):
            lines.append(f"- {source_id}: {state.get('last_failure_category') or state.get('last_health_status') or '-'}")
    return DiagnosticsReport(lines)
