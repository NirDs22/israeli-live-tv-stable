from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IPTV_SIMPLE_ID = "pvr.iptvsimple"


@dataclass
class PVRSetupResult:
    ok: bool
    m3u_path: str
    channel_count: int = 0
    message: str = ""
    technical_details: str = ""
    manual_instructions: str = ""


def iptv_simple_manual_instructions(m3u_path: str) -> str:
    return (
        "Manual Kodi TV setup:\n\n"
        "1. Open Kodi Add-ons -> My add-ons -> PVR clients.\n"
        "2. Install and enable PVR IPTV Simple Client.\n"
        "3. Open PVR IPTV Simple Client settings.\n"
        "4. Set Location to Local path.\n"
        "5. Set M3U playlist path to:\n"
        f"{m3u_path}\n"
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


def enable_pvr_manager() -> tuple[bool, str]:
    try:
        response = _json_rpc("Settings.SetSettingValue", {"setting": "pvrmanager.enabled", "value": True})
        if "error" in response:
            return False, str(response["error"])
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


def reload_pvr() -> tuple[bool, str]:
    try:
        import xbmc  # type: ignore

        xbmc.executebuiltin("StopPVRManager")
        xbmc.executebuiltin("StartPVRManager")
        return True, "Kodi PVR manager reload requested."
    except Exception as exc:
        return False, f"Could not request PVR reload: {exc}"


def setup_kodi_tv(m3u_path: Path, channel_count: int) -> PVRSetupResult:
    path_text = str(m3u_path)
    manual = iptv_simple_manual_instructions(path_text)
    installed, status = iptv_simple_status()
    if not installed:
        return PVRSetupResult(
            ok=False,
            m3u_path=path_text,
            channel_count=channel_count,
            message="PVR IPTV Simple Client is not installed or not detectable.",
            technical_details=status,
            manual_instructions=manual,
        )

    steps: list[str] = [status]
    enabled_ok, enabled_msg = enable_iptv_simple()
    steps.append(enabled_msg)
    pvr_ok, pvr_msg = enable_pvr_manager()
    steps.append(pvr_msg)
    config_ok, config_msg = configure_iptv_simple(path_text)
    steps.append(config_msg)
    reload_ok, reload_msg = reload_pvr()
    steps.append(reload_msg)

    ok = config_ok
    message = (
        f"Kodi TV setup completed with {channel_count} channels. Open Kodi TV -> Channels."
        if ok
        else "Kodi TV setup could not be completed automatically."
    )
    return PVRSetupResult(
        ok=ok,
        m3u_path=path_text,
        channel_count=channel_count,
        message=message,
        technical_details="\n".join(steps),
        manual_instructions="" if ok else manual,
    )
