#!/bin/bash
# Build KeeneticOS for the 32x6 in WSL: sync this port folder, apply to ~/keenetic-sdk, make.
set -eu
PORT=$(cd "$(dirname "$0")/.." && pwd)
SDK=${SDK:-$HOME/keenetic-sdk}
# stock KN-3812 firmware: source of the closed parts (ndm, web UI, prebuilt modules)
STOCK=${STOCK:-$PORT/stock/KN-3812_stable_5.1.8_5.01.C.8.0-2.bin}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
rm -rf "$HOME/kn-32x6-port"; mkdir "$HOME/kn-32x6-port"
(cd "$PORT" && tar --exclude=./.git --exclude=./stock -cf - .) | tar -C "$HOME/kn-32x6-port" -xf -
find "$HOME/kn-32x6-port" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.patch' -o -name '*.dts' -o -name '*.additions' \) -exec sed -i 's/\r$//' {} +
sh "$HOME/kn-32x6-port/scripts/apply-to-sdk.sh" "$SDK" "$STOCK"
cd "$SDK"
# the firmware version is `git describe` (annotated tags only, include/release.mk):
# a shallow clone may lack the release tag
rel=$(git log -1 --format=%s | sed -n 's/^Release //p')
if [ -n "$rel" ] && [ "$(git describe 2>/dev/null)" != "$rel" ]; then
	git -c user.name=build -c user.email=build@localhost tag -a -f -m "Release $rel" "$rel" HEAD
	rm -rf tmp
fi
# DEBUG=1: debug overlay (ndm started by /etc/dbg.sh, its log copied to the kernel log)
rm -rf files
if [ "${DEBUG:-0}" = 1 ]; then
	cp -r "$HOME/kn-32x6-port/debug/files" files
	find files -type f -exec sed -i 's/\r$//' {} +
	chmod 755 files/etc/dbg.sh
	# KeeneticOS /bin/sh is "NDM Shell Wrapper": `sh script` runs /opt/bin/sh (Entware), so
	# init's /etc/init.d/rcS needs a real shell there; the SDK busybox has no "sh" applet
	# (SH_IS_NONE), so build a copy with SH_IS_ASH using the SDK toolchain
	bbsrc=$(ls -d build_dir/target-*/busybox-* | head -1)
	[ -n "$bbsrc" ] || { echo "busybox not built yet: run a normal build first" >&2; exit 1; }
	bb=$HOME/bb-dbg
	if [ ! -x "$bb/busybox" ]; then
		rm -rf "$bb"; cp -r "$bbsrc" "$bb"
		sed -i 's/^CONFIG_SH_IS_NONE=y/# CONFIG_SH_IS_NONE is not set/; s/^# CONFIG_SH_IS_ASH is not set/CONFIG_SH_IS_ASH=y/' "$bb/.config"
		( export PATH="$SDK/staging_dir/toolchain-aarch64-linux-musl/bin:$PATH"
		  cd "$bb" && yes "" | make CROSS_COMPILE=aarch64-ndms-linux-musl- oldconfig >/dev/null &&
		  make CROSS_COMPILE=aarch64-ndms-linux-musl- clean >/dev/null &&
		  make CROSS_COMPILE=aarch64-ndms-linux-musl- -j"$(nproc)" busybox >/dev/null )
	fi
	# two copies: ndm may mount storage over /opt later
	mkdir -p files/bin files/opt/bin
	install -m 755 "$bb/busybox" files/bin/busybox
	install -m 755 "$bb/busybox" files/opt/bin/sh
	# strace from the toolchain's debug root, stripped
	st=$(ls build_dir/toolchain-*/dl/*/debug-root/usr/bin/strace | head -1)
	[ -n "$st" ] && "$SDK"/staging_dir/toolchain-aarch64-linux-musl/bin/aarch64-ndms-linux-musl-strip -o files/bin/strace "$st" && chmod 755 files/bin/strace
	echo "== DEBUG build"
fi
echo "== build $(date)"
make -j"$(nproc)" || make -j1 V=s
echo "== done $(date)"
ls -la bin/mt7981/
