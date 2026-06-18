from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import ADDON_ID, getenv_path, repo_root


@dataclass
class AddonSettings:
    debug_logging: bool = False
    preferred_source_mode: str = "auto"
    network_timeout_seconds: int = 4
    health_check_ttl_minutes: int = 10
    show_disabled_channels: bool = False
    show_setup_kodi_tv: bool = True
    tvheadend_enabled: bool = False
    tvheadend_base_url: str = ""
    tvheadend_username: str = ""
    tvheadend_password: str = ""
    prefer_tvheadend: bool = False
    tvheadend_mapping_path: str = ""
    generate_m3u_on_startup: bool = False
    playlist_server_enabled: bool = True
    playlist_server_port: int = 41555
    remote_config_enabled: bool = True
    remote_config_url: str = "https://raw.githubusercontent.com/NirDs22/israeli-live-tv-stable/main/resources/data/channels.json"
    remote_config_ttl_hours: int = 12

    @property
    def health_ttl_seconds(self) -> int:
        return max(1, self.health_check_ttl_minutes) * 60

    @property
    def remote_config_ttl_seconds(self) -> int:
        return max(1, self.remote_config_ttl_hours) * 60 * 60


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def userdata_path() -> Path:
    env_path = getenv_path("ISRAELI_LIVE_TV_STABLE_USERDATA")
    if env_path:
        return env_path
    try:
        import xbmc  # type: ignore
        import xbmcvfs  # type: ignore

        translated = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}")
        return Path(translated)
    except Exception:
        return repo_root().parent / ".kodi_userdata" / ADDON_ID


def get_settings() -> AddonSettings:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=ADDON_ID)
        return AddonSettings(
            debug_logging=_bool(addon.getSetting("debug_logging")),
            preferred_source_mode=addon.getSetting("preferred_source_mode") or "auto",
            network_timeout_seconds=_int(addon.getSetting("network_timeout_seconds"), 4),
            health_check_ttl_minutes=_int(addon.getSetting("health_check_ttl_minutes"), 10),
            show_disabled_channels=_bool(addon.getSetting("show_disabled_channels")),
            show_setup_kodi_tv=_bool(addon.getSetting("show_setup_kodi_tv") or "true"),
            tvheadend_enabled=_bool(addon.getSetting("tvheadend_enabled")),
            tvheadend_base_url=addon.getSetting("tvheadend_base_url") or "",
            tvheadend_username=addon.getSetting("tvheadend_username") or "",
            tvheadend_password=addon.getSetting("tvheadend_password") or "",
            prefer_tvheadend=_bool(addon.getSetting("prefer_tvheadend")),
            tvheadend_mapping_path=addon.getSetting("tvheadend_mapping_path") or "",
            generate_m3u_on_startup=_bool(addon.getSetting("generate_m3u_on_startup")),
            playlist_server_enabled=_bool(addon.getSetting("playlist_server_enabled") or "true"),
            playlist_server_port=_int(addon.getSetting("playlist_server_port"), 41555),
            remote_config_enabled=_bool(addon.getSetting("remote_config_enabled") or "true"),
            remote_config_url=addon.getSetting("remote_config_url")
            or "https://raw.githubusercontent.com/NirDs22/israeli-live-tv-stable/main/resources/data/channels.json",
            remote_config_ttl_hours=_int(addon.getSetting("remote_config_ttl_hours"), 12),
        )
    except Exception:
        return AddonSettings()
