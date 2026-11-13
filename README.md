# Jabra-Headset-Button-Hook

Capture the center call-control button on a Jabra Evolve 30 II USB headset on Linux and map it to a system hotkey (target use: push-to-talk / transcription trigger).

## Goal

Tap the center button on the headset → fire a configurable action (ydotool keystroke, dbus call, shell command). The button currently produces an audible click in the earcup (firmware-side feedback) but is invisible to evdev tools like Input Remapper.

## Hardware

- **Model**: Jabra Evolve 30 II (wired USB)
- **USB ID**: `0b0e:0314` (GN Audio A/S)
- **Host**: Ubuntu 25.10 / KDE Plasma 6 / Wayland workstation

## What we figured out

Single evdev node is exposed at:

```
/dev/input/by-id/usb-GN_Audio_A_S_Jabra_EVOLVE_30_II_<serial>-event-if03
```

`evtest` capabilities on that node:

- `KEY_VOLUMEUP`, `KEY_VOLUMEDOWN`
- `KEY_MICMUTE`
- `BTN_6`
- `KEY_NUMERIC_0`–`9`, `KEY_NUMERIC_STAR`, `KEY_NUMERIC_POUND`
- `LED_MUTE`

The center call/hook button is **not** in that list. It does not surface on evdev at all, which is why Input Remapper never sees it.

One hidraw node is exposed:

```
/dev/hidraw0   (HID_NAME=GN Audio A/S Jabra EVOLVE 30 II)
```

## Why the button is invisible to evdev

The center button is the HID telephony hook-switch (call answer / end), reported on the HID telephony usage page. The kernel's `hid-generic` driver consumes that report internally — it drives sidetone and the in-cup click feedback — but does not translate it into an evdev key event. There is no mainline `hid-jabra` driver that re-routes telephony usages to evdev.

Consequence: udev `hwdb` scancode remapping cannot help, because no scancode ever reaches userspace through evdev for this button.

## Approach options

1. **Read `/dev/hidraw0` directly.** The HID report for the call button still reaches hidraw. A small daemon can open hidraw0, watch for the call-control report bytes, and dispatch an action (ydotool keypress, dbus signal, shell). This is the path most open-source Jabra-button projects on Linux take. **Chosen path.**
2. **Jabra's official Linux SDK** (`libjabra`). Closed-source `.deb` from Jabra, exposes call-control via a daemon. Heavier than needed for one button.
3. **udev hwdb remap.** Not viable — the kernel never emits an evdev scancode for this button.

## Status

- [x] Capture raw HID reports — see `captures/session1.log` and `docs/hid-protocol.md`.
- [x] Identify the center-button signature: **Report ID `0x02`, byte 1 bit 0** (HID Telephony Hook Switch). Press = `02 01 00`, release = `02 00 00`.
- [x] Listener written: `tools/jabra_button_listener.py` (modes: `ptt`, `tap-hold`, `toggle`; defaults dispatch via ydotool).
- [x] udev rule installed: `udev/70-jabra-hidraw.rules` → `/etc/udev/rules.d/`. ACL now grants the logged-in user rw on `/dev/hidraw0` automatically (`getfacl` confirms `user:<you>:rw-`). No sudo needed for the listener.
- [x] Listener verified end-to-end on the workstation. Captured a real press/release pair:
  - `[jabra-listener] press`
  - `[jabra-listener] release after 3392ms`
- [x] Binding decided: **center button → F13** (PTT semantics — F13 down on press, F13 up on release). F13 = keycode 183, unused by virtually all desktop apps; safe trigger key for transcription / dictation tools.
- [x] Volume Up / Volume Down disabled at the udev hwdb layer (`hwdb/61-jabra-evolve-30-ii.hwdb`). Scancodes `c00e9` and `c00ea` mapped to `reserved` for this device only. Mic-mute deliberately left alone.
- [x] Listener emits F13 directly via its own uinput virtual keyboard (`python3-evdev`), so no `ydotool` / `wtype` dependency. (First implementation tried ydotool but the installed fork only does press+release atoms — no separate down/up — and parsed `key 183:1` as a press of KEY_1 instead of F13. The native uinput path is simpler and gives true PTT.)
- [x] Wrapper `tools/run-listener.sh` invokes the listener in PTT mode with key=F13.
- [x] systemd `--user` service installed and enabled (`systemd/jabra-button-hook.service` → `~/.config/systemd/user/`). Auto-starts with the graphical session.

