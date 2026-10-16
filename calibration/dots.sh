#!/bin/bash
# Show (or close) the 9-dot calibration page fullscreen.
#
#   dots.sh          -> show it, keep the panel awake
#   dots.sh off      -> close it, restore blanking
#
# Tapping known dots and reading the daemon's own log is the check: each touch
# prints  [HH:MM:SS] touch N slotS: raw=(x,y) px=(px,py)
#
# Needs a browser that can run kiosk-mode. Set BROWSER to change it.
HERE="$(cd "$(dirname "$0")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
PROF="$HOME/.config/silead-calprof"
BROWSER=${BROWSER:-firefox}

close_page() {
  for p in $(pgrep -f "$PROF"); do
    # match on the executable, not the comm name: Firefox's binary is
    # "firefox-bin" on Mint/Ubuntu, so a comm check silently misses it
    case "$(readlink /proc/$p/exe 2>/dev/null)" in
      *firefox*) kill "$p" 2>/dev/null ;;
    esac
  done
}

if [ "$1" = "off" ]; then
  close_page
  xset s on +dpms 2>/dev/null
  echo "dots page closed"
  exit 0
fi

close_page
sleep 1
[ -d "$PROF" ] || mkdir -p "$PROF"
xset s off -dpms 2>/dev/null      # keep the panel awake for the round
setsid "$BROWSER" --profile "$PROF" --kiosk \
  "file://$HERE/markers9.html" >/dev/null 2>&1 &
sleep 12
if pgrep -f "silead-calpro[f]" >/dev/null; then
  echo "DOTS PAGE UP - tap dots 1..9 in order"
else
  echo "PAGE FAILED to launch"
  exit 1
fi
