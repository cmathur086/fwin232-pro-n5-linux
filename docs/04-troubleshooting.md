# 4. Troubleshooting

Symptom first. Everything here was hit on the real device.

## Touch

| Symptom | Likely cause | Do this |
|---|---|---|
| No touch at all; `/lib/firmware/silead/` empty or the driver logs no chip ID | firmware missing | [01-firmware.md](01-firmware.md) |
| Driver loads, chip ID prints, still no events | wrong/absent blob, or the blob is the **new-style** build rather than the plain export | rebuild and install the **plain** export (`fwtool -x`), re-check with `rawdump.py` |
| Ghost contacts, "comb" patterns, contacts where nothing is touching | firmware from a different panel | get *your* device's `*.h` from its own driver package — a near-miss blob is worse than none |
| Touch works but axes are mirrored / compressed into part of the screen | expected on this panel without calibration | [02-calibration.md](02-calibration.md) |
| Pointer pinned in a screen corner; every touch lands in the same place | the map's knots are in the wrong **scale** (X units vs raw units) | recalibrate from the raw node, not from `xinput test-xi2` — see the trap in [02-calibration.md](02-calibration.md) |
| Daemon logs `raw x … outside the calibrated space` | the device's coordinate space changed under it | re-run the 9-dot round and update the constants |
| Touch worked, then stopped after a `modprobe` | the event **node number** changed | never address `/dev/input/eventN` directly; resolve by device name (the daemon does, and `Restart=always` recovers it) |
| Two pointers fighting / pointer jumps while touching | the raw device is still visible to X | install `99-silead-ignore.rules`, `udevadm control --reload-rules`; confirm with `xinput list --short` that only `silead_ts_calibrated` is present |
| Calibration "works right now" but not after a reboot | it was fitted in a different chip state | fit after a normal boot, then re-verify with a tap round post-reboot |
| `EINVAL` writing to uinput | `struct` format is wrong — `input_event` is `"<qqHHi"` (24 bytes), `l` is 4 bytes in Python's standard mode | fix the format string |
| Virtual device exists but X ignores it as a touchscreen | missing `INPUT_PROP_DIRECT` | set it via `UI_SET_PROPBIT` |

## UI

| Symptom | Likely cause | Do this |
|---|---|---|
| Everything is tiny | 96 DPI on a ~224 PPI panel | `ui-scale.sh 200` |
| Menus/dialogs clip their own text after scaling | scaled with `Xft/DPI` instead of the GTK scale factor | use `Gtk/WindowScalingFactor`; pin DPI to 96 ([03-tablet-ui.md](03-tablet-ui.md)) |
| Start menu app list cut off, bottom tab bar clipped | same as above | as above — `menu-width`/`menu-height` will **not** help |
| Firefox chrome smaller than the rest of the desktop | Firefox follows neither DPI nor the GTK scale factor here | `layout.css.devPixelsPerPx = 2.0` in the profile's `user.js` |
| Keyboard appears as a small floating box in a corner | Onboard docking disabled | `gsettings set org.onboard.window docking-enabled true` + dock width/height |
| A screenshot shows the start menu missing or blank | xfwm4 compositing; the popup isn't in a root-window grab | toggle `xfwm4:/general/use_compositing` off for the shot |
| Clock text got *smaller* after scaling up | the panel sizes clock text from DPI and ignores the scale factor | raise the clock's fonts explicitly |

## Session / boot

| Symptom | Likely cause | Do this |
|---|---|---|
| Reboot lands on the login greeter instead of the desktop | auto-login not configured, **or** configured but the PAM group check fails | set `autologin-user` in `/etc/lightdm/lightdm.conf.d/`, **and** add the user to the `nopasswdlogin` group — Mint's PAM runs `auth sufficient pam_succeed_if.so user ingroup nopasswdlogin`, and an empty group silently falls through to a password prompt. Confirm success by finding `pam_unix(lightdm-autologin:session)` in the journal |

## Useful one-liners

```bash
# What does the kernel think the device is?
grep -A3 'Name="silead' /proc/bus/input/devices

# Does X see the raw device (it should NOT) and the calibrated one (it should)?
DISPLAY=:0 xinput list --short | grep -i silead

# Is the udev property actually set on the raw node?
sudo udevadm info /dev/input/eventN | grep -E "LIBINPUT|ID_INPUT"

# What is the input device costing you in events? (tap while it runs)
sudo python3 calibration/rawdump.py 10 /tmp/raw.txt

# Is the daemon alive, and what has it been doing?
systemctl status silead-translate
sudo tail -30 /var/log/silead-translate.log

# Where does X think the cursor is? (ground truth; emulated motion lags)
python3 calibration/ptrpoll.py 100
```

## A general debugging note

Three times in this project the "bug" was a **measurement taken at the wrong layer**:
calibration numbers read from X instead of the device node; a screenshot read while
compositing hid the window; a claim about hardware behaviour inferred from an
X-level tool. If something looks impossible, check what layer your instrument is
actually observing before changing the thing you are debugging.
