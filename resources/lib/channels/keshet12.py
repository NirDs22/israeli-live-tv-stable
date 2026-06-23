from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List, Tuple

from ..cache import CacheStore
from ..config import RuntimePaths
from ..logging_utils import kodi_log
from ..models import Channel, FailureCategory, FailureResult, PlayableResult, Source, SourceType, source_from_dict
from ..resolver import SourceResolver
from ..settings import AddonSettings
from ..utils import read_json, write_json


OVERRIDE_FILENAME = "channel12_override.json"
LOG_PREFIX = "[Keshet12]"


def channel12_override_path(paths: RuntimePaths) -> Path:
    return paths.userdata / OVERRIDE_FILENAME


def load_channel12_override(paths: RuntimePaths) -> Tuple[Source | None, List[str], bool]:
    path = channel12_override_path(paths)
    if not path.exists():
        return None, [], False
    try:
        raw = read_json(path)
        if not isinstance(raw, dict):
            return None, ["channel12_override.json must contain a JSON object"], True
        if not bool(raw.get("enabled", True)):
            return None, [], True
        payload = dict(raw)
        payload.setdefault("id", "keshet12_user_override")
        payload.setdefault("type", SourceType.DIRECT_HLS.value)
        payload.setdefault("priority", 1)
        payload.setdefault("headers", {})
        payload.setdefault("mime_type", "application/vnd.apple.mpegurl")
        payload["is_user_configured"] = True
        source = source_from_dict(payload, user_configured=True)
        if source.type not in {SourceType.DIRECT_HLS, SourceType.DIRECT_DASH, SourceType.LOCAL_M3U, SourceType.LOCAL_TVHEADEND}:
            return None, [f"channel12_override.json source type is not playable: {source.type.value}"], True
        if not source.url:
            return None, ["channel12_override.json enabled override is missing url"], True
        return replace(source, id="keshet12_user_override"), [], True
    except Exception as exc:
        return None, [f"channel12_override.json is invalid: {exc}"], True


def disable_channel12_override(paths: RuntimePaths) -> None:
    path = channel12_override_path(paths)
    try:
        raw = read_json(path) if path.exists() else {}
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}
    raw["enabled"] = False
    write_json(path, raw)


def channel12_failure_message() -> str:
    return (
        "Channel 12 did not resolve to a playable source. Other channels are unaffected. "
        "You can add a legal Channel 12 override in channel12_override.json or configure a local TVHeadend mapping."
    )


def _map_failure(category: FailureCategory) -> FailureCategory:
    mapping = {
        FailureCategory.NETWORK_TIMEOUT: FailureCategory.KESHET12_TIMEOUT,
        FailureCategory.HTTP_403: FailureCategory.KESHET12_FORBIDDEN,
        FailureCategory.HTTP_404: FailureCategory.KESHET12_NOT_FOUND,
        FailureCategory.HTTP_5XX: FailureCategory.KESHET12_HTTP_ERROR,
        FailureCategory.MANIFEST_INVALID: FailureCategory.KESHET12_MANIFEST_INVALID,
        FailureCategory.INPUTSTREAM_MISSING: FailureCategory.KESHET12_INPUTSTREAM_MISSING,
        FailureCategory.SOURCE_NOT_CONFIGURED: FailureCategory.KESHET12_NO_PLAYABLE_SOURCE,
        FailureCategory.SOURCE_INFO_ONLY: FailureCategory.KESHET12_NO_PLAYABLE_SOURCE,
        FailureCategory.INVALID_USER_CONFIG: FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
    }
    return mapping.get(category, FailureCategory.KESHET12_UNKNOWN_ERROR)


def _clone_channel(channel: Channel, sources: List[Source]) -> Channel:
    return replace(channel, sources=sources)


def _remember(cache: CacheStore, result: PlayableResult | FailureResult) -> None:
    if isinstance(result, PlayableResult):
        cache.set_channel12_success(result.source.id, result.source.type.value)
    else:
        cache.set_channel12_failure(result.category.value, result.technical_details)


def _wrap_failure(result: FailureResult, cache: CacheStore) -> FailureResult:
    category = result.category if str(result.category.value).startswith("keshet12_") else _map_failure(result.category)
    wrapped = FailureResult(
        result.channel,
        category=category,
        user_message=channel12_failure_message(),
        technical_details=result.technical_details,
        source=result.source,
    )
    _remember(cache, wrapped)
    return wrapped


