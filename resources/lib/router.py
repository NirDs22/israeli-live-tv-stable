from __future__ import annotations

import sys
from typing import Dict, List
from urllib.parse import parse_qsl, urlencode

from .cache import CacheStore
from .config import RuntimePaths, default_paths, ensure_user_files
from .diagnostics import build_diagnostics, inputstream_adaptive_available
from .healthcheck import check_source
from .m3u import generate_m3u
from .models import FailureCategory, FailureResult, PlayableResult
from .playback import fail_to_kodi, resolve_to_kodi, show_failure_dialog
from .playlist_server import playlist_server_status, playlist_url
from .pvr import setup_kodi_tv
from .registry import channel_status, load_registry
from .remote_config import update_remote_channels
from .resolver import SourceResolver
from .settings import AddonSettings, get_settings
from .utils import ADDON_NAME


def parse_params(argv: List[str]) -> Dict[str, str]:
    if len(argv) < 3:
        return {}
    return dict(parse_qsl(argv[2][1:]))


class Router:
    def __init__(self, argv: List[str] | None = None) -> None:
        self.argv = argv or sys.argv
        self.base_url = self.argv[0] if self.argv else ""
        self.handle = int(self.argv[1]) if len(self.argv) > 1 and str(self.argv[1]).isdigit() else -1
        self.settings = get_settings()
        self.paths = default_paths(self.settings)
        ensure_user_files(self.paths)
        self.cache = CacheStore(self.paths.cache)
        self.registry = load_registry(self.paths, self.settings)

    def dispatch(self) -> None:
        params = parse_params(self.argv)
        action = params.get("action", "root")
        if action == "live_channels":
            self.live_channels()
        elif action == "play":
            self.play(params.get("channel_id", ""), params.get("skip_source_id", ""))
        elif action == "diagnostics":
            self.diagnostics()
        elif action == "clear_cache":
            self.clear_cache()
        elif action == "generate_m3u":
            self.generate_m3u()
        elif action == "setup_kodi_tv":
            self.setup_kodi_tv()
        elif action == "restart_playlist_server":
            self.restart_playlist_server()
        elif action == "health_check":
            self.health_check(params.get("channel_id", ""))
        elif action == "update_channels":
            self.update_channels()
        elif action == "source_details":
            self.source_details(params.get("channel_id", ""))
        elif action == "user_source_instructions":
            self.user_source_instructions()
        elif action == "about":
            self.about()
        elif action == "settings":
            self.open_settings()
        else:
            self.root()

    def url(self, **params: str) -> str:
        return f"{self.base_url}?{urlencode(params)}"

    def root(self) -> None:
        self._add_directory("Live Channels", self.url(action="live_channels"))
        if self.settings.show_setup_kodi_tv:
            self._add_directory("Setup / Repair Kodi TV", self.url(action="setup_kodi_tv"))
        self._add_directory("Diagnostics", self.url(action="diagnostics"))
        self._add_directory("Settings", self.url(action="settings"))
        self._add_directory("About", self.url(action="about"))
        self._end_directory()

    def live_channels(self) -> None:
        for channel in self.registry.channels:
            state = self.cache.channel_state(channel.id)
            label = f"{channel.name} [{channel_status(channel, state)}]"
            context = [
                ("Play", f"RunPlugin({self.url(action='play', channel_id=channel.id)})"),
                ("Try next source", f"RunPlugin({self.url(action='play', channel_id=channel.id, skip_source_id=state.get('last_successful_source_id', ''))})"),
                ("Run health check", f"RunPlugin({self.url(action='health_check', channel_id=channel.id)})"),
                ("Show source details", f"RunPlugin({self.url(action='source_details', channel_id=channel.id)})"),
                ("Clear source cache", f"RunPlugin({self.url(action='clear_cache')})"),
                ("Show user source instructions", f"RunPlugin({self.url(action='user_source_instructions')})"),
            ]
            self._add_playable(label, self.url(action="play", channel_id=channel.id), context)
        self._end_directory()

    def play(self, channel_id: str, skip_source_id: str = "") -> None:
        channel = self.registry.get(channel_id)
        if not channel:
            failure = FailureResult(None, category=FailureCategory.UNKNOWN_ERROR, user_message="Channel was not found.", technical_details=channel_id)
            fail_to_kodi(self.handle, failure)
            return
        resolver = SourceResolver(
            self.settings,
            self.cache,
            validate_network=False,
            inputstream_adaptive_available=inputstream_adaptive_available(),
        )
        result = resolver.resolve(channel, skip_source_id=skip_source_id)
        if isinstance(result, PlayableResult):
            resolve_to_kodi(self.handle, result)
        else:
            self.cache.set_channel_failure(channel.id, result.category.value)
            fail_to_kodi(self.handle, result)

    def diagnostics(self) -> None:
        report = build_diagnostics(
            self.paths,
            self.settings,
            self.registry.channels,
            self.registry.validation.errors,
            self.cache,
            self.registry.user_source_count,
        )
        self._show_text("Diagnostics", report.as_text())
        self._add_directory("Run health check now", self.url(action="health_check"))
        self._add_directory("Clear cache", self.url(action="clear_cache"))
        self._add_directory("Regenerate M3U", self.url(action="generate_m3u"))
        self._add_directory("Restart playlist server", self.url(action="restart_playlist_server"))
        self._add_directory("Setup / Repair Kodi TV", self.url(action="setup_kodi_tv"))
        self._add_directory("Update channel list now", self.url(action="update_channels"))
        self._add_directory("Show user source file path", self.url(action="user_source_instructions"))
        self._end_directory()

    def clear_cache(self) -> None:
        self.cache.clear()
        self._notify("Cache cleared")

    def generate_m3u(self) -> None:
        resolver = SourceResolver(self.settings, self.cache, validate_network=False)
        count = generate_m3u(self.registry.channels, resolver, self.paths.generated_m3u)
        self._notify(f"Generated M3U with {count} entries")

    def setup_kodi_tv(self) -> None:
        resolver = SourceResolver(self.settings, self.cache, validate_network=False)
        count = generate_m3u(self.registry.channels, resolver, self.paths.generated_m3u)
        local_url = ""
        if self.settings.playlist_server_enabled:
            server_ok, server_status = playlist_server_status(self.settings.playlist_server_port)
            if server_ok:
                local_url = playlist_url(self.settings.playlist_server_port)
        result = setup_kodi_tv(self.paths.generated_m3u, count, local_url)
        self.cache.set_pvr_setup_status(
            result.setup_mode,
            result.message,
            instance_settings_path=result.instance_settings_path,
            backup_path=result.backup_path,
            playlist_entry_count=result.playlist_entry_count,
        )
        if result.ok:
            self._show_text("Kodi TV Repair", result.message + "\n\n" + result.technical_details)
        else:
            self._show_text(
                "Kodi TV Repair",
                result.message + "\n\n" + result.technical_details + "\n\n" + result.manual_instructions,
            )

    def restart_playlist_server(self) -> None:
        try:
            import xbmc  # type: ignore

            xbmc.executebuiltin("StopScript(resources/lib/service.py)")
            xbmc.executebuiltin("RunScript(resources/lib/service.py)")
        except Exception:
            pass
        ok, status = playlist_server_status(self.settings.playlist_server_port)
        if ok:
            self._notify("Playlist server is running")
        else:
            self._show_text(
                "Playlist server",
                "Playlist server was requested. If it is still not running, restart Kodi.\n\n"
                f"Status: {status}\n"
                f"URL: {playlist_url(self.settings.playlist_server_port)}",
            )

    def health_check(self, channel_id: str = "") -> None:
        channels = [self.registry.get(channel_id)] if channel_id else self.registry.channels
        checked = 0
        for channel in [item for item in channels if item]:
            for source in channel.sources:
                if not source.playable:
                    continue
                ok, status = check_source(source, timeout=5)
                checked += 1
                if ok:
                    self.cache.set_source_health(source.id, "ok")
                else:
                    self.cache.set_source_failure(source.id, status)
                    self.cache.set_channel_failure(channel.id, status)
        self._notify(f"Health check completed ({checked} sources)")

    def update_channels(self) -> None:
        result = update_remote_channels(self.paths, self.settings, self.cache, force=True)
        if result.validation.errors:
            self._show_text("Channel update", result.message + "\n\n" + "\n".join(result.validation.errors))
        else:
            self._notify("Channel list updated" if result.updated else result.message)

    def source_details(self, channel_id: str) -> None:
        channel = self.registry.get(channel_id)
        if not channel:
            self._notify("Channel not found")
            return
        lines = [f"{channel.name} sources:"]
        for source in channel.sources:
            lines.append(f"- {source.id}: {source.type.value}, enabled={source.enabled}, priority={source.priority}, url={'yes' if source.url else 'no'}")
            if source.notes:
                lines.append(f"  {source.notes}")
        self._show_text("Source details", "\n".join(lines))

    def user_source_instructions(self) -> None:
        text = (
            f"User sources path:\n{self.paths.user_sources}\n\n"
            f"TVHeadend mapping path:\n{self.paths.tvheadend_mapping}\n\n"
            "Add only legal sources you are allowed to use. Bad JSON is ignored and shown in Diagnostics."
        )
        self._show_text("User source instructions", text)

    def about(self) -> None:
        self._show_text(
            "About",
            "Israeli Live TV Stable is a live-TV-only Kodi addon. It does not include VOD, scraping, piracy links, DRM bypass, or protected API access.",
        )

    def open_settings(self) -> None:
        try:
            import xbmcaddon  # type: ignore

            xbmcaddon.Addon().openSettings()
        except Exception:
            self._notify("Settings are available inside Kodi.")

    def _add_directory(self, label: str, url: str) -> None:
        import xbmcgui  # type: ignore
        import xbmcplugin  # type: ignore

        item = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(self.handle, url, item, True)

    def _add_playable(self, label: str, url: str, context: List[tuple[str, str]]) -> None:
        import xbmcgui  # type: ignore
        import xbmcplugin  # type: ignore

        item = xbmcgui.ListItem(label=label)
        item.setProperty("IsPlayable", "true")
        item.addContextMenuItems(context)
        xbmcplugin.addDirectoryItem(self.handle, url, item, False)

    def _end_directory(self) -> None:
        import xbmcplugin  # type: ignore

        xbmcplugin.endOfDirectory(self.handle)

    def _show_text(self, title: str, text: str) -> None:
        try:
            import xbmcgui  # type: ignore

            xbmcgui.Dialog().textviewer(title, text)
        except Exception:
            print(f"{title}\n{text}")

    def _notify(self, message: str) -> None:
        try:
            import xbmcgui  # type: ignore

            xbmcgui.Dialog().notification(ADDON_NAME, message)
        except Exception:
            print(message)
