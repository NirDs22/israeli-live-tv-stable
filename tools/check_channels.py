#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resources.lib.models import FailureCategory, PLAYABLE_SOURCE_TYPES, SourceType, source_from_dict  # noqa: E402
from resources.lib.channel_policy import RETIRED_CHANNEL_IDS  # noqa: E402
from resources.lib.channels.keshet12 import (  # noqa: E402
    DYNAMIC_SOURCE_PREFIX,
    KESHET12_RELATIVE_PATHS,
    check_public_entitlement_path,
)


CHECKED_SOURCE_TYPES = {SourceType.DIRECT_HLS.value, SourceType.DIRECT_DASH.value}
NON_BUNDLED_SOURCE_TYPES = {SourceType.LOCAL_M3U.value, SourceType.LOCAL_TVHEADEND.value}
INFO_SOURCE_TYPES = {SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY.value, SourceType.DISABLED.value}
DEFAULT_CHANNELS_PATH = ROOT / "resources" / "data" / "channels.json"
DEFAULT_CANDIDATES_PATH = ROOT / "resources" / "data" / "channel_candidates.json"
DEFAULT_DISCOVERY_PATH = ROOT / "resources" / "data" / "channel_discovery.json"
DEFAULT_REPORT_JSON = ROOT / "channel-health-report.json"
DEFAULT_REPORT_MD = ROOT / "channel-health-report.md"


@dataclass
class SourceCheck:
    channel_id: str
    channel_name: str
    source_id: str
    source_type: str
    priority: int
    url: str
    ok: bool
    status: str
    is_primary: bool = False
    needs_replacement_search: bool = False


@dataclass
class CandidateResult:
    channel_id: str
    source_id: str
    status: str
    message: str
    url: str = ""


@dataclass
class DiscoveryFinding:
    target_id: str
    target_name: str
    source_id: str
    status: str
    message: str
    evidence_url: str = ""
    matched_alias: str = ""


@dataclass
class ChannelSummary:
    channel_id: str
    channel_name: str
    primary_source_id: str = ""
    primary_ok: bool = False
    working_source_count: int = 0
    checked_source_count: int = 0
    broken_source_count: int = 0
    fallback_promoted: bool = False
    replacement_search_needed: bool = False
    all_sources_broken: bool = False


@dataclass
class HealthReport:
    checked_at: str
    changed: bool = False
    channels: list[ChannelSummary] = field(default_factory=list)
    sources: list[SourceCheck] = field(default_factory=list)
    candidates: list[CandidateResult] = field(default_factory=list)
    discovery: list[DiscoveryFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    keshet12: dict[str, Any] = field(default_factory=dict)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_sort_key(source: dict[str, Any]) -> tuple[int, str]:
    try:
        priority = int(source.get("priority", 100))
    except Exception:
        priority = 100
    return priority, str(source.get("id", ""))


def checked_sources(channel: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = channel.get("sources", [])
    if not isinstance(raw_sources, list):
        return []
    return [
        source
        for source in raw_sources
        if isinstance(source, dict)
        and source.get("enabled", True)
        and source.get("type") in CHECKED_SOURCE_TYPES
        and source.get("url")
        and not source.get("is_user_configured", False)
    ]


def keshet12_entitlement_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": f"{DYNAMIC_SOURCE_PREFIX}{path_id}",
            "type": SourceType.DIRECT_HLS.value,
            "priority": 10 + (index * 10),
            "enabled": True,
            "url": relative_path,
            "headers": {},
            "notes": "Dynamic public/free entitlement path; temporary ticket is never stored.",
            "dynamic_entitlement": True,
        }
        for index, (path_id, relative_path) in enumerate(KESHET12_RELATIVE_PATHS)
    ]


