import unittest

from resources.lib.config import default_paths
from resources.lib.registry import load_bundled_channels


class BundledChannelDataTests(unittest.TestCase):
    def test_channel16_has_verified_official_public_hls(self):
        channels, report = load_bundled_channels(default_paths())

        self.assertEqual(report.errors, [])
        channel16 = next((channel for channel in channels if channel.id == "channel16"), None)
        self.assertIsNotNone(channel16)
        source = next((source for source in channel16.sources if source.id == "channel16_official_hls"), None)
        self.assertIsNotNone(source)
        self.assertTrue(source.playable)
        self.assertEqual(source.url, "https://ch16israel-cdn.encoders.immergo.tv/2/streamPlaylist.m3u8")
        self.assertEqual(source.evidence_url, "https://ch16.co.il/player/channel/6a3448c2e20c91b5cd8c9da1")
        self.assertEqual(source.last_verified_at, "2026-10-19")
        self.assertEqual(source.headers, {})


if __name__ == "__main__":
    unittest.main()
