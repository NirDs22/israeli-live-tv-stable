# Install

## Install From Folder

1. Copy this repository folder into Kodi's addons directory, or package it as a ZIP with `addon.xml` at the ZIP root.
2. In Kodi, enable installing from unknown sources if needed.
3. Use `Install from zip file` or restart Kodi after copying the folder.
4. Open `Israeli Live TV Stable` from Video add-ons.

## Android TV Userdata

Kodi userdata is usually under one of these paths:

- `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/`
- `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/userdata/`

The addon data directory is:

`userdata/addon_data/plugin.video.israeli.live.tv.stable/`

Diagnostics shows the exact paths Kodi is using.

## Add User Sources

1. Run the addon once so it creates `user_sources.json`.
2. Open Diagnostics and note the exact user source path.
3. Copy or edit your legal user sources into that file.
4. Reopen the addon or run Diagnostics again to see validation errors.

## Configure TVHeadend

1. Open addon Settings.
2. Enable TVHeadend.
3. Optionally enable Prefer TVHeadend.
4. Run the addon once so it creates `tvheadend_mapping.json`.
5. Add channel URLs for your local TVHeadend instance.

## Debug Logging

Enable debug logging in addon settings and Kodi settings. Use Diagnostics for cache state and last playback errors.
