from __future__ import annotations

from .cache import CacheStore
from .config import default_paths, ensure_user_files
from .logging_utils import kodi_log
from .m3u import generate_m3u
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
    if settings.generate_m3u_on_startup:
        registry = load_registry(paths, settings)
        resolver = SourceResolver(settings, cache, validate_network=False)
        count = generate_m3u(registry.channels, resolver, paths.generated_m3u)
        kodi_log(f"Generated startup M3U with {count} entries: {paths.generated_m3u}")


if __name__ == "__main__":
    run()
