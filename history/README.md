# history/ — dead ends, kept as warnings

Nothing in this directory works. It is here so that you can recognise a path you
are about to walk down, and skip it.

## `apply-calibration.sh` — the X calibration attempt

The natural first move once touch works but is mirrored: tell X to calibrate the
device. This script sets the libinput calibration matrix at login.

**It does nothing.** On this tablet that property is *inert* in a post-boot
session: X accepts the value, reports it back, and ignores it. It appeared to work
exactly once, before a restart, which is what makes it such a trap — you conclude
you are one reboot away from a fix, and you are not.

Related attempts in the same direction, all equally ineffective:

- a udev rule setting `ENV{LIBINPUT_CALIBRATION_MATRIX}`
- disabling and re-enabling the device, and re-adding the driver
- passing the matrix on the kernel command line

The fallback that *would* work — `xserver-xorg-input-evdev` with `Evdev Axis
Calibration` in `xorg.conf.d` — was kept in reserve because it is a **static**
transform: it costs you multitouch and needs an X restart for every change. It is
a legitimate route if you only ever need single-touch and one calibration, and you
do not mind the trade-offs. If you take it, you do not need the translator daemon
at all.

## What to do instead

See [../docs/02-calibration.md](../docs/02-calibration.md): read the raw device,
map it yourself, emit a corrected one through uinput. It sounds like more work than
setting a property. It is — and it is also the only thing on this hardware that
stays working after a reboot.