def _run_resolver(
    channel: Channel,
    sources: List[Source],
    settings: AddonSettings,
    cache: CacheStore,
    *,
    validate_network: bool,
    inputstream_adaptive_available: bool,
) -> PlayableResult | FailureResult:
    resolver = SourceResolver(
        settings,
        cache,
        validate_network=validate_network,
        inputstream_adaptive_available=inputstream_adaptive_available,
    )
    return resolver.resolve(_clone_channel(channel, sources))


def resolve_keshet12(
    channel: Channel,
    paths: RuntimePaths,
    settings: AddonSettings,
    cache: CacheStore,
    *,
    validate_network: bool = False,
    inputstream_adaptive_available: bool = True,
    mode: str = "auto",
) -> PlayableResult | FailureResult:
    try:
        kodi_log(f"{LOG_PREFIX} resolving mode={mode}")
        override, override_errors, _ = load_channel12_override(paths)
        if override_errors:
            cache.set_channel12_failure(FailureCategory.KESHET12_BAD_RESPONSE_SHAPE.value, "; ".join(override_errors))

        normal_sources = list(channel.sources)
        tvh_sources = [source for source in normal_sources if source.type == SourceType.LOCAL_TVHEADEND and source.playable]
        override_sources = [override] if override else []

        plans: List[Tuple[str, List[Source]]] = []
        if mode == "override":
            plans.append(("override", override_sources))
        elif mode == "tvheadend":
            plans.append(("tvheadend", tvh_sources))
        elif mode == "normal":
            plans.append(("normal", normal_sources))
        else:
            last_id = cache.channel12_state().get("channel12_last_successful_source", "")
            all_sources = override_sources + normal_sources
            last_sources = [source for source in all_sources if source.id == last_id and source.enabled]
            if last_sources:
                plans.append(("last-known", last_sources))
            plans.extend(
                [
                    ("normal", normal_sources),
                    ("override", override_sources),
                    ("tvheadend", tvh_sources),
                ]
            )

        failures: List[str] = []
        for plan_name, sources in plans:
            if not sources:
                failures.append(f"{plan_name}: no source")
                continue
            try:
                result = _run_resolver(
                    channel,
                    sources,
                    settings,
                    cache,
                    validate_network=validate_network,
                    inputstream_adaptive_available=inputstream_adaptive_available,
                )
            except Exception as exc:
                failures.append(f"{plan_name}: {exc}")
                continue
            if isinstance(result, PlayableResult):
                kodi_log(f"{LOG_PREFIX} resolved source={result.source.id}")
                _remember(cache, result)
                return result
            failures.append(f"{plan_name}: {result.category.value}")

        failure = FailureResult(
            channel,
            category=FailureCategory.KESHET12_NO_PLAYABLE_SOURCE,
            user_message=channel12_failure_message(),
            technical_details="; ".join(failures + override_errors) or "No Channel 12 source could be resolved.",
        )
        _remember(cache, failure)
        return failure
    except Exception as exc:
        failure = FailureResult(
            channel,
            category=FailureCategory.KESHET12_UNKNOWN_ERROR,
            user_message=channel12_failure_message(),
            technical_details=str(exc),
        )
        _remember(cache, failure)
        return failure


def build_channel12_diagnostics(paths: RuntimePaths, channel: Channel | None, cache: CacheStore) -> str:
    override, errors, exists = load_channel12_override(paths)
    state = cache.channel12_state()
    lines = [
        "Channel 12 Diagnostics",
        "Failure isolation: enabled",
        f"Override path: {channel12_override_path(paths)}",
        f"Override file exists: {'yes' if exists else 'no'}",
        f"Override valid/enabled: {'yes' if override else 'no'}",
        f"Last successful source: {state.get('channel12_last_successful_source') or '-'}",
        f"Last successful at: {state.get('channel12_last_successful_at') or '-'}",
        f"Last failure reason: {state.get('channel12_last_failure_reason') or '-'}",
        f"Last failure at: {state.get('channel12_last_failure_at') or '-'}",
        f"Last failure details: {state.get('channel12_last_failure_details') or '-'}",
    ]
    if channel:
        tvh = [source for source in channel.sources if source.type == SourceType.LOCAL_TVHEADEND and source.playable]
        playable = [source for source in channel.sources if source.playable]
        lines.append(f"Bundled/merged playable sources: {len(playable)}")
        lines.append(f"TVHeadend mapping configured: {'yes' if tvh else 'no'}")
    else:
        lines.append("Channel entry: missing")
    if errors:
        lines.append("Override validation errors:")
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)