def primary_source(sources: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    sorted_sources = sorted(sources, key=source_sort_key)
    return sorted_sources[0] if sorted_sources else None


def check_url(source: dict[str, Any], timeout: int) -> tuple[bool, str]:
    source_type = str(source.get("type", ""))
    url = str(source.get("url", ""))
    if source_type not in CHECKED_SOURCE_TYPES:
        return False, FailureCategory.SOURCE_DISABLED.value
    if not url:
        return False, FailureCategory.SOURCE_NOT_CONFIGURED.value

    headers = source.get("headers") or {}
    if not isinstance(headers, dict):
        return False, FailureCategory.INVALID_USER_CONFIG.value

    request = urllib.request.Request(url, method="GET", headers={str(k): str(v) for k, v in headers.items()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status == 403:
                return False, FailureCategory.HTTP_403.value
            if status == 404:
                return False, FailureCategory.HTTP_404.value
            if status >= 500:
                return False, FailureCategory.HTTP_5XX.value
            sample = response.read(2048)
            if source_type == SourceType.DIRECT_HLS.value and b"#EXTM3U" not in sample:
                return False, FailureCategory.MANIFEST_INVALID.value
            if source_type == SourceType.DIRECT_DASH.value and b"<MPD" not in sample:
                return False, FailureCategory.MANIFEST_INVALID.value
            return True, "ok"
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return False, FailureCategory.HTTP_403.value
        if exc.code == 404:
            return False, FailureCategory.HTTP_404.value
        if exc.code >= 500:
            return False, FailureCategory.HTTP_5XX.value
        return False, FailureCategory.UNKNOWN_ERROR.value
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            return False, FailureCategory.NETWORK_TIMEOUT.value
        return False, FailureCategory.DNS_ERROR.value
    except TimeoutError:
        return False, FailureCategory.NETWORK_TIMEOUT.value
    except Exception:
        return False, FailureCategory.UNKNOWN_ERROR.value


def validate_candidate(candidate: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return False, "candidate must be an object"
    if candidate.get("status", "candidate") == "rejected":
        return False, str(candidate.get("rejection_reason", "candidate was previously rejected"))
    if not candidate.get("evidence_url"):
        return False, "candidate requires evidence_url"
    if not candidate.get("notes"):
        return False, "candidate requires notes"
    try:
        source = source_from_dict(candidate)
    except Exception as exc:
        return False, str(exc)
    if source.type.value not in CHECKED_SOURCE_TYPES:
        return False, "candidate must be DIRECT_HLS or DIRECT_DASH"
    if source.is_user_configured:
        return False, "candidate must be bundled-source metadata, not user configured"
    if not source.url:
        return False, "candidate requires url"
    return True, "ok"


def candidate_exists(channel: dict[str, Any], candidate_id: str) -> bool:
    sources = channel.get("sources", [])
    return any(isinstance(source, dict) and source.get("id") == candidate_id for source in sources)


def add_candidate_as_fallback(channel: dict[str, Any], candidate: dict[str, Any]) -> None:
    source = deepcopy(candidate)
    source.pop("status", None)
    source.pop("rejection_reason", None)
    source["enabled"] = bool(source.get("enabled", True))
    source["priority"] = max(int(source.get("priority", 70)), 70)
    source["is_user_configured"] = False
    source["last_verified_at"] = datetime.now(timezone.utc).date().isoformat()
    channel.setdefault("sources", []).append(source)


def promote_best_fallback(channel: dict[str, Any], checks: list[SourceCheck]) -> bool:
    working = [check for check in checks if check.channel_id == channel.get("id") and check.ok]
    if not working:
        return False
    best = sorted(working, key=lambda item: (item.priority, item.source_id))[0]
    sources = channel.get("sources", [])
    if not isinstance(sources, list):
        return False

    changed = False
    for source in sources:
        if not isinstance(source, dict) or source.get("type") not in CHECKED_SOURCE_TYPES:
            continue
        if source.get("id") == best.source_id and int(source.get("priority", 100)) != 10:
            source["priority"] = 10
            changed = True
        elif source.get("id") != best.source_id and int(source.get("priority", 100)) <= 10:
            source["priority"] = 30
            changed = True
    return changed


def load_candidates(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    data = load_json(path)
    raw = data.get("channels", {})
    if not isinstance(raw, dict):
        raise ValueError("channel_candidates.json must contain an object named channels")
    candidates: dict[str, list[dict[str, Any]]] = {}
    for channel_id, items in raw.items():
        if isinstance(items, list):
            candidates[str(channel_id)] = [item for item in items if isinstance(item, dict)]
    return candidates


def load_discovery_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sources": [], "targets": []}
    data = load_json(path)
    if not isinstance(data.get("sources", []), list):
        raise ValueError("channel_discovery.json sources must be a list")
    if not isinstance(data.get("targets", []), list):
        raise ValueError("channel_discovery.json targets must be a list")
    return data


def normalize_search_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def fetch_discovery_text(source: dict[str, Any], timeout: int, http_open=urllib.request.urlopen) -> tuple[bool, str]:
    url = str(source.get("url", ""))
    if not url:
        return False, "missing discovery source URL"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IsraeliLiveTVStableChannelDiscovery/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with http_open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                return False, f"http_{status}"
            raw = response.read(500_000)
            charset = "utf-8"
            headers = getattr(response, "headers", None)
            if headers and hasattr(headers, "get_content_charset"):
                charset = headers.get_content_charset() or "utf-8"
            return True, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            return False, FailureCategory.NETWORK_TIMEOUT.value
        return False, FailureCategory.DNS_ERROR.value
    except TimeoutError:
        return False, FailureCategory.NETWORK_TIMEOUT.value
    except Exception as exc:
        return False, f"unknown_error: {exc.__class__.__name__}"


def discover_new_channels(
    config: dict[str, Any],
    configured_channel_ids: set[str],
    timeout: int,
    http_open=urllib.request.urlopen,
) -> list[DiscoveryFinding]:
    sources = [source for source in config.get("sources", []) if isinstance(source, dict) and source.get("enabled", True)]
    targets = [target for target in config.get("targets", []) if isinstance(target, dict) and target.get("enabled", True)]
    findings: list[DiscoveryFinding] = []

    for source in sources:
        source_id = str(source.get("id", "discovery_source"))
        ok, text_or_error = fetch_discovery_text(source, timeout, http_open=http_open)
        if not ok:
            findings.append(
                DiscoveryFinding(
                    target_id="",
                    target_name="",
                    source_id=source_id,
                    status="source_failed",
                    message=text_or_error,
                    evidence_url=str(source.get("url", "")),
                )
            )
            continue

        normalized = normalize_search_text(text_or_error)
        for target in targets:
            target_id = str(target.get("id", "")).strip()
            target_name = str(target.get("name", target_id)).strip()
            if not target_id or target_id in configured_channel_ids or target_id in RETIRED_CHANNEL_IDS:
                continue
            aliases = [str(alias).strip() for alias in target.get("aliases", []) if str(alias).strip()]
            matched_alias = next((alias for alias in aliases if normalize_search_text(alias) in normalized), "")
            if matched_alias:
                findings.append(
                    DiscoveryFinding(
                        target_id=target_id,
                        target_name=target_name,
                        source_id=source_id,
                        status="found_missing_channel",
                        message="Potential new Hebrew/Israeli channel found in a public directory. Manual legal source review is required before adding it.",
                        evidence_url=str(source.get("url", "")),
                        matched_alias=matched_alias,
                    )
                )
            else:
                findings.append(
                    DiscoveryFinding(
                        target_id=target_id,
                        target_name=target_name,
                        source_id=source_id,
                        status="not_found",
                        message="Target aliases were not present in this source.",
                        evidence_url=str(source.get("url", "")),
                    )
                )
    return findings


def generate_report_markdown(report: HealthReport) -> str:
    lines = [
        "# Channel Health Report",
        "",
        f"Checked at: {report.checked_at}",
        f"Changed files: {'yes' if report.changed else 'no'}",
        "",
        "## Channels",
        "",
        "| Channel | Primary | Working | Broken | Replacement search |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for channel in report.channels:
        search = "yes" if channel.replacement_search_needed else "no"
        primary = "ok" if channel.primary_ok else "failed"
        if not channel.primary_source_id:
            primary = "-"
        lines.append(
            f"| {channel.channel_name} (`{channel.channel_id}`) | {channel.primary_source_id or '-'} {primary} | "
            f"{channel.working_source_count} | {channel.broken_source_count} | {search} |"
        )

    broken = [source for source in report.sources if not source.ok]
    if broken:
        lines.extend(["", "## Broken Sources", ""])
        for source in broken:
            lines.append(f"- `{source.channel_id}` / `{source.source_id}`: {source.status}")

    if report.candidates:
        lines.extend(["", "## Candidate Results", ""])
        for candidate in report.candidates:
            lines.append(f"- `{candidate.channel_id}` / `{candidate.source_id}`: {candidate.status} - {candidate.message}")

    if report.discovery:
        lines.extend(["", "## New Channel Discovery", ""])
        for finding in report.discovery:
            target = f"`{finding.target_id}`" if finding.target_id else "-"
            alias = f" matched `{finding.matched_alias}`" if finding.matched_alias else ""
            lines.append(
                f"- {target} from `{finding.source_id}`: {finding.status}{alias}. "
                f"{finding.message} Evidence: {finding.evidence_url or '-'}"
            )

    if report.keshet12:
        lines.extend(["", "## Channel 12 / Keshet 12", ""])
        lines.append(f"- Checked: {'yes' if report.keshet12.get('checked') else 'no'}")
        lines.append(f"- Primary: {report.keshet12.get('primary_source_id') or '-'} ({report.keshet12.get('primary_status') or '-'})")
        lines.append(f"- Working sources: {report.keshet12.get('working_source_count', 0)}")
        lines.append(f"- Broken sources: {report.keshet12.get('broken_source_count', 0)}")
        lines.append(f"- Replacement search needed: {'yes' if report.keshet12.get('replacement_search_needed') else 'no'}")
        lines.append(f"- Automatic repair attempted: {'yes' if report.keshet12.get('repair_attempted') else 'no'}")
        actions = report.keshet12.get("repair_actions") or []
        if actions:
            lines.append("- Repair actions:")
            lines.extend(f"  - {action}" for action in actions)
        else:
            lines.append("- Repair actions: none")

    if report.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in report.notes)
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    channels_path = Path(args.channels)
    candidates_path = Path(args.candidates)
    discovery_path = Path(args.discovery_config)
    payload = load_json(channels_path)
    channels = payload.get("channels")
    if not isinstance(channels, list):
        raise ValueError("channels.json must contain a list named channels")

    candidate_map = load_candidates(candidates_path)
    discovery_config = load_discovery_config(discovery_path)
    report = HealthReport(checked_at=utc_now())
    changed = False

    for channel in channels:
        if not isinstance(channel, dict) or not channel.get("enabled", True):
            continue
        channel_id = str(channel.get("id", ""))
        if channel_id in RETIRED_CHANNEL_IDS:
            continue
        channel_name = str(channel.get("name", channel_id))
        sources = keshet12_entitlement_sources() if channel_id == "keshet12" else checked_sources(channel)
        primary = primary_source(sources)
        channel_checks: list[SourceCheck] = []

        for source in sorted(sources, key=source_sort_key):
            if channel_id == "keshet12" and source.get("dynamic_entitlement"):
                ok, status = check_public_entitlement_path(str(source.get("url", "")), args.timeout)
            else:
                ok, status = check_url(source, args.timeout)
            check = SourceCheck(
                channel_id=channel_id,
                channel_name=channel_name,
                source_id=str(source.get("id", "")),
                source_type=str(source.get("type", "")),
                priority=int(source.get("priority", 100)),
                url=str(source.get("url", "")),
                ok=ok,
                status=status,
                is_primary=bool(primary and source.get("id") == primary.get("id")),
                needs_replacement_search=not ok,
            )
            channel_checks.append(check)
            report.sources.append(check)

        broken_count = sum(1 for check in channel_checks if not check.ok)
        working_count = sum(1 for check in channel_checks if check.ok)
        primary_ok = any(check.is_primary and check.ok for check in channel_checks)
        replacement_needed = broken_count > 0
        all_broken = bool(channel_checks) and working_count == 0
        promoted = False

        channel_repair_actions: list[str] = []

        if args.apply_fallbacks and channel_id != "keshet12" and primary and not primary_ok and working_count:
            promoted = promote_best_fallback(channel, channel_checks)
            changed = changed or promoted
            if promoted:
                channel_repair_actions.append("promoted best working fallback to primary priority")

        if args.apply_candidates and channel_id != "keshet12" and replacement_needed:
            for candidate in candidate_map.get(channel_id, []):
                candidate_id = str(candidate.get("id", ""))
                if candidate_exists(channel, candidate_id):
                    continue
                valid, message = validate_candidate(candidate)
                if not valid:
                    report.candidates.append(CandidateResult(channel_id, candidate_id, "rejected", message, str(candidate.get("url", ""))))
                    channel_repair_actions.append(f"rejected candidate {candidate_id}: {message}")
                    continue
                ok, status = check_url(candidate, args.timeout)
                if not ok:
                    report.candidates.append(CandidateResult(channel_id, candidate_id, "failed_validation", status, str(candidate.get("url", ""))))
                    channel_repair_actions.append(f"candidate {candidate_id} failed validation: {status}")
                    continue
                add_candidate_as_fallback(channel, candidate)
                changed = True
                report.candidates.append(CandidateResult(channel_id, candidate_id, "added_as_fallback", "validated and added", str(candidate.get("url", ""))))
                channel_repair_actions.append(f"added validated candidate {candidate_id} as fallback")
                break

        summary = ChannelSummary(
            channel_id=channel_id,
            channel_name=channel_name,
            primary_source_id=str(primary.get("id", "")) if primary else "",
            primary_ok=primary_ok,
            working_source_count=working_count,
            checked_source_count=len(channel_checks),
            broken_source_count=broken_count,
            fallback_promoted=promoted,
            replacement_search_needed=replacement_needed,
            all_sources_broken=all_broken,
        )
        report.channels.append(summary)

        if channel_id == "keshet12":
            primary_status = "-"
            if primary:
                primary_status = "ok" if primary_ok else "failed"
            if primary and not primary_ok and working_count:
                channel_repair_actions.append("runtime resolver will use the first working entitlement fallback path")
            if replacement_needed and not channel_repair_actions:
                channel_repair_actions.append("reviewed entitlement paths need investigation; no ticket or tokenized URL was stored")
            report.keshet12 = {
                "checked": True,
                "channel_name": channel_name,
                "primary_source_id": summary.primary_source_id,
                "primary_ok": primary_ok,
                "primary_status": primary_status,
                "working_source_count": working_count,
                "checked_source_count": len(channel_checks),
                "broken_source_count": broken_count,
                "fallback_promoted": promoted,
                "replacement_search_needed": replacement_needed,
                "all_sources_broken": all_broken,
                "repair_attempted": bool(replacement_needed),
                "repair_actions": channel_repair_actions,
                "resolver_mode": "dynamic_public_entitlement",
            }

    if not report.keshet12:
        report.keshet12 = {
            "checked": False,
            "primary_source_id": "",
            "primary_ok": False,
            "primary_status": "missing",
            "working_source_count": 0,
            "checked_source_count": 0,
            "broken_source_count": 0,
            "fallback_promoted": False,
            "replacement_search_needed": True,
            "all_sources_broken": True,
            "repair_attempted": False,
            "repair_actions": ["keshet12 channel entry was not found"],
        }
        report.notes.append("Keshet 12 channel entry is missing from channels.json.")

    if args.discover_new_channels:
        configured_channel_ids = {
            str(channel.get("id", ""))
            for channel in channels
            if isinstance(channel, dict) and channel.get("id")
        }
        report.discovery = discover_new_channels(discovery_config, configured_channel_ids, args.timeout)
        found_missing = [finding for finding in report.discovery if finding.status == "found_missing_channel"]
        if found_missing:
            report.notes.append("New channel discovery found possible missing channels; manual source/legal review is required.")

    report.changed = changed
    if changed and not args.dry_run:
        write_json(channels_path, payload)

    report_json = asdict(report)
    Path(args.report_json).write_text(json.dumps(report_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.report_markdown).write_text(generate_report_markdown(report), encoding="utf-8")

    broken_sources = [source for source in report.sources if not source.ok]
    if broken_sources:
        print(f"{len(broken_sources)} source(s) need replacement search. See {args.report_markdown}.")
    else:
        print(f"All checked sources passed. See {args.report_markdown}.")
    discovery_hits = [finding for finding in report.discovery if finding.status == "found_missing_channel"]
    if discovery_hits:
        print(f"{len(discovery_hits)} possible new channel(s) found. See {args.report_markdown}.")
    if changed:
        print("Safe channel metadata changes were prepared.")
    return 1 if broken_sources and args.fail_on_broken else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Israeli Live TV Stable bundled channel links.")
    parser.add_argument("--channels", default=str(DEFAULT_CHANNELS_PATH))
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES_PATH))
    parser.add_argument("--discovery-config", default=str(DEFAULT_DISCOVERY_PATH))
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--report-markdown", default=str(DEFAULT_REPORT_MD))
    parser.add_argument("--timeout", type=int, default=6)
    parser.add_argument("--apply-fallbacks", action="store_true")
    parser.add_argument("--apply-candidates", action="store_true")
    parser.add_argument("--discover-new-channels", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-broken", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
