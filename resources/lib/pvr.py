from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


IPTV_SIMPLE_ID = "pvr.iptvsimple"


@dataclass
class PVRSetupResult:
    ok: bool
    m3u_path: str
    channel_count: int = 0
    message: str = ""
    technical_details: str = ""
    manual_instructions: str = ""
    setup_mode: str = "unknown"
    instance_settings_path: str = ""
    backup_path: str = ""
    playlist_entry_count: int = 0


@dataclass
class InstanceRepairResult:
    ok: bool
    mode: str
    message: str
    path: str = ""
    backup_path: str = ""


def validate_generated_m3u(m3u_path: Path) -> tuple[bool, int, str]:
    try:
        if not m3u_path.exists():
            return False, 0, "Generated M3U file does not exist."
        text = m3u_path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("#EXTM3U"):
            return False, 0, "Generated M3U file is not a valid playlist."
        count = sum(1 for line in text.splitlines() if line.startswith("#EXTINF"))
        if count <= 0:
            return False, 0, "Generated M3U playlist has no channels."
        return True, count, f"Generated M3U playlist has {count} channels."
    except Exception as exc:
        return False, 0, f"Could not validate generated M3U file: {exc}"


def iptv_simple_manual_instructions(m3u_path: str, playlist_url: str = "") -> str:
    if playlist_url:
        location = "Remote path (Internet address)"
        playlist_step = f"5. Set M3U playlist URL to:\n{playlist_url}\n"
    else:
        location = "Local path"
        playlist_step = f"5. Set M3U playlist path to:\n{m3u_path}\n"
    return (
        "Manual Kodi TV setup:\n\n"
        "1. Open Kodi Add-ons -> My add-ons -> PVR clients.\n"
        "2. Install and enable PVR IPTV Simple Client.\n"
        "3. Open PVR IPTV Simple Client settings.\n"
        f"4. Set Location to {location}.\n"
        f"{playlist_step}"
        "6. Press OK.\n"
        "7. Restart Kodi, or disable and re-enable PVR IPTV Simple Client.\n"
        "8. Open Kodi TV -> Channels."
    )


def _json_rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
    import xbmc  # type: ignore

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(raw)
    except Exception:
        return {"error": {"message": raw}}


def iptv_simple_status() -> tuple[bool, str]:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=IPTV_SIMPLE_ID)
        version = addon.getAddonInfo("version")
        return True, f"installed ({version})"
    except Exception as exc:
        return False, f"not detected: {exc}"


def enable_iptv_simple() -> tuple[bool, str]:
    try:
        response = _json_rpc("Addons.SetAddonEnabled", {"addonid": IPTV_SIMPLE_ID, "enabled": True})
        if "error" in response:
            return False, str(response["error"])
        return True, "PVR IPTV Simple Client enabled."
    except Exception as exc:
        return False, f"Could not enable PVR IPTV Simple Client: {exc}"


def restart_iptv_simple_client() -> tuple[bool, str]:
    try:
        disable_response = _json_rpc("Addons.SetAddonEnabled", {"addonid": IPTV_SIMPLE_ID, "enabled": False})
        enable_response = _json_rpc("Addons.SetAddonEnabled", {"addonid": IPTV_SIMPLE_ID, "enabled": True})
        if "error" in disable_response or "error" in enable_response:
            return False, "Could not restart PVR IPTV Simple Client automatically."
        return True, "PVR IPTV Simple Client restarted."
    except Exception as exc:
        return False, f"Could not restart PVR IPTV Simple Client: {exc}"


def enable_pvr_manager() -> tuple[bool, str]:
    try:
        response = _json_rpc("Settings.SetSettingValue", {"setting": "pvrmanager.enabled", "value": True})
        if "error" in response:
            return False, "Kodi did not allow automatic PVR manager enabling. If TV is missing, enable PVR in Kodi settings."
        return True, "Kodi PVR manager enabled."
    except Exception as exc:
        return False, f"Could not enable Kodi PVR manager: {exc}"


