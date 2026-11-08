#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v flatpak-builder >/dev/null 2>&1; then
  echo "flatpak-builder is required. Install it from your distribution package manager." >&2
  exit 1
fi

flatpak-builder --user --install --force-clean build-dir com.tmp.FocusFlow.yml
flatpak run com.tmp.FocusFlow
