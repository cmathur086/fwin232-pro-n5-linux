#!/bin/bash
# Build the Silead touch firmware from the ODM's own panel config header.
#
#   ./build-firmware.sh [header.h] [output.fw]
#
# With the FWIN232 PRO N5 header this reproduces the working blob EXACTLY:
#   df1f7d8e7fe70e0666379b5d5311b21d0c22b6aad6759b8ece703c909d5532ad
#
# Needs perl. fwtool is bundled in tools/ (third-party, GPLv2 - see tools/README.md).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

HDR=${1:-WB_SF133A3692_P_X64_JYK_220107.h}
OUT=${2:-plain.fw}

command -v perl >/dev/null 2>&1 || { echo "ERROR: perl is required" >&2; exit 1; }
[ -f "$HDR" ] || { echo "ERROR: header not found: $HDR" >&2; exit 1; }

echo "== building firmware from $HDR"
# -2      input is an unscrambled GSL_TS_CFG header (the .h from the driver package)
# -m 3692 controller model
# -w -h   panel dimensions the controller works in (NOT the screen resolution)
# -t 10   max touch points
# -f track
perl tools/fwtool -c "$HDR" -2 -m 3692 -w 1360 -h 2170 -t 10 -f track out.fw

echo
echo "== exporting PLAIN format (the format the chip actually accepts)"
echo "   NOTE: -x takes the OUTPUT file FIRST"
perl tools/fwtool -x "$OUT" out.fw

echo
echo "== result"
ls -la out.fw "$OUT"
sha256sum out.fw "$OUT"
echo
echo "Expected hash for the FWIN232 PRO N5 config:"
echo "  df1f7d8e7fe70e0666379b5d5311b21d0c22b6aad6759b8ece703c909d5532ad"
echo
echo "Install (this is the PLAIN export, not out.fw):"
echo "  sudo mkdir -p /lib/firmware/silead"
echo "  sudo cp $OUT /lib/firmware/silead/mssl1680.fw"
echo "  sudo modprobe -r silead; sudo modprobe silead"
