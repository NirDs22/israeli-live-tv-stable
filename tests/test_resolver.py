import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resources.lib.cache import CacheStore
from resources.lib.models import Channel, FailureResult, PlayableResult, Source, SourceType
from resources.lib.resolver import SourceResolver
from resources.lib.settings import AddonSettings


class ResolverTests(unittest.TestCase):
    def resolver(self, settings=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cache = CacheStore(Path(tmp.name) / "cache.json")
        return SourceResolver(settings or AddonSettings(), cache), cache

    def test_user_direct_preferred_before_bundled(self):
        resolver, _ = self.resolver()
        channel = Channel(
            id="kan11",
            name="Kan 11",
            sources=[
                Source("bundled", SourceType.DIRECT_HLS, priority=1, url="https://bundled/stream.m3u8"),
                Source("user", SourceType.DIRECT_HLS, priority=50, url="https://user/stream.m3u8", is_user_configured=True),
            ],
        )
        result = resolver.resolve(channel)
        self.assertIsInstance(result, PlayableResult)
        self.assertEqual(result.source.id, "user")

    def test_last_known_good_preferred_first(self):
        resolver, cache = self.resolver()
        cache.set_last_success("kan11", "bundled", "DIRECT_HLS")
        channel = Channel(
            id="kan11",
            name="Kan 11",
            sources=[
                Source("bundled", SourceType.DIRECT_HLS, priority=100, url="https://bundled/stream.m3u8"),
                Source("user", SourceType.DIRECT_HLS, priority=1, url="https://user/stream.m3u8", is_user_configured=True),
            ],
        )
        result = resolver.resolve(channel)
        self.assertIsInstance(result, PlayableResult)
        self.assertEqual(result.source.id, "bundled")

    def test_network_validation_skips_broken_primary(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cache = CacheStore(Path(tmp.name) / "cache.json")
        resolver = SourceResolver(AddonSettings(), cache, validate_network=True)
        channel = Channel(
            id="reshet13",
            name="Reshet 13",
            sources=[
                Source("primary", SourceType.DIRECT_HLS, priority=10, url="https://primary/stream.m3u8"),
                Source("fallback", SourceType.DIRECT_HLS, priority=30, url="https://fallback/stream.m3u8"),
            ],
        )

        def fake_check(source, timeout):
            return (source.id == "fallback", "ok" if source.id == "fallback" else "http_5xx")

        with patch("resources.lib.resolver.check_source", side_effect=fake_check):
            result = resolver.resolve(channel)

        self.assertIsInstance(result, PlayableResult)
        self.assertEqual(result.source.id, "fallback")
        self.assertEqual(cache.source_state("primary")["last_failure_category"], "http_5xx")

    def test_tvheadend_preference_behavior(self):
        resolver, _ = self.resolver(AddonSettings(prefer_tvheadend=True, tvheadend_enabled=True))
        channel = Channel(
            id="kan11",
            name="Kan 11",
            sources=[
                Source("user", SourceType.DIRECT_HLS, priority=1, url="https://user/stream.m3u8", is_user_configured=True),
                Source("tvh", SourceType.LOCAL_TVHEADEND, priority=20, url="http://tvh/stream"),
            ],
        )
        result = resolver.resolve(channel)
        self.assertIsInstance(result, PlayableResult)
        self.assertEqual(result.source.id, "tvh")

    def test_unavailable_source_message(self):
        resolver, _ = self.resolver()
        channel = Channel(
            id="keshet12",
            name="Keshet 12",
            sources=[Source("info", SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY, url="https://example.com")],
        )
        result = resolver.resolve(channel)
        self.assertIsInstance(result, FailureResult)
        self.assertIn("Direct playback is not bundled", result.user_message)


if __name__ == "__main__":
    unittest.main()
