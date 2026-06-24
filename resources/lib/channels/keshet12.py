from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Callable, List, Tuple

from ..cache import CacheStore
from ..config import RuntimePaths
from ..logging_utils import kodi_log
from ..models import Channel, FailureCategory, FailureResult, PlayableResult, Source, SourceType, source_from_dict
from ..resolver import SourceResolver
from ..settings import AddonSettings
from ..utils import read_json, write_json


OVERRIDE_FILENAME = "channel12_override.json"
LOG_PREFIX = "[Keshet12]"
ENTITLEMENT_URL = "https://mass.mako.co.il/ClicksStatistics/entitlementsServicesV2.jsp"
STREAM_BASE_URL = "https://mako-streaming.akamaized.net"
OFFICIAL_LIVE_PAGE = "https://www.mako.co.il/news-channel2/Channel-2-Newscast-q3_2019/Article-3bf5c3a8e967f51006.htm"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PUBLIC_WEB_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.mako.co.il/",
    "Origin": "https://www.mako.co.il",
}
ENTITLEMENT_HEADERS = {
    **PUBLIC_WEB_HEADERS,
    "Accept": "application/json, text/plain, */*",
}
KESHET12_RELATIVE_PATHS: Tuple[Tuple[str, str], ...] = (
    ("primary", "/direct/hls/live/2033791/k12/index.m3u8?as=1"),
    ("news_fallback", "/stream/hls/live/2033791/k12n12wad/index.m3u8?b-in-range=0-700"),
    ("dvr_fallback", "/direct/hls/live/2033791/k12dvr/index.m3u8?b-in-range=800-2700"),
    ("n12_fallback", "/n12/hls/live/2103938/k12/index.m3u8?b-in-range=0-1100"),
)
DYNAMIC_SOURCE_PREFIX = "keshet12_public_entitlement_"
HttpOpen = Callable[..., object]


class Keshet12ResolutionError(Exception):
    def __init__(self, category: FailureCategory, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = redact_sensitive(detail)


def redact_sensitive(value: object) -> str:
    text = str(value)
    text = re.sub(
        r"https?://[^\s]+",
        lambda match: match.group(0).split("?", 1)[0] + ("?<redacted>" if "?" in match.group(0) else ""),
        text,
    )
    return re.sub(
        r"(?i)\b(ticket|hdnea|hdnts|token|auth|signature|sig|expires?)=([^&\s]+)",
        r"\1=<redacted>",
        text,
    )


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
        return None, [f"channel12_override.json is invalid: {redact_sensitive(exc)}"], True


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
        "Channel 12 could not obtain a temporary public playback ticket. Other channels are unaffected. "
        "Try again later, add a legal Channel 12 override, or configure a local TVHeadend mapping."
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


def _http_error_category(status: int) -> FailureCategory:
    if status == 403:
        return FailureCategory.KESHET12_FORBIDDEN
    if status == 404:
        return FailureCategory.KESHET12_NOT_FOUND
    return FailureCategory.KESHET12_HTTP_ERROR


def _read_response(
    url: str,
    headers: dict[str, str],
    timeout: float,
    *,
    http_open: HttpOpen | None = None,
    limit: int = 16384,
) -> bytes:
    request = urllib.request.Request(url, method="GET", headers=headers)
    opener = http_open or urllib.request.urlopen
    try:
        with opener(request, timeout=max(0.1, timeout)) as response:  # type: ignore[attr-defined]
            status = int(getattr(response, "status", 200))
            if status >= 400:
                raise Keshet12ResolutionError(_http_error_category(status), f"HTTP {status}")
            return response.read(limit)
    except Keshet12ResolutionError:
        raise
    except urllib.error.HTTPError as exc:
        raise Keshet12ResolutionError(_http_error_category(exc.code), f"HTTP {exc.code}") from None
    except (socket.timeout, TimeoutError):
        raise Keshet12ResolutionError(FailureCategory.KESHET12_TIMEOUT, "request timed out") from None
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
            raise Keshet12ResolutionError(FailureCategory.KESHET12_TIMEOUT, "request timed out") from None
        raise Keshet12ResolutionError(FailureCategory.KESHET12_HTTP_ERROR, "network request failed") from None
    except Exception as exc:
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_UNKNOWN_ERROR,
            redact_sensitive(exc),
        ) from None


