from __future__ import annotations

from typing import Dict

from .models import FailureResult, PlayableResult


def _header_suffix(headers: Dict[str, str]) -> str:
    if not headers:
        return ""
    encoded = "&".join(f"{key}={value}" for key, value in headers.items())
    return "|" + encoded


def resolve_to_kodi(handle: int, result: PlayableResult) -> None:
    import xbmcgui  # type: ignore
    import xbmcplugin  # type: ignore

    list_item = xbmcgui.ListItem(path=result.url + _header_suffix(result.headers))
    list_item.setProperty("IsPlayable", "true")
    if result.mime_type:
        list_item.setMimeType(result.mime_type)
        list_item.setContentLookup(False)
    if result.requires_inputstream_adaptive:
        list_item.setProperty("inputstream", "inputstream.adaptive")
        list_item.setProperty("inputstreamaddon", "inputstream.adaptive")
        if result.mime_type:
            list_item.setProperty("inputstream.adaptive.manifest_type", "mpd" if "dash" in result.mime_type else "hls")
    xbmcplugin.setResolvedUrl(handle, True, list_item)


def fail_to_kodi(handle: int, failure: FailureResult) -> None:
    import xbmcgui  # type: ignore
    import xbmcplugin  # type: ignore

    xbmcgui.Dialog().ok("Israeli Live TV Stable", failure.user_message)
    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())


def show_failure_dialog(failure: FailureResult) -> None:
    try:
        import xbmcgui  # type: ignore

        xbmcgui.Dialog().ok("Israeli Live TV Stable", failure.user_message)
    except Exception:
        print(failure.user_message)
