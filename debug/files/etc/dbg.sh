#!/bin/busybox sh
# Debug boot (DEBUG=1 builds only): init runs this instead of ndm because /etc/nondm exists.
# Runs ndm under strace (its /dev/log messages are taken from the trace, kept in tmpfs). When
# ndm exits, or after 120 s, the ndm messages, the ndm interface state and a system snapshot go
# to the kernel log and the box warm-reboots, so U-Boot's kn_savelog (mesh button held, no
# power cycle) keeps them.
B=/bin/busybox
$B mount -t tmpfs dbg /dbg
$B mknod /dbg/kmsg c 1 11
K=/dbg/kmsg
log() { echo "dbg: $*" > $K; }
tok() { $B cut -c1-220 | while read -r l; do echo "$1: $l" > $K; done; }
# ndmc with a time limit (it blocks while ndm is busy or gone)
ndmc_t() {
	/bin/ndmc -c "$1" > /dbg/n 2>&1 &
	q=$!
	t=0
	while $B kill -0 $q 2>/dev/null && [ $t -lt 8 ]; do $B sleep 1; t=$((t + 1)); done
	$B kill -9 $q 2>/dev/null && echo "(ndmc timed out)"
	$B cat /dbg/n
}

finish() {
	[ -e /dbg/done ] && return
	: > /dbg/done
	msgs() { $B grep -o 'sendto(5, "<[0-9]*>[^"]*' /dbg/st | $B sed 's/^sendto(5, "//; s/\\n$//'; }
	log "== ndm syslog: $(msgs | $B wc -l) messages, $(msgs | $B grep -c 'system failed') failures"
	log "== ndm errors and warnings (levels 0-4, first 80)"
	msgs | $B grep -E '^<(8|9|10|11|12)>' | $B head -n 80 | tok err
	log "== mtd access (first 60)"
	$B grep -E 'open.*/dev/mtd|/proc/mtd|MEMGETINFO|MEMERASE|MEMGETBADBLOCK|MEMREAD|startup-config|/flash' /dbg/st | $B head -n 60 | tok mtd
	log "== mtd fds read/write (first 40)"
	for fd in $($B grep -oE 'open[a-z]*\(AT_FDCWD, "/dev/mtd[0-9]+"[^=]*= [0-9]+' /dbg/st | $B sed 's/.*= //' | $B sort -u); do
		$B grep -E "^[0-9]+ +[0-9:.]+ (pread64|read|pwrite64|write|lseek|ioctl)\($fd," /dbg/st | $B head -n 6
	done 2>/dev/null | $B head -n 40 | tok mtdio
	log "== ndm config messages"
	msgs | $B grep -iE 'config|storage|startup|flash|state' | $B head -n 40 | tok cfgmsg
	log "== ndm interface/port messages (first 80)"
	msgs | $B grep -iE 'bridge|gigabit|switch|port|ethernet|link|dhcp|home|wifi|ap[0-9]' |
		$B grep -vE '^<(8|9|10|11|12)>' | $B head -n 80 | tok ifc
	if [ -e /dbg/ndm.exited ]; then
		log "== failed syscalls (last 40)"
		$B grep -E ' = -1 E|\+\+\+ exited|killed by' /dbg/st | $B grep -vE 'ENOENT|EAGAIN|ETIMEDOUT' |
			$B tail -n 40 | tok fail
	else
		log "== ndmc show interface (summary)"
		ndmc_t "show interface" | $B grep -E '^ *(id|index|interface-name|type|description|link|connected|state|address|mask|role|port|switch|group|ssid|mac):' |
			$B head -n 160 | tok sif
		log "== ndmc show running-config"
		ndmc_t "show running-config" | $B head -n 160 | tok cfg
	fi
	for c in "ifconfig -a" "cat /proc/net/dev" "ls /sys/class/net"; do
		log "== $c"
		$B $c 2>&1 | $B grep -vE 'collisions|bytes:|RX packets|TX packets|^ *$' | $B head -n 60 | tok snap
	done
	log "rebooting"
	$B sync
	$B kill -TERM 1
	$B sleep 10
	echo b > /proc/sysrq-trigger
}

( $B sleep 120; log "timeout"; finish ) &

log "debug boot, starting ndm under strace"
/bin/strace -f -tt -s 96 -o /dbg/st \
	-e trace='!mmap,mprotect,munmap,brk,futex,clock_gettime,clock_nanosleep,nanosleep,rt_sigprocmask,rt_sigaction,gettid,getpid,epoll_pwait,ppoll,pselect6,sched_yield,madvise,membarrier' \
	/bin/ndm > $K 2>&1
log "ndm exited, status $?"
: > /dbg/ndm.exited
finish
