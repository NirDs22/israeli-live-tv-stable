import tempfile
import unittest
from pathlib import Path

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
