import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resources.lib.cache import CacheStore
from resources.lib.channels.keshet12 import (
    build_channel12_diagnostics,
    channel12_override_path,
    disable_channel12_override,
    load_channel12_override,
    resolve_keshet12,
)
from resources.lib.config import RuntimePaths
from resources.lib.models import Channel, FailureCategory, FailureResult, PlayableResult, Source, SourceType
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

    def test_success_updates_channel12_cache_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            channel = Channel(
                id="keshet12",
                name="Keshet 12",
                sources=[Source("s1", SourceType.DIRECT_HLS, url="https://example.com/a.m3u8")],
            )
            result = resolve_keshet12(channel, paths, AddonSettings(), cache)
            self.assertIsInstance(result, PlayableResult)
            state = cache.channel12_state()
            self.assertEqual(state["channel12_last_successful_source"], "s1")
            self.assertEqual(state["channel12_last_failure_reason"], "")

    def test_resolver_exception_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            channel = Channel(id="keshet12", name="Keshet 12", sources=[])
            with patch("resources.lib.channels.keshet12.SourceResolver.resolve", side_effect=RuntimeError("boom")):
                result = resolve_keshet12(
                    channel,
                    paths,
                    AddonSettings(),
                    cache,
                    mode="normal",
                )
            self.assertIsInstance(result, FailureResult)
            self.assertEqual(result.category, FailureCategory.KESHET12_NO_PLAYABLE_SOURCE)
            self.assertIn("Other channels are unaffected", result.user_message)

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

    def test_diagnostics_mentions_override_and_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = paths_for(tmp)
            cache = CacheStore(paths.cache)
            channel = Channel(id="keshet12", name="Keshet 12", sources=[])
            text = build_channel12_diagnostics(paths, channel, cache)
            self.assertIn("Failure isolation: enabled", text)
            self.assertIn("channel12_override.json", text)


if __name__ == "__main__":
    unittest.main()
