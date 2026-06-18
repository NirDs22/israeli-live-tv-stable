# Daily Channel Maintenance

The addon stays fast because Kodi does not search the web or test every channel during normal use. Link checking runs outside Kodi.

## What Runs Daily

GitHub Actions runs `tools/check_channels.py` every day around 01:00 Israel time. GitHub cron uses UTC, so the workflow runs at both 22:00 and 23:00 UTC to cover Israel standard time and daylight saving time.

The job:

- Runs the Python tests.
- Checks bundled `DIRECT_HLS` and `DIRECT_DASH` sources.
- Promotes a working fallback if a primary source fails.
- Tests reviewed candidates from `resources/data/channel_candidates.json`.
- Opens a pull request for safe metadata changes.
- Opens or updates an issue when broken sources still need investigation.

## Replacement Search Policy

If any source breaks, replacement search is needed even when a fallback still works. This prevents the addon from slowly running out of links.

New links may be used only when they are legal, public, free, and backed by evidence. Do not add piracy playlists, paid TV channels, protected APIs, DRM bypasses, fake headers, cookies, tokens, device IDs, or private app endpoints.

## Candidate Links

Put reviewed candidates in `resources/data/channel_candidates.json`. Each candidate must include:

- `id`
- `type`
- `priority`
- `enabled`
- `url`
- `headers`
- `mime_type`
- `requires_inputstream_adaptive`
- `evidence_url`
- `notes`

The checker adds valid candidates as lower-priority fallbacks first. It does not silently make new links primary unless the fallback promotion rule later proves that source is the best working option.

## Local Commands

Check links and write reports:

```bash
python3 tools/check_channels.py
```

Promote working fallbacks and add reviewed candidates:

```bash
python3 tools/check_channels.py --apply-fallbacks --apply-candidates
```

Fail the command when any checked source is broken:

```bash
python3 tools/check_channels.py --fail-on-broken
```

Reports are written to:

- `channel-health-report.json`
- `channel-health-report.md`

## Codex Automation

The Codex daily automation should inspect the health report, investigate broken or weak channels, search only allowed legal/public/official sources, and prepare a pull request when it finds a safe replacement. If it cannot find one, it should leave a clear report instead of adding questionable links.
