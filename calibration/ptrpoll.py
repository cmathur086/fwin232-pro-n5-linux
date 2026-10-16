#!/usr/bin/env python3
"""Poll XQueryPointer and print the cursor position.

Ground truth for verifying a calibration: X's *emulated* motion events lag by one
event on this hardware, so watching motion events can mislead you about where a
touch actually landed. XQueryPointer does not lag.

Usage: python3 ptrpoll.py [count]      (default 600, ~0.2s apart)
Needs DISPLAY and XAUTHORITY set.
"""
import ctypes, sys, time

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint)]
x11.XQueryPointer.restype = ctypes.c_int

d = x11.XOpenDisplay(None)
if not d:
    print("NO-DISPLAY", flush=True)
    sys.exit(1)
root = x11.XDefaultRootWindow(d)
rr = ctypes.c_ulong(); cr = ctypes.c_ulong()
rx = ctypes.c_int(); ry = ctypes.c_int()
wx = ctypes.c_int(); wy = ctypes.c_int()
mask = ctypes.c_uint()

n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
for i in range(n):
    ok = x11.XQueryPointer(d, root, ctypes.byref(rr), ctypes.byref(cr),
                           ctypes.byref(rx), ctypes.byref(ry),
                           ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
    print(f"{time.monotonic():.3f} {rx.value} {ry.value} ok={ok}", flush=True)
    time.sleep(0.2)
