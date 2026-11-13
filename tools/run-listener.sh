#!/usr/bin/env bash
# Run the Jabra button listener with the workstation's chosen binding:
#   center button = F13 (push-to-talk semantics — F13 down on press, F13 up on release)
#
# F13 is keycode 183 in Linux. F13 is unused by virtually every desktop
# application, which makes it a safe trigger key for transcription / dictation
# tools that listen for a single hotkey.
#
# Listener emits keystrokes via its own uinput virtual keyboard (python-evdev),
# so no ydotool / wtype dependency is required.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$REPO_DIR/tools/jabra_button_listener.py" \
    --mode ptt \
    --key F13 \
    --verbose \
    "$@"
