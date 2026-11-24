#!/usr/bin/env python3
"""Adapt the KeeneticOS (KN-3812) web UI to the Viettel vAP-32X6V1 hardware.

KN-3812 has two switches: its WAN is the SoC PHY (GigabitEthernet1/0, port label "0", blue)
and the MT7531 carries LAN 1-3 (GigabitEthernet0/0..0/2, labels "1".."3"). The labels are
nailed up by the hardware profile ("cannot change nailed-up label"). On the 32x6 the SoC PHY
has no jack and the three jacks are MT7531 ports: WAN = GigabitEthernet0/0 (label "1"),
LAN1/LAN2 = GigabitEthernet0/1, 0/2 (labels "2", "3").

- assets/ndmConstants.json/.js (ndw4): one switch, the blue WAN port is GigabitEthernet0/0
  (label "1"), LAN = labels "2" and "3", GigabitEthernet1/0 removed from the map (the port
  pictures, "Network Ports" in General System Settings, port statistics).
- the setup wizard (ndw3) uses port label "0" as its default Internet port: make it "1",
  otherwise "Modem/router from your provider" configures the jack-less GigabitEthernet1.
- model shown in the header, login page, tab title and wizard: NDM.getDeviceModel() returns
  the `show version` model without the vendor ("KN-3812"); make it MODEL. Display only: ndm,
  U-Config and `show version` keep KN-3812 (the closed ndm needs its own hardware id).

Minified identifiers differ between releases, so the model functions are matched by regex.
Idempotent, aborts on unexpected content.
usage: webui_32x6.py <keenetic-sdk dir>
"""
import glob
import json
import re
import sys

MODEL = "vAP-32X6V1"
PORTS_MAP = {
    "WAN": {"index": 0, "port": "1", "color": "blue", "type": "ethernet", "name": "1",
            "interfaceId": "GigabitEthernet0/0", "group": "WAN", "maxSpeed": 1000},
    "LAN1": {"index": 1, "port": "2", "color": "gray", "type": "ethernet", "name": "2",
             "interfaceId": "GigabitEthernet0/1", "group": "LAN", "maxSpeed": 1000},
    "LAN2": {"index": 2, "port": "3", "color": "gray", "type": "ethernet", "name": "3",
             "interfaceId": "GigabitEthernet0/2", "group": "LAN", "maxSpeed": 1000},
}
WANTED = {"WAN_SWITCH": "GigabitEthernet0", "HAS_TWO_SWITCHES": False, "PORTS_MAP": PORTS_MAP,
          "PORTS_LAYOUT": [["1", "2", "3"]]}

# ndw4 main-*.js and ndw3 wizards/main-*.js
MODEL_UI = re.compile(
    r'getDeviceModel\(\)\{if\(!this\.model\)return"";let (\w+)=(\$?\w+)\.vendor\.toLowerCase\(\),(\w+)=new '
    r'RegExp\(`\^\$\{\1\}`,"i"\);return this\.model\.replace\(\3,""\)\.trim\(\)\}')
MODEL_WIZ = re.compile(
    r'getDeviceModel\(\)\{let (\w+)=(\$?\w+)\.vendorName\.toLowerCase\(\),(\w+)=new '
    r'RegExp\(`\^\$\{\1\}`,"i"\);return this\.model\.replace\(\3,""\)\.trim\(\)\}')
MODEL_UI_DONE = 'getDeviceModel(){return this.model?"%s":""}' % MODEL
MODEL_WIZ_DONE = 'getDeviceModel(){return"%s"}' % MODEL


def constants(d):
    """Return True if d was changed."""
    if all(d.get(k) == v for k, v in WANTED.items()):
        return False
    if d.get("WAN_SWITCH") != "GigabitEthernet0":
        assert d["WAN_SWITCH"] == "GigabitEthernet1" and \
            d["PORTS_MAP"]["WAN"]["interfaceId"] == "GigabitEthernet1/0", d
    d.update(WANTED)
    return True


def write(path, text):
    # in place: keeps the user.package xattr set by unpack.sh
    open(path, "w", encoding="utf-8", newline="").write(text)
    print("edited: " + path)


def edit_json(path):
    d = json.load(open(path, encoding="utf-8"))
    if constants(d):
        write(path, json.dumps(d, indent="\t") + "\n")
    else:
        print("skip (already edited): " + path)


def edit_js(path):
    raw = open(path, encoding="utf-8").read()
    head, body = raw.split("=", 1)
    assert head.strip() == "window.NDM", head
    d = json.loads(body.strip().rstrip(";"))
    if constants(d):
        write(path, "window.NDM = " + json.dumps(d, indent="\t") + ";\n")
    else:
        print("skip (already edited): " + path)


def sub_model(raw, pat, done, path):
    if raw.count("getDeviceModel(){") == 1 and raw.count(done) == 1:
        return raw
    hits = list(pat.finditer(raw))
    assert raw.count("getDeviceModel(){") == 1 and len(hits) == 1, \
        "%s: expected one getDeviceModel() (new release? re-check the bundle)" % path
    return raw[:hits[0].start()] + done + raw[hits[0].end():]


def edit_main(path):
    raw = open(path, encoding="utf-8").read()
    new = sub_model(raw, MODEL_UI, MODEL_UI_DONE, path)
    if new == raw:
        print("skip (already edited): " + path)
    else:
        write(path, new)


def edit_wizard(path):
    raw = open(path, encoding="utf-8").read()
    new = raw
    if not (raw.count('hh="1"') == 1 and 'hh="0"' not in raw):
        assert raw.count('hh="0"') == 1, path
        new = new.replace('hh="0"', 'hh="1"')
    new = sub_model(new, MODEL_WIZ, MODEL_WIZ_DONE, path)
    if new == raw:
        print("skip (already edited): " + path)
    else:
        write(path, new)


def one(pattern):
    hits = glob.glob(pattern)
    assert len(hits) == 1, (pattern, hits)
    return hits[0]


def main(sdk):
    h4 = sdk + "/package/private/ndw4/files-ndw4/usr/share/htdocs_/"
    edit_json(h4 + "assets/ndmConstants.json")
    edit_js(h4 + "assets/ndmConstants.js")
    edit_main(one(h4 + "main-*.js"))
    edit_wizard(one(sdk + "/package/private/ndw3/files-ndw3/usr/share/htdocs_/wizards/main-*.js"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
