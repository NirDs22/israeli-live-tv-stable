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

    def test_channel12_cache_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            cache.set_channel12_success("source12", "DIRECT_HLS")
            cache.set_channel12_failure("keshet12_timeout", "timed out")
            state = cache.channel12_state()
            self.assertEqual(state["channel12_last_successful_source"], "source12")
            self.assertEqual(state["channel12_last_failure_reason"], "keshet12_timeout")
            self.assertEqual(state["channel12_last_failure_details"], "timed out")


if __name__ == "__main__":
    unittest.main()
