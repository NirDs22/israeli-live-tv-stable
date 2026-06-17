import tempfile
import unittest
from pathlib import Path

from resources.lib.cache import CacheStore
from resources.lib.config import RuntimePaths
from resources.lib.diagnostics import build_diagnostics
from resources.lib.models import Channel
from resources.lib.settings import AddonSettings


class DiagnosticsTests(unittest.TestCase):
    def test_diagnostics_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths = RuntimePaths(base, base / "channels.json", base / "remote_channels.json", base / "user_sources.json", base / "tvh.json", base / "cache.json", base / "out.m3u")
            report = build_diagnostics(paths, AddonSettings(), [Channel("kan11", "Kan 11")], ["bad config"], CacheStore(paths.cache), 2)
            text = report.as_text()
            self.assertIn("Kodi version:", text)
            self.assertIn("Channels loaded: 1", text)
            self.assertIn("User sources loaded: 2", text)
            self.assertIn("bad config", text)
            self.assertIn("Remote channel updates enabled:", text)


if __name__ == "__main__":
    unittest.main()
