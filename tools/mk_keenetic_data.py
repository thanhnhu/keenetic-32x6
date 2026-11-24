#!/usr/bin/env python3
"""Build the KeeneticOS data partitions for a Viettel vAP-32X6V1 from its Factory dump.

  U-Config  (NAND 0x100000, 0x40000): Keenetic identity as two redundant 128 KiB U-Boot env
            blocks (CRC32 over the block minus 4), the format quytttb's NR3053 U-Boot writes and
            ndm accepts (ndm later rewrites the active block as a 16 KiB env with lock=yes).
            Values are derived deterministically from the Factory data, so the same router always
            gets the same identity: sernumb, servicetag, servicepass, wlanssid/wlankey/wlanwps,
            country, ndmhwid and ctrlsum = md5("servicetag,servicehost,servicepass,wlanssid,
            wlankey,wlanwps,country,ndmhwid,<mac 0x4>,<mac 0xa>").
  RF-EEPROM (NAND 0x7f60000, 0xa0000): Factory 0x0-0xa0000 (Wi-Fi EEPROM + calibration) with the
            MACs where KN-3812 keeps them: 0x4 = LAN (Factory 0x2a), 0xa = WAN (Factory 0x24).
            The real Factory partition is never written.

The identity is not a real Keenetic one: KeenDNS/cloud services will not work.

usage: mk_keenetic_data.py <factory.bin> <out dir>
"""
import hashlib
import os
import struct
import sys
import zlib

FACTORY_SIZE = 0x200000
E2P_SIZE = 0xa0000
UCONFIG_SIZE = 0x40000
BLOCK = 0x20000
CONTEXT = b"VIETTEL/vAP-32X6V1/KeeneticOS/U-Config/v1"
HWID = "KN-3812"
COUNTRY = "VN"
WLAN_SSID = "Keenetic"       # default Wi-Fi name and key (what KeeneticOS falls back to on reset)
WLAN_KEY = "12345678"        # WPA2/WPA3 need at least 8 characters
SERVICE_HOST = "127.0.0.1"
DEFAULTS = [  # U-Boot entries of the KN-3812 U-Config (strings in libndmCorePack.so)
    ("baudrate", "115200"),
    ("bootfile", "KN-3812_recovery.bin"),
    ("bootfile.bl2", "KN-3812_bl2.img"),
    ("bootfile.fip", "KN-3812_fip.bin"),
    ("bootfile.e2p", "KN-3812_e2p.bin"),
    ("bootfile.bl31", "KN-3812_bl31.img"),
    ("bootfile.bl33", "KN-3812_uboot.bin"),
    ("ethaddr", "00:AA:BB:CC:DD:10"),
    ("ipaddr", "192.168.1.1"),
    ("netmask", "255.255.255.0"),
    ("netretry", "yes"),
    ("serverip", "192.168.1.2"),
]
ALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def mac_ok(m):
    return not (m[0] & 1) and m != b"\0" * 6 and m != b"\xff" * 6


def mac_text(m):
    return ":".join("%02x" % b for b in m)


def derive(seed, label):
    return hashlib.sha256(seed + b"\0" + label.encode()).digest()


def decimal(seed, label, n):
    s = "".join(chr(48 + b % 10) for b in derive(seed, label)[:n])
    return ("1" + s[1:]) if s[0] == "0" else s


def alnum(seed, label, n):
    return "".join(ALNUM[b % len(ALNUM)] for b in derive(seed, label)[:n])


def wps_checksum(pin):
    acc = 0
    while pin:
        acc += 3 * (pin % 10)
        pin //= 10
        acc += pin % 10
        pin //= 10
    return (10 - acc % 10) % 10


def main(factory_path, out):
    f = open(factory_path, "rb").read()
    if len(f) != FACTORY_SIZE:
        sys.exit("Factory dump must be 0x%x bytes" % FACTORY_SIZE)
    wan, lan = f[0x24:0x2a], f[0x2a:0x30]
    if not (mac_ok(wan) and mac_ok(lan)) or wan == lan:
        sys.exit("no valid WAN/LAN MAC at Factory 0x24/0x2a")

    e2p = bytearray(f[:E2P_SIZE])
    e2p[0x4:0xa] = lan
    e2p[0xa:0x10] = wan
    macs = [bytes(e2p[0x4:0xa]), bytes(e2p[0xa:0x10])]

    seed = hashlib.sha256(CONTEXT + f).digest()
    ident = {}
    ident["sernumb"] = "S26%sVN%s" % (decimal(seed, "serial-factory", 2), decimal(seed, "serial", 6))
    ident["servicetag"] = decimal(seed, "servicetag", 15)
    ident["servicehost"] = SERVICE_HOST
    ident["servicepass"] = alnum(seed, "servicepass", 20)
    ident["wlanssid"] = WLAN_SSID
    ident["wlankey"] = WLAN_KEY
    base = int(decimal(seed, "wlanwps", 7))
    ident["wlanwps"] = "%07u%u" % (base, wps_checksum(base))
    ident["country"] = COUNTRY
    ident["ndmhwid"] = HWID
    fields = ["servicetag", "servicehost", "servicepass", "wlanssid", "wlankey", "wlanwps",
              "country", "ndmhwid"]
    ser = ",".join(ident[k] for k in fields) + "".join("," + mac_text(m) for m in macs)
    ctrlsum = hashlib.md5(ser.encode()).hexdigest()

    env = b"".join(("%s=%s" % kv).encode() + b"\0"
                   for kv in list(ident.items()) + DEFAULTS + [("ctrlsum", ctrlsum)])
    payload = env + b"\0" * (BLOCK - 4 - len(env))
    block = struct.pack("<I", zlib.crc32(payload) & 0xffffffff) + payload
    uconfig = block + block

    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "uconfig.bin"), "wb").write(uconfig)
    open(os.path.join(out, "rf-eeprom.bin"), "wb").write(bytes(e2p))
    assert len(uconfig) == UCONFIG_SIZE and len(e2p) == E2P_SIZE
    print("U-Config  -> %s (0x%x), Wi-Fi SSID %s" % (os.path.join(out, "uconfig.bin"), len(uconfig),
                                                    ident["wlanssid"]))
    print("RF-EEPROM -> %s (0x%x), LAN %s, WAN %s" % (os.path.join(out, "rf-eeprom.bin"), len(e2p),
                                                     mac_text(lan), mac_text(wan)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
