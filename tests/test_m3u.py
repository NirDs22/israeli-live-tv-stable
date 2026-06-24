import tempfile
import unittest
from pathlib import Path

from resources.lib.cache import CacheStore
from resources.lib.m3u import generate_m3u
from resources.lib.models import Channel, Source, SourceType
from resources.lib.resolver import SourceResolver
from resources.lib.settings import AddonSettings
from resources.lib.utils import repo_root


class M3UTests(unittest.TestCase):
    def test_m3u_excludes_info_only_disabled_and_missing_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            resolver = SourceResolver(AddonSettings(), cache)
            channels = [
                Channel("playable", "Playable", tvg_id="p1", sources=[Source("s1", SourceType.DIRECT_HLS, url="https://example.com/a.m3u8")]),
                Channel("info", "Info", sources=[Source("i1", SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY, url="https://example.com")]),
                Channel("disabled", "Disabled", sources=[Source("d1", SourceType.DISABLED, enabled=False)]),
                Channel("empty", "Empty", sources=[Source("e1", SourceType.DIRECT_HLS, url="")]),
            ]
            out = Path(tmp) / "out.m3u"
            count = generate_m3u(channels, resolver, out)
            text = out.read_text(encoding="utf-8")
            self.assertEqual(count, 1)
            self.assertIn("Playable", text)
            self.assertNotIn("Info", text)
            self.assertNotIn("Disabled", text)
            self.assertNotIn("Empty", text)

    def test_m3u_preserves_channel_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            resolver = SourceResolver(AddonSettings(), cache)
            channels = [
                Channel("one", "One", sources=[Source("one_hls", SourceType.DIRECT_HLS, url="https://example.com/one.m3u8")]),
                Channel("two", "Two", sources=[Source("two_hls", SourceType.DIRECT_HLS, url="https://example.com/two.m3u8")]),
            ]
            out = Path(tmp) / "out.m3u"
            generate_m3u(channels, resolver, out)
            text = out.read_text(encoding="utf-8")
            self.assertLess(text.index("One"), text.index("Two"))

    def test_m3u_resolves_bundled_logo_to_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            resolver = SourceResolver(AddonSettings(), cache)
            channel = Channel(
                "playable",
                "Playable",
                logo="resources/data/logos/kan11.png",
                sources=[Source("s1", SourceType.DIRECT_HLS, url="https://example.com/a.m3u8")],
            )
            out = Path(tmp) / "out.m3u"
            generate_m3u([channel], resolver, out)
            text = out.read_text(encoding="utf-8")
            expected = repo_root() / "resources" / "data" / "logos" / "kan11.png"
            self.assertIn(f'tvg-logo="{expected}"', text)


if __name__ == "__main__":
    unittest.main()
