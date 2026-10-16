# 1. The touch firmware

**Symptom:** after installing Linux the touchscreen does nothing. `dmesg` shows
the driver probing and reading a chip ID, the input device may even appear, but no
touch events ever arrive. `/lib/firmware/silead/` is empty.

**Cause:** the Silead controllers do not contain their own configuration. The
Windows driver uploads a firmware blob at runtime, and that blob encodes *this
panel's* geometry and calibration. On Linux the kernel `silead` driver looks for
`/lib/firmware/silead/mssl1680.fw` (named after the ACPI ID), and if it is missing
there is nothing to run the controller with.

**What does not work:** grabbing a blob from another tablet. We tried about eight
community-hosted Silead firmwares — every one produced ghost contacts, "comb"
patterns, or axes that were warped into a fraction of the screen. The panel config
is per-device; a near-miss is worse than nothing because it looks like broken
hardware.

## The way through: use the ODM's own config header

The Windows driver package for this exact tablet contains the panel config in a
**plain-text header**, not just a compiled blob. So the firmware can be *built*
rather than guessed.

### 1. Get the OEM driver package

The driver is a Silead/Weibu MSSL1680 package (the one used here was
v15.17.3.624). Two sources that had it:

- **Microsoft Update Catalog** — search `MSSL1680`. There are ~200 entries;
  the one that matters matches ACPI ID `MSSL1680`.
- **oemdrivers.com** — search "Silead MSSL 1680"; mirrors the same package.

Verify whatever you download (the archive used here had SHA-256 starting
`96effc3f…`). You are looking for a driver package whose `x64/` directory
contains a file named like `WB_SF133A3692_P_X64_JYK_220107.h`.

> The filename is the fingerprint: `WB` = Weibu (the ODM that built the tablet),
> the long number is the panel/config revision. If your tablet is a different
> model, you need *your* package — the file will have a different name, and that
> is the file you feed to the build step below.

### 2. Build the blob

`fwtool` (bundled in [`../firmware/tools/`](../firmware/tools/), from
onitake/gsl-firmware) converts the header into the format the chip accepts:

```bash
cd firmware

# -2      input is an unscrambled GSL_TS_CFG header (the .h you just extracted)
# -m 3692 controller model
# -w -h   panel dimensions used by the controller (NOT the screen resolution)
# -t 10   max touch points
# -f track
perl tools/fwtool -c WB_SF133A3692_P_X64_JYK_220107.h -2 \
     -m 3692 -w 1360 -h 2170 -t 10 -f track out.fw

# Export to the PLAIN format the chip actually accepts.
# NOTE THE ARGUMENT ORDER: -x takes the OUTPUT file FIRST.
perl tools/fwtool -x plain.fw out.fw
```

`./build-firmware.sh` in this repo does exactly the above.

**Verified:** this recipe reproduces the working firmware byte-for-byte:

```
sha256  df1f7d8e7fe70e0666379b5d5311b21d0c22b6aad6759b8ece703c909d5532ad  plain.fw
        df1f7d8e7fe70e0666379b5d5311b21d0c22b6aad6759b8ece703c909d5532ad  (installed, working)
```

Two traps that cost time here:

- **The new-style build is not what you install.** `out.fw` (20616 bytes) is an
  intermediate; the chip wants the **plain** export (41184 bytes). Installing the
  new-style file looks like it works and behaves badly.
- **`-x` takes output first.** `fwtool -x in.fw out.fw` silently swaps what you
  think you built. Get this backwards and you will spend an hour on a firmware
  that never changed.

### 3. Install and load

```bash
sudo mkdir -p /lib/firmware/silead
sudo cp plain.fw /lib/firmware/silead/mssl1680.fw     # or this repo's firmware/mssl1680.fw
sudo modprobe -r silead; sudo modprobe silead
sudo dmesg | grep -i silead
```

A healthy probe looks like:

```
silead_ts i2c-MSSL1680:00: supply vddio not found, using dummy regulator
silead_ts i2c-MSSL1680:00: supply avdd not found, using dummy regulator
silead_ts i2c-MSSL1680:00: Silead chip ID: 0x80360000
input: silead_ts as /devices/.../input/input11
```

Then confirm the controller is actually streaming usable data — **not** by watching
the cursor (X distorts it) but by reading the raw node:

```bash
sudo python3 ../calibration/rawdump.py 10 /tmp/raw.txt   # tap the screen while it runs
head -15 /tmp/raw.txt
```

You want **one clean contact per tap**, with both X and Y changing plausibly as you
move around the screen. Ghost contacts, "combs", or one axis barely moving mean the
firmware is close but wrong — go back to step 1 and confirm you have *your* panel's
header, not a model number that merely looks similar.

### 4. Make it load at boot

The driver requests `silead/mssl1680.fw` by ACPI ID, so dropping the file in place
is all that is needed — it persists across reboots and kernel updates (it lives in
`/lib/firmware`, which is not part of the initramfs rebuild).

## If your tablet is a different MSSL1680 device

The blob will not transfer; the recipe will. Find your own driver package, take
its `*.h` config header, and run the same `fwtool` line with your controller model
and panel dimensions. If you have a compiled `.fw` but no header, `fwtool` can also
reverse-convert with `-x`, and can read scrambled Windows `SileadTouch.fw` files
with `-3`.

Then carry on to [02-calibration.md](02-calibration.md) — this panel needed it, and
yours probably will too.
