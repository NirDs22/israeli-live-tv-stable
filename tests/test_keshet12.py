import json
import socket
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from resources.lib.cache import CacheStore
from resources.lib.channels.keshet12 import (
    DYNAMIC_SOURCE_PREFIX,
    ENTITLEMENT_HEADERS,
    KESHET12_RELATIVE_PATHS,
    PUBLIC_WEB_HEADERS,
    build_channel12_diagnostics,
    channel12_override_path,
    disable_channel12_override,
    load_channel12_override,
    redact_sensitive,
    resolve_keshet12,
)
from resources.lib.config import RuntimePaths
from resources.lib.models import Channel, FailureCategory, FailureResult, PlayableResult, Source, SourceType
from resources.lib.resolver import SourceResolver
from resources.lib.settings import AddonSettings
from resources.lib.utils import write_json


def paths_for(tmp: str) -> RuntimePaths:
    base = Path(tmp)
    return RuntimePaths(
        userdata=base,
        bundled_channels=base / "channels.json",
        remote_channels=base / "remote_channels.json",
        user_sources=base / "user_sources.json",
        tvheadend_mapping=base / "tvheadend_mapping.json",
        cache=base / "cache.json",
        generated_m3u=base / "playlist.m3u",
    )


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class FakeOpen:
    def __init__(self, *actions) -> None:
        self.actions = list(actions)
        self.requests = []

    def __call__(self, request, timeout=0):
        self.requests.append((request, timeout))
        action = self.actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


def ticket_response(case_id="1", ticket="hdnea%3Dtemporary-secret%26exp%3D1") -> FakeResponse:
    return FakeResponse(json.dumps({"caseId": case_id, "tickets": [{"ticket": ticket}]}).encode("utf-8"))


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/path?ticket=secret", status, "failed", {}, None)


def empty_channel() -> Channel:
    return Channel(id="keshet12", name="Keshet 12", sources=[])


