import unittest
from pathlib import Path
from unittest.mock import patch

from resources.lib.pvr import iptv_simple_manual_instructions, setup_kodi_tv


class PVRTests(unittest.TestCase):
    def test_manual_instructions_include_m3u_path(self):
        text = iptv_simple_manual_instructions("/tmp/live.m3u")
        self.assertIn("/tmp/live.m3u", text)
        self.assertIn("PVR IPTV Simple Client", text)
        self.assertIn("TV -> Channels", text)

    def test_setup_handles_missing_iptv_simple_without_crashing(self):
        with patch("resources.lib.pvr.iptv_simple_status", return_value=(False, "not detected")):
            result = setup_kodi_tv(Path("/tmp/live.m3u"), 12)
        self.assertFalse(result.ok)
        self.assertIn("not installed", result.message)
        self.assertIn("/tmp/live.m3u", result.manual_instructions)

    def test_setup_success_when_configuration_succeeds(self):
        with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
            "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
        ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
            "resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured")
        ), patch("resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")):
            result = setup_kodi_tv(Path("/tmp/live.m3u"), 12)
        self.assertTrue(result.ok)
        self.assertIn("12 channels", result.message)
        self.assertEqual(result.manual_instructions, "")


if __name__ == "__main__":
    unittest.main()
