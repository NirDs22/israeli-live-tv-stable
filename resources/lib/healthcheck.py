from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Tuple

from .models import FailureCategory, Source, SourceType


def check_source(source: Source, timeout: int = 5) -> Tuple[bool, str]:
    if not source.enabled:
        return False, FailureCategory.SOURCE_DISABLED.value
    if not source.url:
        return False, FailureCategory.SOURCE_NOT_CONFIGURED.value
    if source.type == SourceType.OFFICIAL_WEB_PAGE_INFO_ONLY:
        return False, FailureCategory.SOURCE_INFO_ONLY.value
    if source.type == SourceType.DISABLED:
        return False, FailureCategory.SOURCE_DISABLED.value

    request = urllib.request.Request(source.url, method="GET", headers=source.headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status == 403:
                return False, FailureCategory.HTTP_403.value
            if status == 404:
                return False, FailureCategory.HTTP_404.value
            if status >= 500:
                return False, FailureCategory.HTTP_5XX.value
            sample = response.read(512)
            if source.type in {SourceType.DIRECT_HLS, SourceType.LOCAL_M3U} and b"#EXTM3U" not in sample:
                return False, FailureCategory.MANIFEST_INVALID.value
            if source.type == SourceType.DIRECT_DASH and b"<MPD" not in sample:
                return False, FailureCategory.MANIFEST_INVALID.value
            return True, "ok"
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return False, FailureCategory.HTTP_403.value
        if exc.code == 404:
            return False, FailureCategory.HTTP_404.value
        if exc.code >= 500:
            return False, FailureCategory.HTTP_5XX.value
        return False, FailureCategory.UNKNOWN_ERROR.value
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            return False, FailureCategory.NETWORK_TIMEOUT.value
        return False, FailureCategory.DNS_ERROR.value
    except TimeoutError:
        return False, FailureCategory.NETWORK_TIMEOUT.value
    except Exception:
        return False, FailureCategory.UNKNOWN_ERROR.value