def _entitlement_request_url(relative_path: str) -> str:
    query = urllib.parse.urlencode({"et": "ngt", "lp": relative_path, "rv": "AKAMAI"})
    return f"{ENTITLEMENT_URL}?{query}"


def _parse_ticket(payload: bytes) -> str:
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "public entitlement returned malformed JSON",
        ) from None
    if not isinstance(result, dict):
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "public entitlement response was not an object",
        )
    case_id = str(result.get("caseId", ""))
    if case_id != "1":
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_NO_PLAYABLE_SOURCE,
            f"public entitlement rejected the free request (caseId {case_id or 'missing'})",
        )
    tickets = result.get("tickets")
    if not isinstance(tickets, list) or not tickets or not isinstance(tickets[0], dict):
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "public entitlement response did not include a ticket",
        )
    raw_ticket = tickets[0].get("ticket")
    if not isinstance(raw_ticket, str) or not raw_ticket.strip():
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "public entitlement response included an empty ticket",
        )
    ticket = urllib.parse.unquote_plus(raw_ticket).lstrip("?&")
    if not ticket or "://" in ticket or "\r" in ticket or "\n" in ticket:
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "public entitlement returned an invalid ticket shape",
        )
    return ticket


def resolve_entitled_manifest(
    relative_path: str,
    timeout: float,
    *,
    http_open: HttpOpen | None = None,
    validate_manifest: bool = True,
) -> str:
    entitlement_payload = _read_response(
        _entitlement_request_url(relative_path),
        ENTITLEMENT_HEADERS,
        timeout,
        http_open=http_open,
    )
    ticket = _parse_ticket(entitlement_payload)
    path_without_query = urllib.parse.urlsplit(relative_path).path
    if not path_without_query.startswith("/"):
        raise Keshet12ResolutionError(
            FailureCategory.KESHET12_BAD_RESPONSE_SHAPE,
            "reviewed stream path was not relative",
        )
    manifest_url = f"{STREAM_BASE_URL}{path_without_query}?{ticket}"
    if validate_manifest:
        sample = _read_response(
            manifest_url,
            PUBLIC_WEB_HEADERS,
            timeout,
            http_open=http_open,
            limit=4096,
        )
        if b"#EXTM3U" not in sample:
            raise Keshet12ResolutionError(
                FailureCategory.KESHET12_MANIFEST_INVALID,
                "temporary manifest did not contain an HLS header",
            )
    return manifest_url


def check_public_entitlement_path(
    relative_path: str,
    timeout: float,
    *,
    http_open: HttpOpen | None = None,
) -> Tuple[bool, str]:
    try:
        resolve_entitled_manifest(relative_path, timeout, http_open=http_open, validate_manifest=True)
        return True, "ok"
    except Keshet12ResolutionError as exc:
        return False, exc.category.value
    except Exception:
        return False, FailureCategory.KESHET12_UNKNOWN_ERROR.value


def _dynamic_source(path_id: str) -> Source:
    return Source(
        id=f"{DYNAMIC_SOURCE_PREFIX}{path_id}",
        type=SourceType.DIRECT_HLS,
        priority=10,
        enabled=True,
        url="",
        headers=dict(PUBLIC_WEB_HEADERS),
        mime_type="application/vnd.apple.mpegurl",
        requires_inputstream_adaptive=False,
        is_user_configured=False,
        evidence_url=OFFICIAL_LIVE_PAGE,
        notes="Dynamic public/free Mako entitlement; temporary ticket is never persisted.",
    )


def _dynamic_path_order(cache: CacheStore) -> List[Tuple[str, str]]:
    paths = list(KESHET12_RELATIVE_PATHS)
    last_id = str(cache.channel12_state().get("channel12_last_successful_source", ""))
    if last_id.startswith(DYNAMIC_SOURCE_PREFIX):
        preferred = last_id[len(DYNAMIC_SOURCE_PREFIX) :]
        paths.sort(key=lambda item: (item[0] != preferred, KESHET12_RELATIVE_PATHS.index(item)))
    return paths


