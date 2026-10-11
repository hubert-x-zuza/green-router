#!/bin/sh
# Install (or reinstall) the hourly air-quality archiver as a macOS launchd user agent.
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/pl.zdrowatrasa.air.plist"
mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
sed "s#__REPO__#$REPO#g" "$REPO/ops/pl.zdrowatrasa.air.plist.template" > "$PLIST"
launchctl bootout "gui/$(id -u)/pl.zdrowatrasa.air" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl print "gui/$(id -u)/pl.zdrowatrasa.air" | head -5
echo "installed: $PLIST   (uninstall: launchctl bootout gui/$(id -u)/pl.zdrowatrasa.air)"