def configure_iptv_simple(m3u_path: str) -> tuple[bool, str]:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=IPTV_SIMPLE_ID)
        addon.setSetting("m3uPathType", "0")
        addon.setSetting("m3uPath", m3u_path)
        addon.setSetting("startNum", "1")
        return True, "PVR IPTV Simple Client configured with generated M3U."
    except Exception as exc:
        return False, f"Could not configure PVR IPTV Simple Client: {exc}"


def verify_iptv_simple_local_file(m3u_path: str) -> tuple[bool, str]:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=IPTV_SIMPLE_ID)
        path_type = addon.getSetting("m3uPathType")
        configured_path = addon.getSetting("m3uPath")
        if path_type == "0" and configured_path == m3u_path:
            return True, "IPTV Simple local M3U settings verified."
        return False, "IPTV Simple settings did not reflect the generated M3U path."
    except Exception as exc:
        return False, f"Could not verify IPTV Simple settings: {exc}"


def iptv_simple_profile_dir() -> tuple[Path | None, str]:
    try:
        import xbmcaddon  # type: ignore
        import xbmcvfs  # type: ignore

        raw_path = xbmcaddon.Addon(id=IPTV_SIMPLE_ID).getAddonInfo("profile")
        translated = xbmcvfs.translatePath(raw_path)
        return Path(translated), "ok"
    except Exception as exc:
        return None, f"Could not locate IPTV Simple profile directory: {exc}"


def _find_instance_settings(profile_dir: Path) -> Path | None:
    files = sorted(profile_dir.glob("instance-settings-*.xml"), key=lambda item: item.stat().st_mtime, reverse=True)
    if files:
        return files[0]
    candidate = profile_dir / "instance-settings-1.xml"
    if profile_dir.exists():
        candidate.write_text("<settings version=\"2\">\n</settings>\n", encoding="utf-8")
        return candidate
    return None


def _setting_value(element: ElementTree.Element) -> str:
    if "value" in element.attrib:
        return element.attrib.get("value", "")
    return element.text or ""


def _set_setting_value(root: ElementTree.Element, setting_id: str, value: str) -> bool:
    for element in root.iter("setting"):
        if element.attrib.get("id") == setting_id:
            if "value" in element.attrib:
                element.set("value", value)
            else:
                element.text = value
            return True
    setting = ElementTree.SubElement(root, "setting")
    setting.set("id", setting_id)
    setting.set("value", value)
    return True


def _has_known_settings_shape(root: ElementTree.Element) -> bool:
    if root.tag != "settings":
        return False
    for element in root.iter("setting"):
        if "id" in element.attrib:
            return True
    return len(root) == 0


def repair_iptv_simple_instance_settings(m3u_path: str, profile_dir: Path | None = None) -> InstanceRepairResult:
    if profile_dir is None:
        profile_dir, message = iptv_simple_profile_dir()
        if profile_dir is None:
            return InstanceRepairResult(False, "manual fallback", message)

    if not profile_dir.exists() or not profile_dir.is_dir():
        return InstanceRepairResult(False, "manual fallback", "IPTV Simple profile directory does not exist.")

    try:
        settings_path = _find_instance_settings(profile_dir)
        if not settings_path:
            return InstanceRepairResult(False, "manual fallback", "Could not find or create IPTV Simple instance settings.")
        tree = ElementTree.parse(settings_path)
        root = tree.getroot()
        if not _has_known_settings_shape(root):
            return InstanceRepairResult(False, "manual fallback", "IPTV Simple instance settings format is unknown.", str(settings_path))

        backup_path = settings_path.with_suffix(settings_path.suffix + ".bak")
        shutil.copy2(settings_path, backup_path)

        _set_setting_value(root, "m3uPathType", "0")
        _set_setting_value(root, "m3uPath", m3u_path)
        _set_setting_value(root, "startNum", "1")
        tree.write(settings_path, encoding="utf-8", xml_declaration=True)

        verify_tree = ElementTree.parse(settings_path)
        values = {
            element.attrib.get("id", ""): _setting_value(element)
            for element in verify_tree.getroot().iter("setting")
        }
        if values.get("m3uPathType") != "0" or values.get("m3uPath") != m3u_path:
            return InstanceRepairResult(False, "manual fallback", "IPTV Simple instance settings validation failed.", str(settings_path), str(backup_path))
        return InstanceRepairResult(True, "instance repair", "IPTV Simple instance settings repaired.", str(settings_path), str(backup_path))
    except Exception as exc:
        return InstanceRepairResult(False, "manual fallback", f"Could not repair IPTV Simple instance settings: {exc}")


