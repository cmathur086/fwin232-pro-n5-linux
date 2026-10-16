#!/bin/bash
# Full 9-dot calibration round: show the page, capture RAW frames, stop by itself.
#
#   bash cal9-run.sh [max-seconds]        (default 900)
#
# Then fit it:
#   python3 parse_tap9.py /tmp/silead-raw9.txt
#
# Needs root for the capture (reads /dev/input/eventN).
HERE="$(cd "$(dirname "$0")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
MAXSECS=${1:-900}
OUT=/tmp/silead-raw9.txt

"$HERE/dots.sh" || exit 1
echo "TAP NOW - dots 1..9 in order (ends after 9 touches, max ${MAXSECS}s)"
sudo python3 "$HERE/rawdump.py" "$MAXSECS" "$OUT" --touches 9
echo "capture: $(sudo grep -c '^t=' "$OUT") frame lines; $(sudo tail -1 "$OUT")"
"$HERE/dots.sh" off
echo "DONE - now run: python3 $HERE/parse_tap9.py $OUT"
