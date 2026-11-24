#!/usr/bin/env python3
"""Edit KeeneticOS (KN-3812) ndm default configs for the Viettel vAP-32X6V1.

The 32x6 has its three jacks on the MT7531: WAN = port 0 (GigabitEthernet0/0), LAN1/LAN2 =
ports 1/2 (GigabitEthernet0/1, 0/2). The KN-3812 SoC PHY (GigabitEthernet1/0, its WAN) has no
jack. Router mode: ISP = GigabitEthernet0/Vlan2 with GigabitEthernet0/0 in access VLAN 2
(`role inet for ISP`), GigabitEthernet1 + 1/0 down. Extender mode: GigabitEthernet1/0 down.
Both: system description "Viettel vAP-32X6V1" and components auto-update disabled (an official
KN-3812 image would bring the stock NAND layout with NMBM and break the shared flash).

Files are CRLF; lines are matched without the CR. Idempotent, aborts on unexpected content.
usage: ndm_default_config_32x6.py <keenetic-sdk dir>
"""
import sys

NAME = "Viettel vAP-32X6V1"
MARK = '    description "%s"' % NAME  # present once edited


def block(lines, header):
    """index range [start, end) of the block starting with header up to (not including) '!'"""
    s = lines.index(header)
    e = s + 1
    while lines[e] != "!":
        e += 1
    return s, e


def common(lines):
    i = lines.index("    domainname WORKGROUP")
    lines[i + 1:i + 1] = ["    caption description", '    description "%s"' % NAME]
    j = lines.index("!", i)
    lines[j + 1:j + 1] = ["components", "    auto-update disable", "!"]
    s, e = block(lines, "interface GigabitEthernet1/0")
    assert lines[s + 1:e] == ["    up"], lines[s:e]
    lines[s + 1:e] = ["    down"]


def router(lines):
    s, e = block(lines, "interface GigabitEthernet0/0")
    assert "    switchport access vlan 1" in lines[s:e]
    lines[lines.index("    switchport access vlan 1", s)] = "    switchport access vlan 2"
    s, e = block(lines, "interface GigabitEthernet1")
    assert lines[s + 1] == "    rename ISP", lines[s:e]
    lines[s] = "interface GigabitEthernet0/Vlan2"
    lines[e + 1:e + 1] = ["interface GigabitEthernet0/0", "    role inet for ISP", "!",
                          "interface GigabitEthernet1", "    down", "!"]


def edit(path, fn):
    raw = open(path, "rb").read().decode("utf-8")
    if MARK in raw:
        print("skip (already edited): " + path)
        return
    lines = raw.replace("\r\n", "\n").split("\n")
    common(lines)
    fn(lines)
    open(path, "wb").write("\r\n".join(lines).encode("utf-8"))
    print("edited: " + path)


def main(sdk):
    d = sdk + "/package/private/ndm/files-ndm/flash/"
    edit(d + "default-config", router)
    edit(d + "default-config.extender", lambda lines: None)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
