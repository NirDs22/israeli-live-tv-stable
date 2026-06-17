from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


ADDON_ID = "plugin.video.israeli.live.tv.stable"
ADDON_NAME = "Israeli Live TV Stable"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return repo_root() / "resources" / "data"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def ensure_file(path: Path, default_data: Any) -> bool:
    if path.exists():
        return False
    write_json(path, default_data)
    return True


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> Optional[float]:
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def getenv_path(name: str) -> Optional[Path]:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else None