class Keshet12Tests(unittest.TestCase):
    def test_missing_override_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, errors, exists = load_channel12_override(paths_for(tmp))
            self.assertIsNone(source)
            self.assertEqual(errors, [])
            self.assertFalse(exists)

    def test_invalid_override_shape_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            write_json(channel12_override_path(paths), ["bad"])
            source, errors, exists = load_channel12_override(paths)
            self.assertIsNone(source)
            self.assertTrue(exists)
            self.assertIn("must contain a JSON object", errors[0])

    def test_disabled_override_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            write_json(channel12_override_path(paths), {"enabled": False, "url": "https://example.com/a.m3u8"})
            source, errors, exists = load_channel12_override(paths)
            self.assertIsNone(source)
            self.assertEqual(errors, [])
            self.assertTrue(exists)

    def test_valid_override_is_user_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            write_json(
                channel12_override_path(paths),
                {"enabled": True, "type": "DIRECT_HLS", "url": "https://example.com/a.m3u8", "headers": {}},
            )
            source, errors, exists = load_channel12_override(paths)
            self.assertTrue(exists)
            self.assertEqual(errors, [])
            self.assertIsNotNone(source)
            self.assertEqual(source.id, "keshet12_user_override")
            self.assertTrue(source.is_user_configured)

    def test_disable_override_writes_enabled_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            write_json(channel12_override_path(paths), {"enabled": True, "url": "https://example.com/a.m3u8"})
            disable_channel12_override(paths)
            source, _, exists = load_channel12_override(paths)
            self.assertTrue(exists)
            self.assertIsNone(source)

    def test_successful_ticket_resolution_is_ephemeral(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            opener = FakeOpen(ticket_response(), FakeResponse(b"#EXTM3U\n#EXT-X-VERSION:3\n"))

            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), cache, http_open=opener)

            self.assertIsInstance(result, PlayableResult)
            self.assertTrue(result.url.startswith("https://mako-streaming.akamaized.net/"))
            self.assertIn("hdnea=temporary-secret", result.url)
            self.assertEqual(result.source.url, "")
            self.assertTrue(result.source.id.startswith(DYNAMIC_SOURCE_PREFIX))
            self.assertEqual(result.headers, PUBLIC_WEB_HEADERS)
            self.assertEqual(opener.requests[0][0].headers["Origin"], ENTITLEMENT_HEADERS["Origin"])
            cache_text = paths.cache.read_text(encoding="utf-8")
            self.assertNotIn("temporary-secret", cache_text)
            self.assertNotIn("mako-streaming.akamaized.net", cache_text)

    def test_falls_back_to_second_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            opener = FakeOpen(http_error(404), ticket_response(), FakeResponse(b"#EXTM3U\n"))

            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)

            self.assertIsInstance(result, PlayableResult)
            self.assertEqual(result.source.id, f"{DYNAMIC_SOURCE_PREFIX}{KESHET12_RELATIVE_PATHS[1][0]}")
            second_entitlement_url = opener.requests[1][0].full_url
            self.assertIn("k12n12wad", second_entitlement_url)

    def test_timeout_is_channel_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            opener = FakeOpen(*(socket.timeout() for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
            self.assertIsInstance(result, FailureResult)
            self.assertEqual(result.category, FailureCategory.KESHET12_TIMEOUT)

    def test_http_errors_are_channel_specific(self):
        expected = {
            403: FailureCategory.KESHET12_FORBIDDEN,
            404: FailureCategory.KESHET12_NOT_FOUND,
            500: FailureCategory.KESHET12_HTTP_ERROR,
        }
        for status, category in expected.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                paths = paths_for(tmp)
                opener = FakeOpen(*(http_error(status) for _ in KESHET12_RELATIVE_PATHS))
                result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
                self.assertIsInstance(result, FailureResult)
                self.assertEqual(result.category, category)
                self.assertNotIn("secret", result.technical_details)

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            opener = FakeOpen(*(FakeResponse(b"{not-json") for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
            self.assertEqual(result.category, FailureCategory.KESHET12_BAD_RESPONSE_SHAPE)

    def test_unsuccessful_case_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            opener = FakeOpen(*(ticket_response(case_id="4") for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
            self.assertEqual(result.category, FailureCategory.KESHET12_NO_PLAYABLE_SOURCE)

    def test_missing_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            response = FakeResponse(json.dumps({"caseId": "1", "tickets": []}).encode("utf-8"))
            opener = FakeOpen(*(response for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
            self.assertEqual(result.category, FailureCategory.KESHET12_BAD_RESPONSE_SHAPE)

    def test_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            actions = []
            for _ in KESHET12_RELATIVE_PATHS:
                actions.extend([ticket_response(), FakeResponse(b"<html>not hls</html>")])
            result = resolve_keshet12(
                empty_channel(),
                paths,
                AddonSettings(),
                CacheStore(paths.cache),
                http_open=FakeOpen(*actions),
            )
            self.assertEqual(result.category, FailureCategory.KESHET12_MANIFEST_INVALID)

    def test_user_override_is_used_after_dynamic_paths_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            write_json(
                channel12_override_path(paths),
                {"enabled": True, "type": "DIRECT_HLS", "url": "https://example.com/user.m3u8"},
            )
            opener = FakeOpen(*(http_error(404) for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(empty_channel(), paths, AddonSettings(), CacheStore(paths.cache), http_open=opener)
            self.assertIsInstance(result, PlayableResult)
            self.assertEqual(result.source.id, "keshet12_user_override")

    def test_tvheadend_is_used_after_dynamic_and_user_fallbacks_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            tvh = Source(
                "keshet12_local_tvheadend",
                SourceType.LOCAL_TVHEADEND,
                url="http://127.0.0.1:9981/stream/channelid/12",
                is_user_configured=True,
            )
            opener = FakeOpen(*(http_error(404) for _ in KESHET12_RELATIVE_PATHS))
            result = resolve_keshet12(
                Channel(id="keshet12", name="Keshet 12", sources=[tvh]),
                paths,
                AddonSettings(),
                CacheStore(paths.cache),
                http_open=opener,
            )
            self.assertIsInstance(result, PlayableResult)
            self.assertEqual(result.source.id, "keshet12_local_tvheadend")

    def test_channel12_failure_does_not_affect_another_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            opener = FakeOpen(*(socket.timeout() for _ in KESHET12_RELATIVE_PATHS))
            failed = resolve_keshet12(empty_channel(), paths, AddonSettings(), cache, http_open=opener)
            other = Channel(
                id="kan11",
                name="Kan 11",
                sources=[Source("kan", SourceType.DIRECT_HLS, url="https://example.com/kan.m3u8")],
            )
            other_result = SourceResolver(AddonSettings(), cache).resolve(other)
            self.assertIsInstance(failed, FailureResult)
            self.assertIsInstance(other_result, PlayableResult)
            self.assertEqual(other_result.source.id, "kan")

    def test_resolver_exception_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            with patch(
                "resources.lib.channels.keshet12._try_dynamic_paths",
                side_effect=RuntimeError("https://example.invalid/a.m3u8?ticket=secret"),
            ):
                result = resolve_keshet12(empty_channel(), paths, AddonSettings(), cache)
            self.assertIsInstance(result, FailureResult)
            self.assertEqual(result.category, FailureCategory.KESHET12_UNKNOWN_ERROR)
            self.assertIn("Other channels are unaffected", result.user_message)
            self.assertNotIn("secret", result.technical_details)

    def test_clear_channel12_cache_removes_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            cache.set_last_success("keshet12", "s1", "DIRECT_HLS")
            cache.set_channel12_success("s1", "DIRECT_HLS")
            cache.set_channel12_failure("keshet12_timeout", "timeout")
            cache.clear_channel12()
            state = cache.channel12_state()
            self.assertEqual(state["channel12_last_successful_source"], "")
            self.assertEqual(cache.channel_state("keshet12"), {})

    def test_diagnostics_mentions_dynamic_resolver_and_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            text = build_channel12_diagnostics(paths, empty_channel(), cache)
            self.assertIn("Resolver: dynamic public/free Mako entitlement", text)
            self.assertIn("Temporary ticket persistence: disabled", text)
            self.assertIn("Failure isolation: enabled", text)
            self.assertIn("channel12_override.json", text)

    def test_redaction_removes_query_credentials(self):
        redacted = redact_sensitive(
            "failed https://cdn.example/live.m3u8?hdnea=secret&token=other ticket=third"
        )
        self.assertNotIn("secret", redacted)
        self.assertNotIn("other", redacted)
        self.assertNotIn("third", redacted)
        self.assertIn("?<redacted>", redacted)


if __name__ == "__main__":
    unittest.main()
