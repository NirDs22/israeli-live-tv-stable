from __future__ import annotations

from .cache import CacheStore
from .config import default_paths, ensure_user_files
from .logging_utils import kodi_log
from .m3u import generate_m3u
from .playlist_server import PlaylistServer
from .registry import load_registry
from .remote_config import update_remote_channels
from .resolver import SourceResolver
from .settings import get_settings


def run() -> None:
    settings = get_settings()
    paths = default_paths(settings)
    ensure_user_files(paths)
    cache = CacheStore(paths.cache)
    result = update_remote_channels(paths, settings, cache, force=False)
    kodi_log(result.message)

    def refresh_playlist() -> None:
        registry = load_registry(paths, settings)
        resolver = SourceResolver(settings, cache, validate_network=False)
        count = generate_m3u(registry.channels, resolver, paths.generated_m3u)
        kodi_log(f"Generated M3U with {count} entries: {paths.generated_m3u}")

    if settings.generate_m3u_on_startup or settings.playlist_server_enabled:
        refresh_playlist()

    server = None
    if settings.playlist_server_enabled:
        try:
            server = PlaylistServer(paths.generated_m3u, port=settings.playlist_server_port, refresh=refresh_playlist)
            server.start()
            kodi_log(f"Local playlist server started at {server.url}")
        except Exception as exc:
            kodi_log(f"Local playlist server could not start: {exc}")

    if server:
        try:
            import xbmc  # type: ignore

            monitor = xbmc.Monitor()
            while not monitor.abortRequested():
                if monitor.waitForAbort(10):
                    break
        except Exception:
            return
        finally:
            server.stop()


if __name__ == "__main__":
    run()
