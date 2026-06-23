from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .utils import now_iso, read_json, write_json


@dataclass
class CacheStore:
    path: Path

    def _empty(self) -> Dict[str, Any]:
        return {"channels": {}, "sources": {}, "metadata": {}}

    def load(self) -> Dict[str, Any]:
        try:
            data = read_json(self.path)
            if not isinstance(data, dict):
                return self._empty()
            data.setdefault("channels", {})
            data.setdefault("sources", {})
            data.setdefault("metadata", {})
            return data
        except Exception:
            return self._empty()

    def save(self, data: Dict[str, Any]) -> None:
        write_json(self.path, data)

    def clear(self) -> None:
        self.save(self._empty())

    def channel_state(self, channel_id: str) -> Dict[str, Any]:
        return self.load().setdefault("channels", {}).get(channel_id, {})

    def source_state(self, source_id: str) -> Dict[str, Any]:
        return self.load().setdefault("sources", {}).get(source_id, {})

    def set_last_success(self, channel_id: str, source_id: str, source_type: str) -> None:
        data = self.load()
        data.setdefault("channels", {}).setdefault(channel_id, {}).update(
            {
                "last_successful_source_id": source_id,
                "last_successful_source_type": source_type,
                "last_successful_playback_at": now_iso(),
                "last_failure_reason": "",
                "last_health_status": "last_worked",
            }
        )
        self.save(data)

    def set_channel_failure(self, channel_id: str, reason: str) -> None:
        data = self.load()
        data.setdefault("channels", {}).setdefault(channel_id, {}).update(
            {"last_failure_reason": reason, "last_health_status": "failed"}
        )
        self.save(data)

    def set_source_failure(self, source_id: str, category: str) -> None:
        data = self.load()
        data.setdefault("sources", {}).setdefault(source_id, {}).update(
            {"last_checked_at_epoch": time.time(), "last_checked_at": now_iso(), "last_failure_category": category}
        )
        self.save(data)

    def set_source_health(self, source_id: str, status: str) -> None:
        data = self.load()
        data.setdefault("sources", {}).setdefault(source_id, {}).update(
            {"last_checked_at_epoch": time.time(), "last_checked_at": now_iso(), "last_health_status": status}
        )
        self.save(data)

    def set_pvr_setup_status(
        self,
        mode: str,
        message: str,
        *,
        instance_settings_path: str = "",
        backup_path: str = "",
        playlist_entry_count: int = 0,
    ) -> None:
        data = self.load()
        data.setdefault("metadata", {}).update(
            {
                "pvr_setup_mode": mode,
                "pvr_setup_message": message,
                "pvr_setup_checked_at": now_iso(),
                "pvr_instance_settings_path": instance_settings_path,
                "pvr_instance_settings_backup_path": backup_path,
                "pvr_playlist_entry_count": playlist_entry_count,
            }
        )
        self.save(data)

    def set_channel12_success(self, source_id: str, source_type: str = "") -> None:
        data = self.load()
        data.setdefault("metadata", {}).update(
            {
                "channel12_last_successful_source": source_id,
                "channel12_last_successful_source_type": source_type,
                "channel12_last_successful_at": now_iso(),
                "channel12_last_failure_reason": "",
            }
        )
        self.save(data)

    def set_channel12_failure(self, reason: str, details: str = "") -> None:
        data = self.load()
        data.setdefault("metadata", {}).update(
            {
                "channel12_last_failure_reason": reason,
                "channel12_last_failure_at": now_iso(),
                "channel12_last_failure_details": details,
            }
        )
        self.save(data)

    def channel12_state(self) -> Dict[str, Any]:
        metadata = self.load().setdefault("metadata", {})
        return {
            "channel12_last_successful_source": metadata.get("channel12_last_successful_source", ""),
            "channel12_last_successful_source_type": metadata.get("channel12_last_successful_source_type", ""),
            "channel12_last_successful_at": metadata.get("channel12_last_successful_at", ""),
            "channel12_last_failure_reason": metadata.get("channel12_last_failure_reason", ""),
            "channel12_last_failure_at": metadata.get("channel12_last_failure_at", ""),
            "channel12_last_failure_details": metadata.get("channel12_last_failure_details", ""),
        }

    def clear_channel12(self) -> None:
        data = self.load()
        metadata = data.setdefault("metadata", {})
        for key in [
            "channel12_last_successful_source",
            "channel12_last_successful_source_type",
            "channel12_last_successful_at",
            "channel12_last_failure_reason",
            "channel12_last_failure_at",
            "channel12_last_failure_details",
        ]:
            metadata.pop(key, None)
        channels = data.setdefault("channels", {})
        channels.pop("keshet12", None)
        self.save(data)

    def unhealthy_until_ttl(self, source_id: str, ttl_seconds: int) -> Optional[str]:
        state = self.source_state(source_id)
        category = state.get("last_failure_category")
        checked = float(state.get("last_checked_at_epoch") or 0)
        if category and checked and time.time() - checked < ttl_seconds:
            return str(category)
        return None

    def last_known_source_id(self, channel_id: str) -> str:
        return str(self.channel_state(channel_id).get("last_successful_source_id", "") or "")

    def summary(self) -> Dict[str, int]:
        data = self.load()
        return {
            "channels": len(data.get("channels", {})),
            "sources": len(data.get("sources", {})),
        }
