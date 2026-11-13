# Jabra Evolve 30 II — hidraw0 protocol notes

Reverse-engineered from the device's HID report descriptor (`/sys/class/hidraw/hidraw0/device/report_descriptor`) and a live capture session (`captures/session1.log`).

## Reports observed on `/dev/hidraw0`

All reports are 3 bytes: `[report_id, byte1, byte2]`.

### Report ID `0x02` — Telephony page (HID Usage Page 0x0B)

Byte 1, bit 0 = **Hook Switch** (HID usage `0x20`). This is the **center call button**.

| Bytes | Meaning |
|---|---|
| `02 01 00` | Center button pressed (down) |
| `02 00 00` | Center button released (up) |

Hold duration is the time between press and release events. Short tap and long-hold both emit the same press/release pair — distinguish them in userspace by timing.

Other bits in this report (per the descriptor) cover Phone Mute (`0x2F`), Flash (`0x21`), Redial (`0x24`), Speed Dial (`0x50`), and the DTMF programmable keys (`0xB0`–`0xBB`). Not observed in capture because the device only exposes one physical telephony button.

### Report ID `0x01` — Consumer page (HID Usage Page 0x0C)

Byte 1, bits 0 and 1 = Volume Decrement (`0xEA`) / Volume Increment (`0xE9`).

| Bytes | Meaning |
|---|---|
| `01 01 00` | Volume Down |
| `01 02 00` | Volume Up |
| `01 00 00` | Release |

These also reach the evdev node (`event-if03`) as `KEY_VOLUMEDOWN` / `KEY_VOLUMEUP`, so they're already remappable through Input Remapper. We don't need them.

### Reports not observed

- Mic-mute button — likely emitted on the evdev side as `KEY_MICMUTE` and not on hidraw0, or on a different report ID we didn't trigger cleanly.
- The DTMF / numeric / additional vendor-specific reports listed in the descriptor (Report IDs `0x04`, `0x05`, `0x9A`, `0x9B`) — not exercised; not needed for the center-button hook.

## Implication for the project

To capture the center button, a userspace listener needs to:

1. Open `/dev/hidraw0` for read.
2. Read 3-byte chunks.
3. Match `report_id == 0x02`:
   - `byte1 & 0x01 == 1` → press event (start timer).
   - `byte1 & 0x01 == 0` → release event (stop timer).
4. Dispatch:
   - Short tap (release within ~500ms) → action A.
   - Long hold (release after threshold) → action B.
   - Or treat press/release as a hold-style PTT (key down on press, key up on release).

That's the listener architecture in `tools/jabra_button_listener.py` (next).
