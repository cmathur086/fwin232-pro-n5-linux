#!/bin/sh
# DEAD END - kept only as a warning. This does NOT work on this tablet.
#
# It sets the libinput Calibration Matrix on the silead device at login. X will
# accept the value and report it back, and the pointer will not move accordingly:
# the property is inert in a post-boot session (it worked once, pre-restart, which
# is what makes it such a trap). See history/README.md.
for i in 1 2 3 4 5 10 15 20; do
  SID=$(xinput list --id-only "silead_ts" 2>/dev/null)
  if [ -n "$SID" ]; then
    xinput set-prop "$SID" "libinput Calibration Matrix" -1.104700 0 1.086460 0 3.309860 -0.023633 0 0 1
    exit 0
  fi
  sleep 1
done
