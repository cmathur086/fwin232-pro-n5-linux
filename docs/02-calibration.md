# 2. Calibration: working around X

With good firmware loaded, touch *works* — and is unusable. On this panel the axes
come out mirrored and compressed: the reported X decreases as you move right, and
the whole screen is covered by part of the reported range. Dragging your finger
moves the pointer in the wrong direction, and the pointer's position has almost no
relationship to your finger.

The obvious fix is to calibrate the device in X. **On this hardware that does not
work**, and knowing exactly how it fails saves a lot of time.

## What does NOT work (all tried on the device)

| Attempt | Result |
|---|---|
| `xinput set-prop <dev> "libinput Calibration Matrix" …` at runtime | Worked **once**, before a restart. Inert in every post-boot session afterwards. |
| udev rule setting `ENV{LIBINPUT_CALIBRATION_MATRIX}` | No effect at all. |
| Device disable/enable, driver re-add (`modprobe -r/-+`) | No effect. |
| `xserver-xorg-input-evdev` + `Evdev Axis Calibration` in `xorg.conf.d` | Would give per-axis min/max and inversion, but this is a **static** transform: you lose multitouch, and every re-measurement needs an X restart. Kept as a fallback, not used. |

The libinput property being *inert* (rather than rejected) is the nasty part: X
reports the property, accepts your value, and ignores it.

## What works: translate the device instead of calibrating it

Read the physical device, apply your own mapping, and emit a **new** virtual
multitouch touchscreen through `/dev/uinput`. X then sees a device that is already
correct, and the stubborn calibration machinery never gets involved.

[`../translator/silead_translate.py`](../translator/silead_translate.py) does this in
pure stdlib Python:

1. Resolve the physical device **by name** from `/sys/class/input/event*/device/name`
   — **never** by node number. The node moved `event11` → `event17` across a single
   reboot here, and anything that cached `/dev/input/event11` broke.
2. Map positions: `px = SLOPE * raw + OFFSET`, clamped to the screen.
3. Emit an identically-shaped device (`silead_ts_calibrated`) via uinput.
4. Keep the raw device away from X entirely with a udev rule, so only the corrected
   device moves the pointer.

## The trap that cost a full night: two different coordinate scales

**`xinput test-xi2` does not report what the kernel node reports.**

- XInput2 prints valuators on its **own 0..65535 axis, after X's own transforms**
  (including whatever the calibration matrix did).
- The kernel node reports what the driver actually emitted. On this panel that is a
  **near-pixel space**: a tap at screen x=1800 reads **raw x=1846**.

Calibrating the daemon from `test-xi2` numbers therefore produced knots roughly 16×
too large. Every real value fell below the first knot, so the piecewise map clamped
it to that knot's output — the pointer sat pinned in one corner, and the real taps
looked like "phantom noise" in the logs because they were being read at the wrong
assumed scale.

Two lessons worth more than the fix:

1. **Calibrate a raw-device consumer from that same raw node.** Comparing numbers
   from two layers of the stack compares two coordinate spaces.
2. **A device's declared `absinfo` range need not be what it emits.** Here the
   driver declared `max=4095` while emitting values that topped out around 1900,
   because the mapping is proportional to the panel. Measure; do not infer.

A corollary worth stating, because it was in the earlier notes as a hardware
behaviour and was wrong: a claim that "raw values differ between a warm and a cold
chip state" was measured through an X-level tool, so it was describing **X's** state
(matrix applied or not) rather than the panel's. Re-measure at the raw node before
believing the hardware moved. On this device the raw values were stable across a
cold reboot to within a few units.

## The calibration procedure

Calibration is a **9-dot round**, and it takes about a minute.

```bash
# both scripts live in ../calibration/
bash cal9-run.sh            # shows the dot page fullscreen, captures raw frames
                            # (ends by itself once it has 9 touches)
python3 parse_tap9.py /tmp/silead-raw9.txt
```

Tap the dots **1..9 in order**. The fitter prints the per-axis line and the
residuals, and you paste the two lines into the daemon:

```
X: 0.97724 * raw - 8.9
Y: 0.97004 * raw - 32.8
```

Details that matter:

- **Use the median of each contact, not its first frame.** Fitting only the first
  frame per tap gives ~30 px residuals here (the fingertip is still settling);
  medians give 10-16 px. If a fitter samples "the frame that carries `BTN_TOUCH`",
  it is silently taking one sample per touch — that was a real bug in ours.
- **The linear model is enough.** The residual pattern is random, not curved, so a
  piecewise table buys nothing and adds an extrapolation cliff — which is exactly
  what turned the units mismatch into a corner-pinned pointer.
- **Calibrate in the state you will use it in** (i.e. after a normal boot), and
  re-check after a reboot before trusting it.

## Wiring it in permanently

```bash
sudo mkdir -p /opt/fwin232
sudo cp translator/silead_translate.py /opt/fwin232/
sudo cp translator/silead-translate.service /etc/systemd/system/
sudo cp translator/99-silead-ignore.rules /etc/udev/rules.d/
sudo cp translator/silead-translate.logrotate /etc/logrotate.d/silead-translate
sudo systemctl daemon-reload
sudo systemctl enable --now silead-translate     # starts now and at every boot
sudo udevadm control --reload-rules
```

The udev rule is what keeps the **raw** device away from X:

```
ACTION=="add|change", KERNEL=="event*", ATTRS{name}=="silead_ts", ENV{LIBINPUT_IGNORE_DEVICE}="1"
```

It matches the exact name, so the calibrated device (`silead_ts_calibrated`) is
unaffected. It only affects libinput — the daemon reads the kernel node directly and
keeps working. **Verified:** after a reboot, `xinput list` shows only
`silead_ts_calibrated`; the raw device is absent from X entirely.

If you would rather not use the udev property, the fallback is to disable the raw
device at login (`xinput disable "$(xinput list --id-only silead_ts)"` from an
autostart entry) — but note that name-based `xinput` lookup matches substrings, so
resolve the ID carefully when both devices exist.

## Verifying it actually works

The daemon prints one line per touch, which makes the whole chain checkable:

```
[23:26:05] touch 8 slot0: raw=(956,784) px=(925,728) n=78
[23:43:49] touch 19 slot0: raw=(990,397) px=(959,352) n=80
```

Put the dot page up, tap a known dot, and compare `px=` with where that dot actually
is. Independent confirmation that X agrees:

```bash
export DISPLAY=:0
xinput list --short | grep silead     # expect ONLY silead_ts_calibrated
python3 ptrpoll.py 100                # prints XQueryPointer's idea of the cursor
```

`ptrpoll.py` matters because X's *emulated* motion events lag by one event, so
watching a cursor can mislead you about where a touch landed; `XQueryPointer` is
ground truth.

## Appendix: the ABI details that cost time

- **`struct input_event` must be `"<qqHHi"` (24 bytes).** Python's `struct` in
  standard mode makes `l` four bytes; using it gives a 16-byte struct and `EINVAL`
  from uinput with no explanation.
- **The virtual device needs `INPUT_PROP_DIRECT`** (`UI_SET_PROPBIT`), or udev
  classifies it as a tablet and **X refuses to use it as a touchscreen**.
- **Mirror the physical device's capabilities onto the virtual one.** If you forward
  an event code the uinput device did not declare, the kernel rejects the *write* —
  in a daemon that ignores `os.write`'s return, that means silently dropped events.
  The daemon here reads `EVIOCGBIT` from the real device and declares exactly the
  same set, re-ranging only the position axes.
- **Resolve the device by name on every reconnect** (see above), and have the systemd
  unit `Restart=always` so a module reload does not leave you touchless.
