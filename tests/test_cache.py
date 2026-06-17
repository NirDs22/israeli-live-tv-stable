import tempfile
import time
import unittest
from pathlib import Path

from resources.lib.cache import CacheStore


class CacheTests(unittest.TestCase):
    def test_cache_ttl_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            cache.set_source_failure("s1", "network_timeout")
            self.assertEqual(cache.unhealthy_until_ttl("s1", 60), "network_timeout")
            self.assertIsNone(cache.unhealthy_until_ttl("s1", 0))

    def test_last_success_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            cache.set_last_success("kan11", "source1", "DIRECT_HLS")
            self.assertEqual(cache.last_known_source_id("kan11"), "source1")
            self.assertEqual(cache.channel_state("kan11")["last_successful_source_type"], "DIRECT_HLS")


if __name__ == "__main__":
    unittest.main()
