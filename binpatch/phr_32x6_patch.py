#!/usr/bin/env python3
"""Patch Keenetic's closed phr.ko (KN-3812 profile, KeeneticOS 5.01.C.8.0-2) so its buttons and
status LED use the Viettel 32x6 GPIO pins.

KN-3812 has one status LED, "WAN" (index 12), with GREEN and ORANGE colors (driver color mask 0x11
at driver+1196). phr_driver_soc_set_led_state_ drives it directly, bypassing the chip table:
    GPIO 11 <- w19, GPIO 12 <- w22   off: 0/1   green: 1/1   orange: 0/0
The chip table (chip_gpio_dev at .bss+0x1b8: LEDs [0x00..0x27], buttons 5 bytes each from 0x28,
devices from 0x46; byte = GPIO | 0x80 inverts, 0xff = absent) only holds LED 12 = GPIO 11, so
the chip configures that pin as an output and reports the LED as supported.

32x6: RGB LED red GPIO 5, blue GPIO 7, green GPIO 8 (all active-low); reset button GPIO 1, WPS
(mesh) button GPIO 0 (active-low, the chip's default polarity); no USB. Mapping:
    green  -> GPIO 8 <- (w19 ^ 1)     off: 1  green: 0  orange: 1
    orange -> GPIO 5 (red) <- w22     off: 1  green: 1  orange: 0
LED 12 chip byte = 0x88 (GPIO 8 active-low) so the chip sets GPIO 8 as an output; GPIO 5 is an
output already (U-Boot gpio-leds, plus a gpio-hog in the Keenetic DTS).

phr_driver_soc_configure_ drives GPIO 39 low; on the 32x6 that is the MT7531 reset (low = held in
reset, high = running, as OpenWrt's mt7530 driver leaves it), so it is driven high instead.

phr_driver_init reuses w2 (= 11) for LED 12's chip byte and for the last entry of LED 12's
foreground array, so the LED 12 byte is written from w10 by the instruction that stored the USB_1
device byte (w10 held its GPIO 6; it is set at 20f4, after the original LED store at 20a8). The
chip table is 0xff-filled by chip_gpio_dev_init, so the USB_1 device is left absent.

Patched instruction words (text vaddr; file offset = vaddr + 0x80; none carries a relocation):
  1f50 mov w2,#0             -> mov w2,#1            GPIO 39 (MT7531 reset) high, not low
  1fe4 mov w2,w19            -> eor w2,w19,#1        green is active-low
  1fec mov w1,#11            -> mov w1,#8            green GPIO 8
  1ffc mov w1,#12            -> mov w1,#5            orange -> red GPIO 5
  20a8 strb w2,[x20,#452]    -> nop                  chip: LED 12 byte written at 2110
  20f4 mov w10,#6            -> mov w10,#0x88        w10 = GPIO 8 active-low
  2108 strb w12,[x20,#480]   -> strb w1,[x20,#480]   chip: RESET button GPIO 24 -> 1 (w1 == 1)
  210c strb w11,[x20,#485]   -> strb wzr,[x20,#485]  chip: WPS button GPIO 29 -> 0
  2110 strb w10,[x20,#510]   -> strb w10,[x20,#452]  chip: LED 12 = 0x88, USB_1 device absent
  2130 strb w1,[x19,#1288]   -> strb wzr,[x19,#1288] driver: USB_1 device not available

Idempotent; verifies original bytes and aborts before writing on any mismatch. Usage:
  python3 phr_32x6_patch.py /path/to/phr.ko
"""
import struct
import sys

# (text vaddr, original word, patched word, label) -- words as objdump prints them
WORDS = [
    (0x1f50, 0x52800002, 0x52800022, "GPIO 39 (MT7531 reset) high, not low"),
    (0x1fe4, 0x2a1303e2, 0x52000262, "LED: green is active-low"),
    (0x1fec, 0x52800161, 0x52800101, "LED: green GPIO 11 -> 8"),
    (0x1ffc, 0x52800181, 0x528000a1, "LED: orange GPIO 12 -> red GPIO 5"),
    (0x20a8, 0x39071282, 0xd503201f, "chip: LED 12 byte moved to 2110"),
    (0x20f4, 0x528000ca, 0x5280110a, "chip: LED 12 = GPIO 8 active-low (0x88)"),
    (0x2108, 0x3907828c, 0x39078281, "chip: RESET button GPIO 24 -> 1"),
    (0x210c, 0x3907968b, 0x3907969f, "chip: WPS button GPIO 29 -> 0"),
    (0x2110, 0x3907fa8a, 0x3907128a, "chip: LED 12 = w10 (0x88), USB_1 device absent"),
    (0x2130, 0x39142261, 0x3914227f, "driver: USB_1 device unavailable"),
]
PATCHES = [(va + 0x80, struct.pack("<I", o), struct.pack("<I", n), label) for va, o, n, label in WORDS]


def reloc_file_offsets(data):
    """File offsets of every RELA target (r_offset) in an ELF64 LE relocatable object."""
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3a)
    sh = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    out = set()
    for _, sh_type, _, _, off, size, _, info, _, entsize in sh:
        if sh_type != 4:  # SHT_RELA; info = index of the section it patches
            continue
        base = sh[info][4]
        for j in range(size // entsize):
            r_offset, r_info = struct.unpack_from("<QQ", data, off + j * entsize)
            width = 8 if r_info & 0xffffffff == 257 else 4  # R_AARCH64_ABS64; others patch one word
            out.update(range(base + r_offset, base + r_offset + width))
    return out


def main(path):
    data = bytearray(open(path, "rb").read())
    relocated = reloc_file_offsets(data)
    for off, orig, new, label in PATCHES:
        changed = {off + i for i in range(len(new)) if orig[i] != new[i]}
        assert not changed & relocated, f"{label}: changes bytes under a relocation"
    done = 0
    for off, orig, new, label in PATCHES:
        cur = bytes(data[off:off + len(new)])
        if cur == new:
            print(f"skip (already patched): {label}")
            continue
        if cur != orig:
            sys.exit(f"ABORT: {label} @ {off:#x}: expected {orig.hex()}, found {cur.hex()}")
        data[off:off + len(new)] = new
        done += 1
        print(f"patched: {label}")
    if done:
        open(path, "wb").write(data)
    print(f"done ({done} site(s) written)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
