#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANNELS = ROOT / "resources" / "data" / "channels.json"
PLAYABLE_TYPES = {"DIRECT_HLS", "DIRECT_DASH"}
FORBIDDEN_QUERY_KEYS = {
    "access_token",
    "auth",
    "cookie",
    "device_id",
    "hdnea",
    "jwt",
    "session",
    "signature",
    "ticket",
    "token",
}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HttpOpen = Callable[..., Any]


@dataclass
class CatalogValidationReport:
    errors: list[str] = field(default_factory=list)
    new_channel_ids: list[str] = field(default_factory=list)


def _channels(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("channels")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _is_https(value: object) -> bool:
    return isinstance(value, str) and urllib.parse.urlsplit(value).scheme == "https"


def _date_is_present(value: object) -> bool:
    return isinstance(value, str) and bool(DATE_PATTERN.fullmatch(value))


def _source_label(channel_id: str, source: dict[str, Any]) -> str:
    return f"{channel_id}/{source.get('id') or '<missing-source-id>'}"


def validate_catalog(
    payload: dict[str, Any],
    *,
    root: Path,
    base_payload: dict[str, Any] | None = None,
) -> CatalogValidationReport:
    report = CatalogValidationReport()
    channels = _channels(payload)
    if not isinstance(payload.get("channels"), list):
        report.errors.append("catalog requires a channels list")
        return report

    base_ids = {str(item.get("id")) for item in _channels(base_payload or {}) if item.get("id")}
    seen_ids: set[str] = set()

    for channel in channels:
        channel_id = str(channel.get("id") or "").strip()
        if not channel_id:
            report.errors.append("channel requires id")
            continue
        if channel_id in seen_ids:
            report.errors.append(f"{channel_id}: duplicate channel id")
        seen_ids.add(channel_id)

        enabled = bool(channel.get("enabled", True))
        logo = str(channel.get("logo") or "").strip()
        if enabled and not logo:
            report.errors.append(f"{channel_id}: enabled channel requires a logo")
        elif logo and not _is_https(logo):
            local_logo = root / logo
            if not local_logo.is_file():
                report.errors.append(f"{channel_id}: local logo does not exist: {logo}")

        is_new = base_payload is not None and channel_id not in base_ids
        if not is_new:
            continue
        report.new_channel_ids.append(channel_id)

        if not str(channel.get("name") or "").strip():
            report.errors.append(f"{channel_id}: new channel requires name")
        if not str(channel.get("tvg_id") or "").strip():
            report.errors.append(f"{channel_id}: new channel requires tvg_id")
        if not _is_https(logo):
            report.errors.append(
                f"{channel_id}: new channel logo must use HTTPS so installed addons can receive it"
            )
        if not _is_https(channel.get("logo_evidence_url")):
            report.errors.append(f"{channel_id}: new channel requires logo_evidence_url")
        if not _date_is_present(channel.get("discovered_at")):
            report.errors.append(f"{channel_id}: new channel requires discovered_at")

        raw_sources = channel.get("sources")
        playable = [
            source
            for source in raw_sources
            if isinstance(source, dict)
            and source.get("enabled", True)
            and source.get("type") in PLAYABLE_TYPES
            and source.get("url")
        ] if isinstance(raw_sources, list) else []
        if not playable:
            report.errors.append(f"{channel_id}: new channel requires a directly playable HLS/DASH source")
            continue

        if not any(source.get("type") == "DIRECT_HLS" for source in playable):
            report.errors.append(
                f"{channel_id}: automatic publication currently requires at least one HLS source for full media-segment validation"
            )

        for source in playable:
            label = _source_label(channel_id, source)
            url = str(source.get("url") or "")
            if not _is_https(url):
                report.errors.append(f"{label}: source URL must use HTTPS")
            query_keys = {key.casefold() for key in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)}
            unsafe_keys = sorted(query_keys & FORBIDDEN_QUERY_KEYS)
            if unsafe_keys:
                report.errors.append(f"{label}: forbidden token/session query parameter: {unsafe_keys[0]}")
            if source.get("headers") not in ({}, None):
                report.errors.append(f"{label}: new public source cannot require custom headers")
            if not _is_https(source.get("evidence_url")):
                report.errors.append(f"{label}: requires evidence_url")
            if not _date_is_present(source.get("discovered_at")):
                report.errors.append(f"{label}: requires discovered_at")
            if not _date_is_present(source.get("last_verified_at")):
                report.errors.append(f"{label}: requires last_verified_at")
            if source.get("validation_result") != "manifest_and_media_segment_ok":
                report.errors.append(
                    f"{label}: validation_result must be manifest_and_media_segment_ok"
                )
            if not str(source.get("notes") or "").strip():
                report.errors.append(f"{label}: requires notes")

    return report


def _read_url(url: str, timeout: int, limit: int, http_open: HttpOpen) -> tuple[bytes, Any]:
    request = urllib.request.Request(url, method="GET")
    with http_open(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200))
        if status < 200 or status >= 300:
            raise ValueError(f"HTTP {status}")
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError(f"response exceeded {limit} bytes")
        return body, getattr(response, "headers", {})


