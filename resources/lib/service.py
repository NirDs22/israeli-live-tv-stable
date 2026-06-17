from __future__ import annotations

from .cache import CacheStore
from .config import default_paths, ensure_user_files
from .logging_utils import kodi_log
from .remote_config import update_remote_channels
from .settings import get_settings


def run() -> None:
    settings = get_settings()
    paths = default_paths(settings)
    ensure_user_files(paths)
    cache = CacheStore(paths.cache)
    result = update_remote_channels(paths, settings, cache, force=False)
    kodi_log(result.message)


if __name__ == "__main__":
    run()
