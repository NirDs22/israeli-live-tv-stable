from __future__ import annotations

import logging

from .utils import ADDON_NAME


def get_logger(name: str = ADDON_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def kodi_log(message: str, level: int = 1) -> None:
    try:
        import xbmc  # type: ignore

        xbmc.log(f"{ADDON_NAME}: {message}", level)
    except Exception:
        get_logger().info(message)
