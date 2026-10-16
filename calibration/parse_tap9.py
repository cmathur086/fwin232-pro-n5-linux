#!/usr/bin/env python3
"""Segment a rawdump.py capture into touches; report kernel-scale knots + fit.

Usage: parse_tap9.py /tmp/raw9.txt [--frames N] [--expect 9]

Touches are segmented on BTN_TOUCH transitions (falling back to MT_TRACK
sign), and each touch's position is the median of its down-samples. With
--expect touches and a geometry sanity check against the 9-dot page, the
touches are matched to dots in tap order.
"""
import re, statistics, sys

DOTS = [(1, 120, 600), (2, 540, 600), (3, 960, 600), (4, 1380, 600), (5, 1800, 600),
        (6, 960, 120), (7, 960, 360), (8, 960, 840), (9, 960, 1080)]

FRAME_RE = re.compile(r"^t=\s*([\d.]+)\s+\[\s*\d+ev\]\s*(.*)$")


def frames(path):
    out = []
    for line in open(path):
        m = FRAME_RE.match(line.strip())
        if not m:
            continue
        t = float(m.group(1))
        kv = {}
        for tok in m.group(2).split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    kv[k] = int(v)
                except ValueError:
                    pass
        out.append((t, kv))
    return out


def segment(fr):
    """Return list of touches: dict(start, end, samples=[(x,y)], events=frame list).

    Every frame between the down edge and the up edge contributes samples, not
    just the frames that carry BTN_TOUCH/MT_TRACK (those appear only on the
    edges - sampling only them yields one point per touch)."""
    touches, cur = [], None
    down = False
    for t, kv in fr:
        edge = None
        if "BTN_TOUCH" in kv:
            edge = kv["BTN_TOUCH"] == 1
        elif "MT_TRACK" in kv:
            edge = kv["MT_TRACK"] >= 0
        if edge is not None:
            if edge and not down:
                cur = {"start": t, "end": t, "samples": [], "events": []}
                touches.append(cur)
            down = edge
        if cur is None:
            continue
        cur["events"].append((t, kv))
        if down:  # skip the release frame - it carries no useful position
            x = kv.get("MT_POS_X", kv.get("ABS_X"))
            y = kv.get("MT_POS_Y", kv.get("ABS_Y"))
            if x is not None and y is not None:
                cur["samples"].append((x, y))
        else:
            cur["end"] = t
            cur = None
    return touches


def fit(pairs):
    """Least-squares y = a*x + b, plus max |residual|."""
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    den = sum((p[0] - mx) ** 2 for p in pairs)
    if den == 0:
        return None
    a = sum((p[0] - mx) * (p[1] - my) for p in pairs) / den
    b = my - a * mx
    res = [abs(a * p[0] + b - p[1]) for p in pairs]
    return a, b, max(res)


def main():
    path = sys.argv[1]
    show_frames = 0
    expect = 9
    if "--frames" in sys.argv:
        show_frames = int(sys.argv[sys.argv.index("--frames") + 1])
    if "--expect" in sys.argv:
        expect = int(sys.argv[sys.argv.index("--expect") + 1])

    fr = frames(path)
    if not fr:
        print(f"no frame lines in {path}")
        return 1
    touches = segment(fr)
    print(f"frames={len(fr)} touches={len(touches)}")
    for i, tc in enumerate(touches, 1):
        if not tc["samples"]:
            print(f"  touch {i}: NO POSITION SAMPLES ({len(tc['events'])} frames)")
            continue
        xs = [s[0] for s in tc["samples"]]
        ys = [s[1] for s in tc["samples"]]
        print(f"  touch {i}: n={len(xs):3d} dur={tc['end']-tc['start']:.2f}s "
              f"first=({xs[0]},{ys[0]}) "
              f"median=({statistics.median(xs):.1f},{statistics.median(ys):.1f}) "
              f"spread=(x{max(xs)-min(xs)},y{max(ys)-min(ys)})")

    if show_frames and touches:
        print(f"--- first {show_frames} frames of touch 1 ---")
        for t, kv in touches[0]["events"][:show_frames]:
            print(f"  t={t:8.3f} " + " ".join(f"{k}={v}" for k, v in kv.items()))

    good = [tc for tc in touches if tc["samples"]]
    if len(good) != expect:
        print(f"NOTE: expected {expect} touches, got {len(good)} - not matching to dots")
        return 0

    pts = [(statistics.median([s[0] for s in tc["samples"]]),
            statistics.median([s[1] for s in tc["samples"]])) for tc in good]
    # geometry sanity check: taps 1-5 share Y, taps 6-9 share X
    row = pts[:5]
    col = pts[5:9]
    row_spread = max(p[0] for p in row) - min(p[0] for p in row)
    col_spread = max(p[1] for p in col) - min(p[1] for p in col)
    print(f"geometry: row x-spread={row_spread} (want large), "
          f"col y-spread={col_spread} (want large)")
    xs_row = [p[0] for p in row]
    print("  row x monotonic decreasing (left dot = highest raw x):",
          all(xs_row[i] > xs_row[i + 1] for i in range(len(xs_row) - 1)))

    print("--- tap order assumed = dot order ---")
    for (dot, px, py), (rx, ry) in zip(DOTS, pts):
        print(f"  dot {dot} ({px:4d},{py:4d}) <- raw ({rx:7.1f},{ry:7.1f})")

    for label, sel in (("median", lambda tc: (
                          statistics.median([s[0] for s in tc["samples"]]),
                          statistics.median([s[1] for s in tc["samples"]]))),
                       ("first ", lambda tc: tc["samples"][0])):
        sel_pts = [sel(tc) for tc in good]
        for name, idx, out in (("X", 0, 0), ("Y", 1, 1)):
            pr = [((p[idx]), d[1 + idx]) for p, d in zip(sel_pts, DOTS)]
            f = fit(pr)
            if f:
                a, b, r = f
                print(f"  {label} {name} fit: px = {a:.5f}*raw + {b:.1f}   max|res|={r:.1f}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
