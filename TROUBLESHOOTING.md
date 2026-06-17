# Troubleshooting

## Channel Unavailable

The channel has no configured playable source. Add a legal source to `user_sources.json` or configure a local TVHeadend mapping.

## inputstream.adaptive Missing

Some DASH/HLS sources may require `inputstream.adaptive`. Install and enable it from Kodi's add-on repository. Diagnostics shows whether it is detected.

## User Source Invalid

Bad JSON is ignored so the addon can keep running. Open Diagnostics and check `Config validation errors`.

Common mistakes:

- `channels` is missing.
- A channel entry is not a list.
- A source is missing `id` or `type`.
- `headers` is not an object.

## TVHeadend Not Configured

If TVHeadend is preferred but no mapping exists, playback will explain:

`Local TVHeadend is not configured. Add a mapping in tvheadend_mapping.json or disable TVHeadend preference.`

Add a valid mapping or disable the TVHeadend preference.

## M3U Empty

The M3U includes only playable configured/legal sources. Info-only pages, disabled sources, and missing URLs are excluded.

Add a legal user source or TVHeadend mapping, then regenerate M3U from Diagnostics.

## Kodi TV Menu Is Empty

Run `Setup Kodi TV` again from the addon. If automatic setup fails, configure `PVR IPTV Simple Client` manually with the generated M3U path.

Also check:

- PVR IPTV Simple Client is installed and enabled.
- Kodi PVR is enabled.
- The generated M3U is not empty.
- Restart Kodi after changing IPTV Simple settings.

## IPTV Simple Not Installed

Install it from Kodi:

`Add-ons -> My add-ons -> PVR clients -> PVR IPTV Simple Client`

Then run `Setup Kodi TV` again.

## Kodi Freezes Or UI Is Slow

V1 does not perform network calls while opening the main menu or channel list. If Kodi is slow:

- Disable broken user sources.
- Lower timeout settings.
- Clear cache from Diagnostics.
- Check Kodi logs for platform-level playback problems.

## Logs

Kodi logs are platform dependent. On Android TV they are usually inside Kodi's app data directory. Enable Kodi debug logging and addon debug logging before reproducing the issue.
