#!/bin/sh
# Apply the Viettel vAP-32X6V1 changes to a keenetic-sdk checkout and unpack the stock KN-3812 image.
# Usage: scripts/apply-to-sdk.sh <keenetic-sdk dir> <stock KN-3812 .bin>
# Run as a non-root user (unpack.sh requirement), on a case-sensitive filesystem (ext4).
# Then: cd <sdk> && make -j$(nproc)
set -eu
[ $# -eq 2 ] || { echo "usage: $0 <keenetic-sdk dir> <stock KN-3812 .bin>" >&2; exit 1; }
PORT=$(cd "$(dirname "$0")/.." && pwd)
SDK=$(cd "$1" && pwd)
STOCK=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
T=$SDK/target/linux/mt7981

# Kernel 4.9: 32x6 NAND layout (no NMBM, KeeneticOS in the last 32 MiB), single-image U-State,
# DTS, config.
mkdir -p "$T/patches"
cp "$PORT"/kernel/40*.patch "$T/patches/"
cp "$PORT/kernel/KN-3812.dts" "$T/dts/KN-3812.dts"
C=$T/KN-3812/config-4.9
sed -i 's/^CONFIG_MTD_NDM_FLASH_SIZE_LIMIT=.*/CONFIG_MTD_NDM_FLASH_SIZE_LIMIT=0x7f00000/' "$C"
grep -q '^CONFIG_PSTORE_RAM=y' "$C" || cat "$PORT/kernel/config-4.9.additions" >> "$C"

# Closed files (ndm, ndw4, .ko) come from the stock image.
cd "$SDK"
./unpack.sh "$STOCK"

# Components: exactly those of the stock image (stock/<image>.txt, the `show version` format).
# Keep them all: dropping the USB/storage ones changes the network drivers loaded at boot and
# hw_nat.ko then panics in ppe_init (PpeDevRegHandler).
LIST=${STOCK%.bin}.txt
[ -f "$LIST" ] || { echo "missing component list $LIST" >&2; exit 1; }
tr -d '\r' < "$LIST" | sed '/^[[:space:]]*$/d' | paste -sd, - | ./configure.sh -p manual KN-3812

# Prebuilt closed module: binary patch (checks the stock bytes, refuses anything else, idempotent).
python3 "$PORT/binpatch/phr_32x6_patch.py" package/kernel/phr/files-phr/lib/modules/4.9-ndm-5/phr.ko

# ndm default configs (ports, name, no auto-update).
python3 "$PORT/rootfs/ndm_default_config_32x6.py" "$SDK"

# Web UI: port map, no USB, setup wizard WAN port, model in the header.
python3 "$PORT/rootfs/webui_32x6.py" "$SDK"

echo "OK. Now: cd $SDK && make -j\$(nproc)"
