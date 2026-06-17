import tempfile
import unittest
from pathlib import Path

from resources.lib.cache import CacheStore
from resources.lib.m3u import generate_m3u
from resources.lib.models import Channel, Source, SourceType
from resources.lib.resolver import SourceResolver
from resources.lib.settings import AddonSettings


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


if __name__ == "__main__":
    unittest.main()