## Final layout

```
hwdb/61-jabra-evolve-30-ii.hwdb     -> /etc/udev/hwdb.d/    (disable vol+/vol-)
udev/70-jabra-hidraw.rules          -> /etc/udev/rules.d/   (ACL for /dev/hidraw0)
systemd/jabra-button-hook.service   -> ~/.config/systemd/user/  (auto-start listener)
tools/run-listener.sh                                       (wrapper invoking the listener)
tools/jabra_button_listener.py                              (the listener itself)
tools/capture_hidraw.py                                     (debug helper)
docs/hid-protocol.md                                        (decoded protocol)
captures/                                                   (capture logs as evidence)
```

## Reapplying the install on a fresh machine

```bash
sudo cp udev/70-jabra-hidraw.rules /etc/udev/rules.d/
sudo cp hwdb/61-jabra-evolve-30-ii.hwdb /etc/udev/hwdb.d/
sudo systemd-hwdb update
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw
sudo udevadm trigger --action=change --subsystem-match=input

mkdir -p ~/.config/systemd/user
cp systemd/jabra-button-hook.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jabra-button-hook.service
```

Prereqs:
- `python3-evdev` (Debian/Ubuntu: `sudo apt install python3-evdev`).
- `/dev/uinput` writable by your user. Most distros grant this via the `uaccess` udev tag for the local seat user; if not, add a udev rule.

## Verifying the keystroke

The listener's virtual keyboard appears as a Linux input device named `jabra-button-hook`. To watch it live:

```bash
DEV=$(for d in /sys/class/input/event*; do n=$(cat $d/device/name 2>/dev/null); [ "$n" = jabra-button-hook ] && basename $d; done)
sudo evtest /dev/input/$DEV
# Press the headset center button — should print KEY_F13 value=1 then value=0.
```

To bind F13 to an action, configure your transcription / dictation tool (or KDE Plasma global shortcuts under System Settings → Shortcuts) to trigger on F13.

## Notes from testing

- **Chrome holds `/dev/hidraw0` open** while it's running (WebHID, for call-control integration with web-meeting apps). This is a *non-issue* — the kernel multicasts hidraw reports to every reader, so our listener and Chrome both get a copy. No need to fight Chrome for the device.
- The listener handles concurrent readers transparently. If you stop seeing events while debugging, check `fuser /dev/hidraw0` to confirm what else has it open, but don't kill Chrome for it.
- **Volume Up/Down also surface on hidraw0** as Report ID `0x01` (Consumer page bits) in addition to evdev. We ignore those — they're already remappable through Input Remapper.
- The mic-mute and short single-tap of the center button were not seen on hidraw0 during the capture session — they may go through a different report path or our timing missed them. Doesn't affect the project: the press/release pair on Report ID `0x02` is sufficient.

## Quick test (after installing the udev rule)

```bash
./tools/jabra_button_listener.py --mode ptt --verbose
# tap the center button — should print press/release lines
```

## Why hidraw and not evdev

The center button is the HID Telephony hook-switch. The kernel's `hid-generic` driver consumes that usage page internally (it drives sidetone and the in-cup click) and does **not** translate it into evdev key events. So Input Remapper, `xbindkeys`, and udev `hwdb` scancode remaps are all blind to it. Reading hidraw directly is the only path that works without writing a kernel driver.

Volume Up / Volume Down / Mic-Mute *do* reach evdev (`event-if03` exposes `KEY_VOLUMEUP`, `KEY_VOLUMEDOWN`, `KEY_MICMUTE`) — those are already remappable through normal tooling and are out of scope for this project.

## References to chase

- GitHub search: `jabra hidraw call control`, `dolauer/jabra-headset-controls`
- Linux HID telephony usage page documentation
- ydotool docs (already installed on this workstation)
- [Watchdog0x/jLink](https://github.com/Watchdog0x/jLink) — "Jabra Direct for Linux" (TUI for device management, firmware updates, pairing). Built on Jabra's closed-source `libjabra` C SDK. **Not useful for this project** — it targets the Bluetooth dongle (Link 380 + Evolve2 85) scenario and doesn't expose button events to userspace. Worth bookmarking only for firmware updates.
