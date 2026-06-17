from __future__ import annotations

from .router import Router


def main() -> None:
    Router().dispatch()
