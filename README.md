# FocusFlow

A proprietary, local-first focus planner for GNOME, developed and distributed by TMP Inc.

Copyright © 2026 TMP Inc. All rights reserved. FocusFlow is proprietary software. Use, copying, modification, redistribution, and commercial distribution require written permission from TMP Inc.

FocusFlow combines a lightweight task list with focused Pomodoro sessions and a clear daily progress view. It is designed to feel at home on the GNOME desktop: keyboard-friendly, distraction-free, and fully usable without an account or network connection.

## Highlights

- Native GTK4 + libadwaita interface
- Local-only task persistence in `~/.local/share/com.tmp.FocusFlow/tasks.json`
- Focus, short break, and long break timer modes
- Daily completion and focus-minute stats
- Keyboard shortcuts and a compact, responsive layout
- Dark mode support inherited from GNOME
- Flatpak-ready with no network permission

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install PyGObject
python3 src/focusflow.py
```

System packages needed for PyGObject vary by distribution. On Fedora:

```bash
sudo dnf install python3-gobject gtk4 libadwaita
```

## Build the Flatpak

Install Flatpak and the GNOME SDK/runtime, then run:

```bash
flatpak install flathub org.gnome.Sdk//49 org.gnome.Platform//49
flatpak-builder --user --install --force-clean build-dir com.tmp.FocusFlow.yml
flatpak run com.tmp.FocusFlow
```

## Distribution notes

Before submitting to a software catalog, replace the placeholder developer contact in the metainfo file, add screenshots to `screenshots/`, and publish the source repository or release archive at a stable tag. Because FocusFlow is proprietary, confirm that the target catalog accepts proprietary applications and review its source-availability and licensing policies first.
