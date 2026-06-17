import tempfile
import unittest
from pathlib import Path

from resources.lib.cache import CacheStore
from resources.lib.config import RuntimePaths, ensure_user_files
from resources.lib.registry import load_registry
from resources.lib.remote_config import load_remote_channels_if_valid, remote_cache_fresh
from resources.lib.settings import AddonSettings
from resources.lib.utils import write_json


class RemoteConfigTests(unittest.TestCase):
    def paths(self, tmp: str) -> RuntimePaths:
        base = Path(tmp)
        bundled = base / "channels.json"
        write_json(
            bundled,
            {
                "channels": [
                    {
                        "id": "bundled",
                        "name": "Bundled",
                        "sources": [{"id": "bundled_info", "type": "OFFICIAL_WEB_PAGE_INFO_ONLY", "url": "https://example.com"}],
                    }
                ]
            },
        )
        return RuntimePaths(base, bundled, base / "remote_channels.json", base / "user_sources.json", base / "tvh.json", base / "cache.json", base / "out.m3u")

    def test_remote_channels_override_bundled_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            ensure_user_files(paths)
            write_json(
                paths.remote_channels,
                {
                    "channels": [
                        {
                            "id": "remote",
                            "name": "Remote",
                            "sources": [{"id": "remote_hls", "type": "DIRECT_HLS", "url": "https://example.com/live.m3u8"}],
                        }
                    ]
                },
            )
            registry = load_registry(paths, AddonSettings())
            self.assertIsNotNone(registry.get("remote"))
            self.assertIsNone(registry.get("bundled"))

    def test_invalid_remote_falls_back_to_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            ensure_user_files(paths)
            write_json(paths.remote_channels, {"channels": {"bad": "shape"}})
            payload, report = load_remote_channels_if_valid(paths)
            self.assertIsNone(payload)
            self.assertTrue(report.errors)
            registry = load_registry(paths, AddonSettings())
            self.assertIsNotNone(registry.get("bundled"))

    def test_remote_cache_ttl(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(Path(tmp) / "cache.json")
            self.assertFalse(remote_cache_fresh(cache, 60))
            data = cache.load()
            data.setdefault("metadata", {})["remote_channels_checked_at_epoch"] = 9999999999
            cache.save(data)
            self.assertTrue(remote_cache_fresh(cache, 60))


if __name__ == "__main__":
    unittest.main()
