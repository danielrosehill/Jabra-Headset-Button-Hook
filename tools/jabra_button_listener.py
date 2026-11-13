#!/usr/bin/python3
"""Listen on /dev/hidraw0 for the Jabra Evolve 30 II center button and
emit a configurable key on a virtual keyboard (uinput).

Protocol (see docs/hid-protocol.md):
    Report ID 0x02, byte 1 bit 0 = Hook Switch.
    02 01 00  -> press
    02 00 00  -> release

Modes:
    --mode ptt      key DOWN on press, key UP on release   (push-to-talk)
    --mode tap      single key tap on each release         (down+up together)
    --mode toggle   alternate key tap with --tap-other on each press

Default key is F13 (keycode 183) which is unused by virtually every desktop
app — safe trigger for transcription / dictation tools.

Requires python3-evdev (Debian/Ubuntu package). Must have rw on /dev/uinput
(typically via udev ACL — usually granted to the local seat user out of the box).
"""
from __future__ import annotations
import argparse, os, sys, time

from evdev import UInput, ecodes as e

HOOK_REPORT_ID = 0x02
HOOK_BIT = 0x01
LONG_PRESS_THRESHOLD_S = 0.500


def resolve_key(name: str) -> int:
    """Accept either an integer keycode or a KEY_* name."""
    s = name.strip()
    if s.isdigit():
        return int(s)
    if not s.startswith("KEY_"):
        s = "KEY_" + s.upper()
    code = getattr(e, s, None)
    if code is None:
        raise SystemExit(f"unknown key: {name}")
    return code


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="/dev/hidraw0")
    p.add_argument("--mode", choices=["ptt", "tap", "toggle"], default="ptt")
    p.add_argument("--key", default="F13", help="key for ptt/tap/toggle (name or numeric keycode)")
    p.add_argument("--tap-other", default=None, help="alternate key for toggle mode")
    p.add_argument("--threshold", type=float, default=LONG_PRESS_THRESHOLD_S)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    primary = resolve_key(args.key)
    secondary = resolve_key(args.tap_other) if args.tap_other else None

    keys = [primary] + ([secondary] if secondary else [])
    ui = UInput({e.EV_KEY: keys}, name="jabra-button-hook")

    fd = os.open(args.device, os.O_RDONLY)
    if args.verbose:
        print(f"[jabra-listener] reading {args.device}, mode={args.mode}, key={args.key}", flush=True)

    pressed_at: float | None = None
    toggle_use_secondary = False

    def emit_tap(code: int) -> None:
        ui.write(e.EV_KEY, code, 1); ui.syn()
        ui.write(e.EV_KEY, code, 0); ui.syn()

    while True:
        data = os.read(fd, 64)
        if len(data) < 2 or data[0] != HOOK_REPORT_ID:
            continue
        is_down = bool(data[1] & HOOK_BIT)

        if is_down and pressed_at is None:
            pressed_at = time.monotonic()
            if args.verbose:
                print("[jabra-listener] press", flush=True)
            if args.mode == "ptt":
                ui.write(e.EV_KEY, primary, 1); ui.syn()
            elif args.mode == "toggle":
                code = secondary if (toggle_use_secondary and secondary) else primary
                emit_tap(code)
                if secondary:
                    toggle_use_secondary = not toggle_use_secondary

        elif not is_down and pressed_at is not None:
            held = time.monotonic() - pressed_at
            pressed_at = None
            if args.verbose:
                print(f"[jabra-listener] release after {held*1000:.0f}ms", flush=True)
            if args.mode == "ptt":
                ui.write(e.EV_KEY, primary, 0); ui.syn()
            elif args.mode == "tap":
                emit_tap(primary)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        pass
