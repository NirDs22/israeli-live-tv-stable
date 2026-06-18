import unittest
from pathlib import Path
from unittest.mock import patch

from resources.lib.pvr import configure_iptv_simple_url, enable_pvr_manager, iptv_simple_manual_instructions, setup_kodi_tv


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

    def test_pvr_manager_invalid_params_is_friendly_optional_warning(self):
        with patch("resources.lib.pvr._json_rpc", return_value={"error": {"code": -32602, "message": "Invalid params."}}):
            ok, message = enable_pvr_manager()
        self.assertFalse(ok)
        self.assertIn("did not allow automatic PVR manager enabling", message)
        self.assertNotIn("-32602", message)

    def test_setup_succeeds_when_optional_pvr_manager_enable_fails(self):
        with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
            "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
        ), patch(
            "resources.lib.pvr.enable_pvr_manager",
            return_value=(False, "Kodi did not allow automatic PVR manager enabling. If TV is missing, enable PVR in Kodi settings."),
        ), patch("resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured")), patch(
            "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
        ):
            result = setup_kodi_tv(Path("/tmp/live.m3u"), 13)
        self.assertTrue(result.ok)
        self.assertIn("13 channels", result.message)
        self.assertIn("Optional step skipped", result.technical_details)
        self.assertNotIn("Invalid params", result.technical_details)

    def test_url_setup_uses_iptv_simple_remote_playlist_settings(self):
        settings = {}

        class FakeAddon:
            def __init__(self, id=None):
                self.id = id

            def setSetting(self, key, value):
                settings[key] = value

        with patch.dict("sys.modules", {"xbmcaddon": type("FakeModule", (), {"Addon": FakeAddon})}):
            ok, message = configure_iptv_simple_url("http://127.0.0.1:41555/playlist.m3u")
        self.assertTrue(ok)
        self.assertEqual(settings["m3uPathType"], "1")
        self.assertEqual(settings["m3uUrl"], "http://127.0.0.1:41555/playlist.m3u")
        self.assertIn("local playlist URL", message)

    def test_setup_prefers_playlist_url(self):
        with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
            "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
        ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
            "resources.lib.pvr.configure_iptv_simple_url", return_value=(True, "configured url")
        ) as configure_url, patch("resources.lib.pvr.configure_iptv_simple") as configure_file, patch(
            "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
        ):
            result = setup_kodi_tv(Path("/tmp/live.m3u"), 13, "http://127.0.0.1:41555/playlist.m3u")
        self.assertTrue(result.ok)
        configure_url.assert_called_once()
        configure_file.assert_not_called()

    def test_setup_falls_back_to_file_when_url_config_fails(self):
        with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
            "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
        ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
            "resources.lib.pvr.configure_iptv_simple_url", return_value=(False, "url failed")
        ), patch("resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured file")) as configure_file, patch(
            "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
        ):
            result = setup_kodi_tv(Path("/tmp/live.m3u"), 13, "http://127.0.0.1:41555/playlist.m3u")
        self.assertTrue(result.ok)
        self.assertIn("Fallback local file setup", result.technical_details)
        configure_file.assert_called_once()


if __name__ == "__main__":
    unittest.main()
