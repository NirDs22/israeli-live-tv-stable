from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceType(str, Enum):
    DIRECT_HLS = "DIRECT_HLS"
    DIRECT_DASH = "DIRECT_DASH"
    LOCAL_M3U = "LOCAL_M3U"
    LOCAL_TVHEADEND = "LOCAL_TVHEADEND"
    OFFICIAL_WEB_PAGE_INFO_ONLY = "OFFICIAL_WEB_PAGE_INFO_ONLY"
    DISABLED = "DISABLED"


PLAYABLE_SOURCE_TYPES = {
    SourceType.DIRECT_HLS,
    SourceType.DIRECT_DASH,
    SourceType.LOCAL_M3U,
    SourceType.LOCAL_TVHEADEND,
}


class FailureCategory(str, Enum):
    NETWORK_TIMEOUT = "network_timeout"
    DNS_ERROR = "dns_error"
    HTTP_403 = "http_403"
    HTTP_404 = "http_404"
    HTTP_5XX = "http_5xx"
    MANIFEST_INVALID = "manifest_invalid"
    STREAM_SEGMENTS_UNAVAILABLE = "stream_segments_unavailable"
    INPUTSTREAM_MISSING = "inputstream_missing"
    UNSUPPORTED_DRM = "unsupported_drm"
    SOURCE_DISABLED = "source_disabled"
    SOURCE_NOT_CONFIGURED = "source_not_configured"
    SOURCE_INFO_ONLY = "source_info_only"
    INVALID_USER_CONFIG = "invalid_user_config"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class Source:
    id: str
    type: SourceType
    priority: int = 100
    enabled: bool = True
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    mime_type: str = ""
    inputstream_type: str = ""
    requires_inputstream_adaptive: bool = False
    is_user_configured: bool = False
    evidence_url: str = ""
    last_verified_at: str = ""
    notes: str = ""

    @property
    def playable(self) -> bool:
        return self.enabled and self.type in PLAYABLE_SOURCE_TYPES and bool(self.url)


@dataclass
class Channel:
    id: str
    name: str
    description: str = ""
    category: str = "Israel"
    logo: str = ""
    tvg_id: str = ""
    enabled: bool = True
    sources: List[Source] = field(default_factory=list)


@dataclass
class PlayableResult:
    channel: Channel
    source: Source
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    mime_type: str = ""
    inputstream_type: str = ""
    requires_inputstream_adaptive: bool = False


@dataclass
class FailureResult:
    channel: Optional[Channel]
    category: FailureCategory
    user_message: str
    technical_details: str = ""
    source: Optional[Source] = None


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def source_from_dict(data: Dict[str, Any], *, user_configured: bool = False) -> Source:
    if not isinstance(data, dict):
        raise ValueError("source entry must be an object")
    source_id = str(data.get("id", "")).strip()
    if not source_id:
        raise ValueError("source id is required")
    raw_type = str(data.get("type", "")).strip()
    try:
        source_type = SourceType(raw_type)
    except ValueError as exc:
        raise ValueError(f"unsupported source type: {raw_type}") from exc
    headers = data.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError(f"headers for {source_id} must be an object")
    return Source(
        id=source_id,
        type=source_type,
        priority=int(data.get("priority", 100)),
        enabled=bool(data.get("enabled", True)),
        url=str(data.get("url", "") or ""),
        headers={str(k): str(v) for k, v in headers.items()},
        mime_type=str(data.get("mime_type", "") or ""),
        inputstream_type=str(data.get("inputstream_type", "") or ""),
        requires_inputstream_adaptive=bool(data.get("requires_inputstream_adaptive", False)),
        is_user_configured=bool(data.get("is_user_configured", user_configured)),
        evidence_url=str(data.get("evidence_url", "") or ""),
        last_verified_at=str(data.get("last_verified_at", "") or ""),
        notes=str(data.get("notes", "") or ""),
    )


def channel_from_dict(data: Dict[str, Any]) -> Channel:
    if not isinstance(data, dict):
        raise ValueError("channel entry must be an object")
    channel_id = str(data.get("id", "")).strip()
    if not channel_id:
        raise ValueError("channel id is required")
    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError(f"sources for {channel_id} must be a list")
    sources = [source_from_dict(item) for item in raw_sources]
    return Channel(
        id=channel_id,
        name=str(data.get("name", channel_id)),
        description=str(data.get("description", "") or ""),
        category=str(data.get("category", "Israel") or "Israel"),
        logo=str(data.get("logo", "") or ""),
        tvg_id=str(data.get("tvg_id", channel_id) or channel_id),
        enabled=bool(data.get("enabled", True)),
        sources=sources,
    )
