#!/usr/bin/env python3
"""
Silead touch translator for the Fusion5 FWIN232 PRO N5 (and similar MSSL1680
tablets where X refuses to calibrate the panel).

The physical silead_ts device reports positions in a near-pixel space (a tap at
screen x=1800 reads raw x=1846), and X/libinput applies no usable calibration to
it: the libinput "Calibration Matrix" property is inert in a post-boot session, a
udev LIBINPUT_CALIBRATION_MATRIX rule does nothing, and a runtime set-prop worked
exactly once, before a restart.

So this daemon reads the physical device, maps the position axes to screen pixels
with a measured affine calibration, and emits a corrected multitouch touchscreen
through /dev/uinput.  A udev rule sets LIBINPUT_IGNORE_DEVICE=1 on the PHYSICAL
device, so only the corrected one drives the pointer.

Runs as root under systemd: silead-translate.service.

CALIBRATING - READ THIS FIRST
  Calibrate from the RAW kernel node (calibration/rawdump.py), NEVER from
  `xinput test-xi2`.  XI2 reports its own 0..65535 valuator scale after X's own
  transforms, which does not describe what this daemon reads; calibrating against
  it puts every real value outside the fitted range and pins the pointer to one
  corner.  Also: a device's declared absinfo range need not be what it emits.
  See docs/02-calibration.md.

  Set SILEAD_DEV if your input device is not named "silead_ts".
"""
import fcntl
import glob
import os
import select
import struct
import time

SCREEN_W, SCREEN_H = 1920, 1200
DEV_NAME = os.environ.get("SILEAD_DEV", "silead_ts")

# ---------------------------------------------------------------------------
# CALIBRATION: screen_px = SLOPE * raw + OFFSET, clamped to the screen.
# Measured from a 9-dot round using the MEDIAN of each contact's samples
# (fitting only the first frame of each contact gives ~30 px residuals here -
# the fingertip is still settling - versus 10-16 px for the medians).
#
# THESE NUMBERS ARE FOR ONE SPECIFIC UNIT. Re-measure for yours:
#   bash calibration/cal9-run.sh          # shows the dots, captures the taps
#   python3 calibration/parse_tap9.py /tmp/silead-raw9.txt
# The daemon also logs every touch as raw=(x,y) px=(px,py), which is usually
# enough to check a calibration without the full fit.
X_SLOPE, X_OFFSET = 0.97724, -8.9
Y_SLOPE, Y_OFFSET = 0.97004, -32.8

# If raw values appear beyond this, the device's coordinate space has changed
# under us and the calibration above is stale. (This is the failure mode that
# produces a pointer stuck in one corner.)
RAW_EXPECT_X, RAW_EXPECT_Y = 2100, 1350
# ---------------------------------------------------------------------------

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
ABS_X, ABS_Y = 0x00, 0x01
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = \
    0x2F, 0x35, 0x36, 0x39
BTN_TOUCH = 0x14A
XMAP_CODES = (ABS_X, ABS_MT_POSITION_X)
YMAP_CODES = (ABS_Y, ABS_MT_POSITION_Y)

# struct input_event is 24 bytes on 64-bit: 'l' is only 4 bytes in Python's
# standard struct mode, so the format must be explicit ("<qqHHi").
EVENT_FMT = "<qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)


def _ioc(direction, typ, nr, size):
    return (direction << 30) | (size << 16) | (ord(typ) << 8) | nr


UI_SET_EVBIT = _ioc(1, 'U', 100, 4)
UI_SET_KEYBIT = _ioc(1, 'U', 101, 4)
UI_SET_ABSBIT = _ioc(1, 'U', 103, 4)
UI_SET_PROPBIT = _ioc(1, 'U', 110, 4)
UI_DEV_CREATE = _ioc(0, 'U', 1, 0)
INPUT_PROP_DIRECT = 0x01
EVIOCGBIT = lambda ev, ln: _ioc(2, 'E', 0x20 + ev, ln)
EVIOCGABS = lambda code: _ioc(2, 'E', 0x40 + code, 24)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def make_map(slope, offset, limit):
    def f(v):
        px = int(round(slope * v + offset))
        return 0 if px < 0 else (limit if px > limit else px)
    return f