def _manifest_uri(text: str, *, after_stream_inf: bool = False) -> str:
    waiting_for_variant = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-STREAM-INF"):
            waiting_for_variant = True
            continue
        if line.startswith("#"):
            continue
        if after_stream_inf and not waiting_for_variant:
            continue
        return line
    return ""


def probe_hls_source(
    url: str,
    timeout: int,
    *,
    http_open: HttpOpen = urllib.request.urlopen,
) -> tuple[bool, str]:
    try:
        manifest_body, _ = _read_url(url, timeout, 1024 * 1024, http_open)
        manifest_text = manifest_body.decode("utf-8", errors="replace")
        if "#EXTM3U" not in manifest_text:
            return False, "manifest_invalid"
        if "#EXT-X-KEY" in manifest_text:
            return False, "encrypted_or_drm_manifest"

        if "#EXT-X-STREAM-INF" in manifest_text:
            variant = _manifest_uri(manifest_text, after_stream_inf=True)
            if not variant:
                return False, "master_manifest_has_no_variant"
            media_url = urllib.parse.urljoin(url, variant)
            media_body, _ = _read_url(media_url, timeout, 1024 * 1024, http_open)
            media_text = media_body.decode("utf-8", errors="replace")
        else:
            media_url = url
            media_text = manifest_text

        if "#EXTM3U" not in media_text or "#EXTINF" not in media_text:
            return False, "media_playlist_invalid"
        if "#EXT-X-KEY" in media_text:
            return False, "encrypted_or_drm_manifest"
        segment = _manifest_uri(media_text)
        if not segment:
            return False, "media_playlist_has_no_segment"
        segment_url = urllib.parse.urljoin(media_url, segment)
        segment_body, _ = _read_url(segment_url, timeout, 32 * 1024 * 1024, http_open)
        if not segment_body:
            return False, "empty_media_segment"
        if urllib.parse.urlsplit(segment_url).path.casefold().endswith(".ts"):
            if len(segment_body) < 188 or len(segment_body) % 188:
                return False, "incomplete_mpeg_ts_segment"
            if any(segment_body[offset] != 0x47 for offset in range(0, len(segment_body), 188)):
                return False, "invalid_mpeg_ts_segment"
        return True, "manifest_and_media_segment_ok"
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        return False, f"network_validation_failed: {exc}"


def probe_logo(
    url: str,
    timeout: int,
    *,
    http_open: HttpOpen = urllib.request.urlopen,
) -> tuple[bool, str]:
    try:
        body, headers = _read_url(url, timeout, 5 * 1024 * 1024, http_open)
        content_type = str(headers.get("Content-Type", "")).split(";", 1)[0].strip().casefold()
        if content_type != "image/png":
            return False, f"logo_content_type_must_be_image_png: {content_type or 'missing'}"
        if len(body) < 24 or not body.startswith(b"\x89PNG\r\n\x1a\n") or body[12:16] != b"IHDR":
            return False, "logo_is_not_a_valid_png"
        width = int.from_bytes(body[16:20], "big")
        height = int.from_bytes(body[20:24], "big")
        if width < 128 or height < 128:
            return False, f"logo_is_too_small: {width}x{height}"
        return True, f"png_ok_{width}x{height}"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return False, f"logo_validation_failed: {exc}"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _load_git_payload(ref: str, relative_path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError(f"{ref}:{relative_path} must contain a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the complete publication contract for new TV channels.")
    parser.add_argument("--channels", default=str(DEFAULT_CHANNELS))
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--check-network", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args(argv)

    channels_path = Path(args.channels)
    payload = _load_json(channels_path)
    try:
        relative_path = str(channels_path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        relative_path = str(channels_path)
    base_payload = _load_git_payload(args.base_ref, relative_path) if args.base_ref else None
    report = validate_catalog(payload, root=ROOT, base_payload=base_payload)

    if args.check_network:
        by_id = {str(item.get("id")): item for item in _channels(payload)}
        for channel in _channels(payload):
            logo = str(channel.get("logo") or "")
            if _is_https(logo):
                ok, message = probe_logo(logo, args.timeout)
                if not ok:
                    report.errors.append(f"{channel.get('id')}: logo network validation failed: {message}")
        for channel_id in report.new_channel_ids:
            channel = by_id[channel_id]
            hls_sources = [
                source for source in channel.get("sources", [])
                if isinstance(source, dict)
                and source.get("enabled", True)
                and source.get("type") == "DIRECT_HLS"
            ]
            if hls_sources:
                outcomes = [probe_hls_source(str(source.get("url") or ""), args.timeout) for source in hls_sources]
                if not any(ok for ok, _ in outcomes):
                    details = ", ".join(message for _, message in outcomes)
                    report.errors.append(f"{channel_id}: no HLS source passed manifest and media-segment validation: {details}")

    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Channel catalog publication contract passed; "
        f"new channels: {', '.join(report.new_channel_ids) if report.new_channel_ids else 'none'}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