def _try_dynamic_paths(
    channel: Channel,
    settings: AddonSettings,
    cache: CacheStore,
    *,
    http_open: HttpOpen | None,
) -> Tuple[PlayableResult | None, List[str], FailureCategory | None]:
    failures: List[str] = []
    first_category: FailureCategory | None = None
    deadline = time.monotonic() + 6.0
    per_request_timeout = float(max(1, min(settings.network_timeout_seconds, 4)))
    for path_id, relative_path in _dynamic_path_order(cache):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            failures.append(f"{path_id}: {FailureCategory.KESHET12_TIMEOUT.value}")
            first_category = first_category or FailureCategory.KESHET12_TIMEOUT
            break
        try:
            manifest_url = resolve_entitled_manifest(
                relative_path,
                min(per_request_timeout, remaining),
                http_open=http_open,
                validate_manifest=True,
            )
            source = _dynamic_source(path_id)
            result = PlayableResult(
                channel=channel,
                source=source,
                url=manifest_url,
                headers=dict(PUBLIC_WEB_HEADERS),
                mime_type=source.mime_type,
            )
            _remember(cache, result)
            kodi_log(f"{LOG_PREFIX} public entitlement resolved path={path_id}")
            return result, failures, first_category
        except Keshet12ResolutionError as exc:
            first_category = first_category or exc.category
            failures.append(f"{path_id}: {exc.category.value}")
            kodi_log(f"{LOG_PREFIX} path={path_id} failed category={exc.category.value}")
        except Exception:
            first_category = first_category or FailureCategory.KESHET12_UNKNOWN_ERROR
            failures.append(f"{path_id}: {FailureCategory.KESHET12_UNKNOWN_ERROR.value}")
            kodi_log(f"{LOG_PREFIX} path={path_id} failed category={FailureCategory.KESHET12_UNKNOWN_ERROR.value}")
    return None, failures, first_category


def _clone_channel(channel: Channel, sources: List[Source]) -> Channel:
    return replace(channel, sources=sources)