map_x = make_map(X_SLOPE, X_OFFSET, SCREEN_W - 1)
map_y = make_map(Y_SLOPE, Y_OFFSET, SCREEN_H - 1)


def find_device():
    """Resolve the PHYSICAL device by name - node numbers shift across reloads
    (event11 -> event17 across a single reboot on this tablet)."""
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            with open(path) as f:
                if f.read().strip() == DEV_NAME:
                    return "/dev/input/" + path.split("/")[4]
        except OSError:
            continue
    return None


def _bits(fd, req, nbytes):
    buf = bytearray(nbytes)
    fcntl.ioctl(fd, req, buf, True)
    return {i * 8 + b for i, byte in enumerate(buf) for b in range(8)
            if byte >> b & 1}


def create_uinput(src):
    """Mirror the physical device's capabilities, so uinput never rejects an
    event we forward; the position axes are re-ranged to screen pixels."""
    types = _bits(src, EVIOCGBIT(0, 8), 8)
    keys = _bits(src, EVIOCGBIT(EV_KEY, 96), 96)
    abses = _bits(src, EVIOCGBIT(EV_ABS, 8), 8)

    u = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    for ev in types:
        fcntl.ioctl(u, UI_SET_EVBIT, ev)
    for code in keys:
        fcntl.ioctl(u, UI_SET_KEYBIT, code)
    absmax, absmin, absfuzz, absflat = [0] * 64, [0] * 64, [0] * 64, [0] * 64
    for code in abses:
        fcntl.ioctl(u, UI_SET_ABSBIT, code)
        info = struct.unpack("<6i", fcntl.ioctl(src, EVIOCGABS(code), b"\x00" * 24))
        absmin[code], absmax[code], absfuzz[code], absflat[code] = \
            info[1], info[2], info[3], info[4]
        if code in XMAP_CODES:
            absmin[code], absmax[code] = 0, SCREEN_W - 1
        elif code in YMAP_CODES:
            absmin[code], absmax[code] = 0, SCREEN_H - 1
    # Without INPUT_PROP_DIRECT, udev tags the device as a tablet and X refuses
    # to use it as a touchscreen.
    fcntl.ioctl(u, UI_SET_PROPBIT, INPUT_PROP_DIRECT)

    name = b"silead_ts_calibrated"
    name += b"\x00" * (80 - len(name))
    dev = struct.pack("<80sHHHHI256i", name, 0x0006, 0x0000, 0x0000, 0x0001, 0,
                      *(absmax + absmin + absfuzz + absflat))
    os.write(u, dev)
    fcntl.ioctl(u, UI_DEV_CREATE)
    log(f"uinput ready: abs={sorted(abses)} keys={sorted(keys)} types={sorted(types)}")
    return u


