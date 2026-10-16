#!/usr/bin/env python3
"""Raw frame dumper for the silead touch device - ground truth for calibration.

Usage: rawdump.py [seconds] [outfile] [--touches N]

Prints one line per completed SYN_REPORT frame that carried events, so a real tap
and an idle frame can be told apart, plus the device's EVIOCGABS ranges. This is
the instrument to use when calibrating: `xinput test-xi2` reports a different
(0..65535) scale, and calibrating from it pins the pointer to a corner.

Set SILEAD_DEV if the input device is not named "silead_ts".

Needs root (or input-group membership) to read /dev/input/eventN.
"""
import glob, os, select, struct, sys, time, fcntl

DEV_NAME = os.environ.get("SILEAD_DEV", "silead_ts")
FMT = "<qqHHi"
SZ = struct.calcsize(FMT)

ABS = {0x00: "ABS_X", 0x01: "ABS_Y", 0x18: "ABS_PRESSURE", 0x2f: "MT_SLOT",
       0x35: "MT_POS_X", 0x36: "MT_POS_Y", 0x39: "MT_TRACK", 0x3a: "MT_PRESSURE"}
KEY = {0x14a: "BTN_TOUCH", 0x145: "BTN_TOOL_FINGER", 0x14b: "BTN_STYLUS",
       0x14d: "BTN_TOOL_QUINTTAP"}


def eviocgabs(fd, code):
    """EVIOCGABS(code) = _IOR('E', 0x40+code, struct input_absinfo) - 6 x __s32."""
    req = (2 << 30) | (24 << 16) | (ord('E') << 8) | (0x40 + code)
    try:
        return struct.unpack("<6i", fcntl.ioctl(fd, req, b"\x00" * 24))
    except OSError:
        return None


def find():
    for p in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            with open(p) as f:
                if f.read().strip() == DEV_NAME:
                    return "/dev/input/" + p.split("/")[4]
        except OSError:
            pass
    return None


def fmt(etype, code, value):
    if etype == 3:
        return f"{ABS.get(code, hex(code))}={value}"
    if etype == 1:
        return f"{KEY.get(code, hex(code))}={value}"
    return f"type{etype}:{code:#x}={value}"


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    out = open(sys.argv[2], "w") if len(sys.argv) > 2 else sys.stdout
    src = find()
    if not src:
        print(f"no device named {DEV_NAME} found", file=out, flush=True)
        return 1
    fd = os.open(src, os.O_RDONLY | os.O_NONBLOCK)
    print(f"# {src} for {secs}s", file=out, flush=True)
    for name, code in (("ABS_X", 0x00), ("ABS_Y", 0x01), ("MT_SLOT", 0x2f),
                       ("MT_POS_X", 0x35), ("MT_POS_Y", 0x36), ("MT_TRACK", 0x39)):
        a = eviocgabs(fd, code)
        print(f"# absinfo {name}: value={a[0]} min={a[1]} max={a[2]} fuzz={a[3]} "
              f"flat={a[4]} res={a[5]}" if a else f"# absinfo {name}: <ioctl failed>",
              file=out, flush=True)

    want_touches = 0
    if "--touches" in sys.argv:
        want_touches = int(sys.argv[sys.argv.index("--touches") + 1])

    t0 = time.time()
    frame, lines, empty, printed = [], 0, 0, 0
    touches, btn_down, track_down, seen_btn = 0, False, False, False
    while True:
        left = secs - (time.time() - t0)
        if left <= 0 or (want_touches and touches >= want_touches):
            break
        r, _, _ = select.select([fd], [], [], min(left, 0.5))
        if not r:
            continue
        data = os.read(fd, SZ * 1024)
        i = 0
        while i + SZ <= len(data):
            sec, usec, etype, code, value = struct.unpack(FMT, data[i:i + SZ])
            i += SZ
            if etype == 0 and code == 0:
                lines += 1
                if frame:
                    if printed < 600:
                        print(f"t={time.time()-t0:7.3f} [{len(frame):2d}ev] "
                              + " ".join(frame), file=out, flush=True)
                        printed += 1
                    frame = []
                else:
                    empty += 1
            else:
                frame.append(fmt(etype, code, value))
                if etype == 1 and code == 0x14A:  # BTN_TOUCH
                    seen_btn = True
                    if value == 1 and not btn_down:
                        btn_down = True
                    elif value == 0 and btn_down:
                        btn_down = False
                        touches += 1
                elif etype == 3 and code == 0x39 and not seen_btn:  # MT_TRACKING_ID
                    if value >= 0 and not track_down:
                        track_down = True
                    elif value < 0 and track_down:
                        track_down = False
                        touches += 1
    print(f"# frames={lines} with-events={lines-empty} empty={empty} "
          f"printed={printed} touches={touches}", file=out, flush=True)
    if out is not sys.stdout:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
