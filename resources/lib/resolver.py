from __future__ import annotations

from typing import Iterable, List, Union

from .cache import CacheStore
from .healthcheck import check_source
from .models import (
    FailureCategory,
    FailureResult,
    PLAYABLE_SOURCE_TYPES,
    PlayableResult,
    Source,
    SourceType,
    Channel,
)
from .settings import AddonSettings


ResolutionResult = Union[PlayableResult, FailureResult]


def _friendly_unavailable(channel: Channel) -> str:
    if channel.id == "keshet12":
        return (
            "Direct playback is not bundled for this channel because no verified stable legal direct source is configured. "
            "You can add a legal user source in user_sources.json or configure a local TVHeadend source."
        )
    return (
        f"{channel.name} does not have a configured playable source. Add a legal user source in user_sources.json "
        "or configure a local TVHeadend mapping."
    )


class SourceResolver:
    def __init__(
        self,
        settings: AddonSettings,
        cache: CacheStore,
        *,
        validate_network: bool = False,
        inputstream_adaptive_available: bool = True,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.validate_network = validate_network
        self.inputstream_adaptive_available = inputstream_adaptive_available

    def resolve(self, channel: Channel, *, skip_source_id: str = "") -> ResolutionResult:
        ordered = self._ordered_sources(channel)
        failures: List[str] = []
        for source in ordered:
            if skip_source_id and source.id == skip_source_id:
                continue
            failure = self._source_preflight(channel, source)
            if failure:
                failures.append(f"{source.id}: {failure.category.value}")
                self.cache.set_source_failure(source.id, failure.category.value)
                continue
            if self.validate_network:
                ok, status = check_source(source, timeout=max(1, self.settings.network_timeout_seconds))
                if not ok:
                    failures.append(f"{source.id}: {status}")
                    self.cache.set_source_failure(source.id, status)
                    continue
            result = PlayableResult(
                channel=channel,
                source=source,
                url=source.url,
                headers=source.headers,
                mime_type=source.mime_type or self._default_mime(source.type),
                inputstream_type=source.inputstream_type,
                requires_inputstream_adaptive=source.requires_inputstream_adaptive,
            )
            self.cache.set_last_success(channel.id, source.id, source.type.value)
            return result

        info_source = next((source for source in channel.sources if source.type == SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY), None)
        if info_source:
            return FailureResult(
                channel=channel,
                source=info_source,
                category=FailureCategory.SOURCE_INFO_ONLY,
                user_message=_friendly_unavailable(channel),
                technical_details=f"Official page: {info_source.url}. Tried: {', '.join(failures) or 'no playable sources'}",
            )
        return FailureResult(
            channel=channel,
            category=FailureCategory.SOURCE_NOT_CONFIGURED,
            user_message=_friendly_unavailable(channel),
            technical_details=", ".join(failures) or "No enabled playable source exists.",
        )

    def _source_preflight(self, channel: Channel, source: Source) -> FailureResult | None:
        if not source.enabled:
            return FailureResult(channel, FailureCategory.SOURCE_DISABLED, "This source is disabled.", source=source)
        if source.type == SourceType.DISABLED:
            return FailureResult(channel, FailureCategory.SOURCE_DISABLED, "This source is disabled.", source=source)
        if source.type == SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY:
            return FailureResult(channel, FailureCategory.SOURCE_INFO_ONLY, _friendly_unavailable(channel), source=source)
        if source.type not in PLAYABLE_SOURCE_TYPES:
            return FailureResult(channel, FailureCategory.UNKNOWN_ERROR, "Unsupported source type.", source=source)
        if not source.url:
            message = "Local TVHeadend is not configured. Add a mapping in tvheadend_mapping.json or disable TVHeadend preference."
            return FailureResult(channel, FailureCategory.SOURCE_NOT_CONFIGURED, message, source=source)
        unhealthy = self.cache.unhealthy_until_ttl(source.id, self.settings.health_ttl_seconds)
        if unhealthy:
            try:
                category = FailureCategory(unhealthy)
            except ValueError:
                category = FailureCategory.UNKNOWN_ERROR
            return FailureResult(channel, category, "This source is temporarily marked unhealthy.", source=source)
        if source.requires_inputstream_adaptive and not self.inputstream_adaptive_available:
            return FailureResult(
                channel,
                FailureCategory.INPUTSTREAM_MISSING,
                "This stream requires inputstream.adaptive. Install and enable inputstream.adaptive in Kodi, then try again.",
                source=source,
            )
        return None

    def _ordered_sources(self, channel: Channel) -> List[Source]:
        last_id = self.cache.last_known_source_id(channel.id)

        def bucket(source: Source) -> tuple[int, int, str]:
            if last_id and source.id == last_id:
                return (0, source.priority, source.id)
            if source.type == SourceType.LOCAL_TVHEADEND and self._prefer_tvheadend():
                return (1, source.priority, source.id)
            if source.is_user_configured and source.type in {SourceType.DIRECT_HLS, SourceType.DIRECT_DASH}:
                return (2, source.priority, source.id)
            if source.is_user_configured and source.type == SourceType.LOCAL_M3U:
                return (3, source.priority, source.id)
            if source.type == SourceType.LOCAL_TVHEADEND:
                return (4, source.priority, source.id)
            if source.type in {SourceType.DIRECT_HLS, SourceType.DIRECT_DASH}:
                return (5, source.priority, source.id)
            if source.type == SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY:
                return (6, source.priority, source.id)
            return (7, source.priority, source.id)

        return sorted(channel.sources, key=bucket)

    def _prefer_tvheadend(self) -> bool:
        return self.settings.prefer_tvheadend or self.settings.preferred_source_mode == "prefer_tvheadend"

    def _default_mime(self, source_type: SourceType) -> str:
        if source_type in {SourceType.DIRECT_HLS, SourceType.LOCAL_M3U, SourceType.LOCAL_TVHEADEND}:
            return "application/vnd.apple.mpegurl"
        if source_type == SourceType.DIRECT_DASH:
            return "application/dash+xml"
        return ""


def is_playable_result(result: ResolutionResult) -> bool:
    return isinstance(result, PlayableResult)