class Tracer:
    """Per-slot sample collector; logs one line per contact when it ends."""

    def __init__(self):
        self.slot = 0
        self.raw_x, self.px_x, self.raw_y, self.px_y = {}, {}, {}, {}
        self.count = 0

    def drop(self, s):
        for d in (self.raw_x, self.px_x, self.raw_y, self.px_y):
            d.pop(s, None)

    def finish(self, s):
        if s in self.raw_x or s in self.raw_y:
            self.count += 1
            def med(d):
                return sorted(d[s])[len(d[s]) // 2] if s in d and d[s] else -1
            n = max(len(self.raw_x.get(s, [])), len(self.raw_y.get(s, [])))
            log(f"touch {self.count} slot{s}: raw=({med(self.raw_x)},{med(self.raw_y)}) "
                f"px=({med(self.px_x)},{med(self.px_y)}) n={n}")
        self.drop(s)

    def finish_all(self):
        for s in set(self.raw_x) | set(self.raw_y):
            self.finish(s)


def run_once(seen_scale_warning):
    src_path = find_device()
    if not src_path:
        raise FileNotFoundError(DEV_NAME)
    inp = os.open(src_path, os.O_RDONLY | os.O_NONBLOCK)
    out = create_uinput(inp)
    log(f"translating {src_path} -> silead_ts_calibrated")

    tr = Tracer()
    drops = 0
    seen_btn = False
    buf = b""
    try:
        while True:
            r, _, _ = select.select([inp], [], [], 30)
            if not r:
                continue  # idle: this chip is silent when untouched
            data = os.read(inp, EVENT_SIZE * 512)
            if not data:
                raise OSError("device returned EOF")
            buf += data
            while len(buf) >= EVENT_SIZE:
                chunk, buf = buf[:EVENT_SIZE], buf[EVENT_SIZE:]
                sec, usec, etype, code, value = struct.unpack(EVENT_FMT, chunk)

                if etype == EV_ABS and code in XMAP_CODES:
                    if not seen_scale_warning and value > RAW_EXPECT_X:
                        seen_scale_warning = True
                        log(f"!! raw x={value} is outside the calibrated space "
                            f"(expected <= {RAW_EXPECT_X}) - the device's coordinate "
                            f"space changed; recalibrate with cal9-run.sh")
                    px = map_x(value)
                    tr.raw_x.setdefault(tr.slot, []).append(value)
                    tr.px_x.setdefault(tr.slot, []).append(px)
                    value = px
                elif etype == EV_ABS and code in YMAP_CODES:
                    if not seen_scale_warning and value > RAW_EXPECT_Y:
                        seen_scale_warning = True
                        log(f"!! raw y={value} is outside the calibrated space "
                            f"(expected <= {RAW_EXPECT_Y}) - the device's coordinate "
                            f"space changed; recalibrate with cal9-run.sh")
                    py = map_y(value)
                    tr.raw_y.setdefault(tr.slot, []).append(value)
                    tr.px_y.setdefault(tr.slot, []).append(py)
                    value = py
                elif etype == EV_ABS and code == ABS_MT_SLOT:
                    tr.slot = value
                elif etype == EV_ABS and code == ABS_MT_TRACKING_ID:
                    if value < 0:
                        tr.finish(tr.slot)
                    else:
                        tr.drop(tr.slot)
                elif etype == EV_KEY and code == BTN_TOUCH:
                    seen_btn = True
                    if value == 0:
                        tr.finish_all()

                # Forward everything; a write the uinput device cannot accept is
                # counted rather than fatal (mirroring capabilities should make
                # this impossible, but silence would be worse than a warning).
                try:
                    os.write(out, struct.pack(EVENT_FMT, sec, usec, etype, code, value))
                except OSError as e:
                    drops += 1
                    if drops in (1, 10, 100) or drops % 1000 == 0:
                        log(f"!! uinput rejected type={etype} code={code}: {e} "
                            f"(dropped={drops})")
    finally:
        os.close(inp)
        os.close(out)
    return seen_scale_warning


def main():
    log(f"start: device={DEV_NAME} screen={SCREEN_W}x{SCREEN_H} "
        f"x_px={X_SLOPE}*raw{X_OFFSET:+g} y_px={Y_SLOPE}*raw{Y_OFFSET:+g}")
    warned = False
    missing = 0
    while True:
        try:
            warned = run_once(warned)
            missing = 0
        except FileNotFoundError:
            missing += 1
            if missing in (1, 10, 100) or missing % 600 == 0:
                log(f"{DEV_NAME} not present (attempt {missing}) - waiting")
        except OSError as e:
            log(f"device error: {e} - re-resolving in 2s")
        except Exception as e:  # keep the service alive on anything unexpected
            log(f"unexpected error: {e!r} - retrying in 2s")
        time.sleep(2)


if __name__ == "__main__":
    main()