def _remember(cache: CacheStore, result: PlayableResult | FailureResult) -> None:
    if isinstance(result, PlayableResult):
        cache.set_channel12_success(result.source.id, result.source.type.value)
    else:
        cache.set_channel12_failure(result.category.value, redact_sensitive(result.technical_details))


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
    http_open: HttpOpen | None = None,
) -> PlayableResult | FailureResult:
    try:
        kodi_log(f"{LOG_PREFIX} resolving mode={mode}")
        override, override_errors, _ = load_channel12_override(paths)
        safe_override_errors = [redact_sensitive(error) for error in override_errors]
        if safe_override_errors:
            cache.set_channel12_failure(FailureCategory.KESHET12_BAD_RESPONSE_SHAPE.value, "; ".join(safe_override_errors))

        normal_sources = list(channel.sources)
        bundled_sources = [
            source
            for source in normal_sources
            if source.playable
            and not source.is_user_configured
            and source.type in {SourceType.DIRECT_HLS, SourceType.DIRECT_DASH}
        ]
        user_sources = [
            source
            for source in normal_sources
            if source.playable and source.is_user_configured and source.type != SourceType.LOCAL_TVHEADEND
        ]
        tvh_sources = [source for source in normal_sources if source.type == SourceType.LOCAL_TVHEADEND and source.playable]
        override_sources = [override] if override else []
        user_plan = override_sources + [source for source in user_sources if source.id != "keshet12_user_override"]

        failures: List[str] = []
        dynamic_failure_category: FailureCategory | None = None
        run_dynamic = mode in {"auto", "normal"}
        if run_dynamic:
            dynamic_result, dynamic_failures, dynamic_failure_category = _try_dynamic_paths(
                channel,
                settings,
                cache,
                http_open=http_open,
            )
            failures.extend(f"dynamic/{item}" for item in dynamic_failures)
            if dynamic_result:
                return dynamic_result

        plans: List[Tuple[str, List[Source]]] = []
        if mode == "override":
            plans.append(("user", user_plan))
        elif mode == "tvheadend":
            plans.append(("tvheadend", tvh_sources))
        elif mode == "normal":
            plans.append(("bundled-fallback", bundled_sources))
        else:
            last_id = cache.channel12_state().get("channel12_last_successful_source", "")
            fallback_sources = bundled_sources + user_plan + tvh_sources
            last_sources = [source for source in fallback_sources if source.id == last_id and source.enabled]
            if last_sources:
                plans.append(("last-known", last_sources))
            plans.extend(
                [
                    ("bundled-fallback", bundled_sources),
                    ("user", user_plan),
                    ("tvheadend", tvh_sources),
                ]
            )

        attempted_ids: set[str] = set()
        for plan_name, sources in plans:
            unique_sources = [source for source in sources if source.id not in attempted_ids]
            attempted_ids.update(source.id for source in unique_sources)
            if not unique_sources:
                failures.append(f"{plan_name}: no source")
                continue
            try:
                result = _run_resolver(
                    channel,
                    unique_sources,
                    settings,
                    cache,
                    validate_network=validate_network,
                    inputstream_adaptive_available=inputstream_adaptive_available,
                )
            except Exception:
                failures.append(f"{plan_name}: {FailureCategory.KESHET12_UNKNOWN_ERROR.value}")
                continue
            if isinstance(result, PlayableResult):
                kodi_log(f"{LOG_PREFIX} resolved fallback source={result.source.id}")
                _remember(cache, result)
                return result
            failures.append(f"{plan_name}: {_map_failure(result.category).value}")

        failure = FailureResult(
            channel,
            category=dynamic_failure_category or FailureCategory.KESHET12_NO_PLAYABLE_SOURCE,
            user_message=channel12_failure_message(),
            technical_details="; ".join(failures + safe_override_errors) or "No Channel 12 source could be resolved.",
        )
        _remember(cache, failure)
        kodi_log(f"{LOG_PREFIX} failure isolated; other channels unaffected")
        return failure
    except Exception as exc:
        failure = FailureResult(
            channel,
            category=FailureCategory.KESHET12_UNKNOWN_ERROR,
            user_message=channel12_failure_message(),
            technical_details=redact_sensitive(exc),
        )
        _remember(cache, failure)
        kodi_log(f"{LOG_PREFIX} unexpected failure isolated category={failure.category.value}")
        return failure


def build_channel12_diagnostics(paths: RuntimePaths, channel: Channel | None, cache: CacheStore) -> str:
    override, errors, exists = load_channel12_override(paths)
    state = cache.channel12_state()
    lines = [
        "Channel 12 Diagnostics",
        "Resolver: dynamic public/free Mako entitlement",
        "Failure isolation: enabled",
        "Temporary ticket persistence: disabled",
        f"Reviewed relative paths: {len(KESHET12_RELATIVE_PATHS)}",
        f"Override path: {channel12_override_path(paths)}",
        f"Override file exists: {'yes' if exists else 'no'}",
        f"Override valid/enabled: {'yes' if override else 'no'}",
        f"Last successful source: {state.get('channel12_last_successful_source') or '-'}",
        f"Last successful at: {state.get('channel12_last_successful_at') or '-'}",
        f"Last failure reason: {state.get('channel12_last_failure_reason') or '-'}",
        f"Last failure at: {state.get('channel12_last_failure_at') or '-'}",
        f"Last failure details: {redact_sensitive(state.get('channel12_last_failure_details') or '-')}",
    ]
    if channel:
        tvh = [source for source in channel.sources if source.type == SourceType.LOCAL_TVHEADEND and source.playable]
        fallback_sources = [source for source in channel.sources if source.playable]
        lines.append(f"Configured fallback sources: {len(fallback_sources)}")
        lines.append(f"TVHeadend mapping configured: {'yes' if tvh else 'no'}")
    else:
        lines.append("Channel entry: missing")
    if errors:
        lines.append("Override validation errors:")
        lines.extend(f"- {redact_sensitive(error)}" for error in errors)
    return "\n".join(lines)
