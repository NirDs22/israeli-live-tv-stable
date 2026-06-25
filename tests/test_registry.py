import tempfile
import unittest
from pathlib import Path

from resources.lib.config import RuntimePaths, ensure_user_files
from resources.lib.registry import load_registry
from resources.lib.settings import AddonSettings
from resources.lib.utils import write_json
from resources.lib.utils import resolve_addon_asset


class RegistryTests(unittest.TestCase):
    def paths(self, tmp: str) -> RuntimePaths:
        base = Path(tmp)
        bundled = base / "channels.json"
        write_json(
            bundled,
            {
                "channels": [
                    {
                        "id": "kan11",
                        "name": "Kan 11",
                        "sources": [
                            {
                                "id": "kan11_info",
                                "type": "OFFICIAL_WEB_PAGE_INFO_ONLY",
                                "enabled": True,
                                "url": "https://example.com",
                            }
                        ],
                    }
                ]
            },
        )
        return RuntimePaths(base, bundled, base / "remote_channels.json", base / "user_sources.json", base / "tvh.json", base / "cache.json", base / "out.m3u")

    def test_channel_json_parsing_and_user_source_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            ensure_user_files(paths)
            write_json(
                paths.user_sources,
                {
                    "channels": {
                        "kan11": [
                            {
                                "id": "user_hls",
                                "type": "DIRECT_HLS",
                                "priority": 1,
                                "enabled": True,
                                "url": "https://example.com/live.m3u8",
                            }
                        ]
                    }
                },
            )
            registry = load_registry(paths, AddonSettings())
            channel = registry.get("kan11")
            self.assertIsNotNone(channel)
            self.assertEqual(registry.user_source_count, 1)
            self.assertTrue(any(source.id == "user_hls" and source.is_user_configured for source in channel.sources))

    def test_invalid_user_config_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            ensure_user_files(paths)
            paths.user_sources.write_text("[bad shape]", encoding="utf-8")
            registry = load_registry(paths, AddonSettings())
            self.assertEqual(len(registry.channels), 1)
            self.assertTrue(registry.validation.errors)

    def test_bad_sources_shape_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            write_json(paths.bundled_channels, {"channels": [{"id": "bad", "name": "Bad", "sources": {}}]})
            registry = load_registry(paths, AddonSettings())
            self.assertEqual(registry.channels, [])
            self.assertTrue(registry.validation.errors)

    def test_relative_channel_logo_resolves_inside_addon(self):
        resolved = resolve_addon_asset("resources/data/logos/kan11.png")
        self.assertTrue(Path(resolved).is_absolute())
        self.assertTrue(resolved.endswith("resources/data/logos/kan11.png"))

    def test_retired_channels_are_filtered_even_if_config_contains_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(tmp)
            write_json(
                paths.bundled_channels,
                {
                    "channels": [
                        {"id": "kan11", "name": "Kan 11", "sources": []},
                        {"id": "makan33", "name": "Makan 33", "sources": []},
                        {"id": "ynet_live", "name": "Ynet Live", "sources": []},
                    ]
                },
            )
            registry = load_registry(paths, AddonSettings(remote_config_enabled=False))
            self.assertEqual([channel.id for channel in registry.channels], ["kan11"])


if __name__ == "__main__":
    unittest.main()