def configure_iptv_simple_url(playlist_url: str) -> tuple[bool, str]:
    try:
        import xbmcaddon  # type: ignore

        addon = xbmcaddon.Addon(id=IPTV_SIMPLE_ID)
        addon.setSetting("m3uPathType", "1")
        addon.setSetting("m3uUrl", playlist_url)
        addon.setSetting("startNum", "1")
        return True, f"PVR IPTV Simple Client configured with local playlist URL: {playlist_url}"
    except Exception as exc:
        return False, f"Could not configure PVR IPTV Simple Client URL: {exc}"


def reload_pvr() -> tuple[bool, str]:
    try:
        import xbmc  # type: ignore

        xbmc.executebuiltin("StopPVRManager")
        xbmc.executebuiltin("StartPVRManager")
        return True, "Kodi PVR manager reload requested."
    except Exception as exc:
        return False, f"Could not request PVR reload: {exc}"


def setup_kodi_tv(m3u_path: Path, channel_count: int, playlist_url: str = "") -> PVRSetupResult:
    path_text = str(m3u_path)
    manual = iptv_simple_manual_instructions(path_text)
    playlist_ok, playlist_entry_count, playlist_msg = validate_generated_m3u(m3u_path)
    if not playlist_ok:
        return PVRSetupResult(
            ok=False,
            m3u_path=path_text,
            channel_count=channel_count,
            message="Kodi TV repair could not continue because the generated playlist is not valid.",
            technical_details=playlist_msg,
            manual_instructions=manual,
            setup_mode="manual fallback",
            playlist_entry_count=playlist_entry_count,
        )
    installed, status = iptv_simple_status()
    if not installed:
        return PVRSetupResult(
            ok=False,
            m3u_path=path_text,
            channel_count=channel_count,
            message="PVR IPTV Simple Client is not installed or not detectable.",
            technical_details=playlist_msg + "\n" + status,
            manual_instructions=manual,
            setup_mode="manual fallback",
            playlist_entry_count=playlist_entry_count,
        )

    steps: list[str] = [playlist_msg, status]
    enabled_ok, enabled_msg = enable_iptv_simple()
    steps.append(enabled_msg)
    pvr_ok, pvr_msg = enable_pvr_manager()
    if pvr_ok:
        steps.append(pvr_msg)
    else:
        steps.append(f"Optional step skipped: {pvr_msg}")

    setup_mode = "manual fallback"
    instance_settings_path = ""
    backup_path = ""
    config_ok, config_msg = configure_iptv_simple(path_text)
    steps.append(config_msg)
    verified, verify_msg = verify_iptv_simple_local_file(path_text)
    steps.append(verify_msg)

    repair = repair_iptv_simple_instance_settings(path_text)
    steps.append(repair.message)
    instance_settings_path = repair.path
    backup_path = repair.backup_path
    config_ok = bool(config_ok and verified and repair.ok)
    if repair.ok:
        setup_mode = repair.mode
        restart_ok, restart_msg = restart_iptv_simple_client()
        steps.append(restart_msg)
    else:
        setup_mode = repair.mode

    reload_ok, reload_msg = reload_pvr()
    steps.append(reload_msg)

    ok = config_ok
    message = (
        "Kodi TV was repaired. Restart Kodi, wait 60 seconds, then open TV -> Channels."
        if ok
        else "Kodi TV repair could not be completed automatically. Open IPTV Simple settings and verify the playlist path manually."
    )
    return PVRSetupResult(
        ok=ok,
        m3u_path=path_text,
        channel_count=channel_count,
        message=message,
        technical_details="\n".join(steps),
        manual_instructions="" if ok else manual,
        setup_mode=setup_mode,
        instance_settings_path=instance_settings_path,
        backup_path=backup_path,
        playlist_entry_count=playlist_entry_count,
    )
