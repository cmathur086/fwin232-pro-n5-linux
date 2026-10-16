# Fusion5 FWIN232 PRO N5 — Linux touch + tablet UI

Everything needed to turn this Windows-only 10.1" tablet into a usable Linux
tablet: the **touch firmware** the vendor never shipped for Linux, a
**calibration translator** that works around X refusing to calibrate the panel at
all, and the **UI scaling** that makes a 1920x1200 / ~224 PPI screen usable with
fingers.

Every step here was run on the real device and verified — including a firmware
build that reproduces the working blob **byte-for-byte** (see
[`firmware/`](firmware/)).

> **Touch dead after installing Linux?** Go straight to
> [docs/01-firmware.md](docs/01-firmware.md). That is the fix, and it is the part
> that took a full night to find.

## The device

| | |
|---|---|
| Model | Fusion5 FWIN232 PRO N5 (10.1", 1920x1200, ~224 PPI) |
| Touch controller | Silead MSSL1680-class — chip ID `0x80360000`, i2c, ACPI `MSSL1680` |
| Panel config header | `WB_SF133A3692_P_X64_JYK_220107.h` (Weibu = the ODM) |
| Tested OS | Linux Mint 22.2 XFCE (X11) |
| In-tree driver | `silead` → `/lib/modules/*/kernel/drivers/input/touchscreen/silead.ko` |

The same controller family shows up in a lot of cheap Intel tablets. The
**method** transfers even where the exact firmware blob does not — the config
header is panel-specific and has to come from your own device's driver package.

## The three problems, and what fixes each

1. **No touch at all.** `silead_ts` loads, the chip answers, but the firmware blob
   is a Windows-only file and no community archive has the right one. Wrong blobs
   give ghost touches, combs or warped axes. → **Build the blob from the ODM's own
   config header.** → [docs/01-firmware.md](docs/01-firmware.md)

2. **Touch works but is unusable** — axes mirrored and compressed into part of the
   screen — and X ignores every calibration you give it: the libinput
   `Calibration Matrix` property is inert in a post-boot session, a udev
   `LIBINPUT_CALIBRATION_MATRIX` rule does nothing, and a runtime `set-prop`
   worked exactly once, before a restart. → **Read the device yourself and emit a
   corrected one** (a ~200-line stdlib Python uinput daemon).
   → [docs/02-calibration.md](docs/02-calibration.md)

3. **The UI is unusably small** — 1920x1200 across 10.1" is ~224 PPI, so the
   96-DPI default renders everything at ~45% of comfortable physical size. And the
   obvious fix (raise the DPI) **breaks apps**. → **`Gtk/WindowScalingFactor`,
   not DPI.** → [docs/03-tablet-ui.md](docs/03-tablet-ui.md)

Stuck on a symptom rather than a topic? → [docs/04-troubleshooting.md](docs/04-troubleshooting.md)

## Repository layout

```
firmware/       The touch firmware: the working blob, the ODM header it came
                from, the build tooling, and the exact reproduction recipe.
translator/     silead_translate.py — the calibrated uinput touch device, its
                systemd unit, and the udev rule that hides the raw device from X.
calibration/    Measure-and-fit tools: raw frame dumper, 9-dot page, fitter.
ui/             UI scale script + a device-pixel-ratio ruler page.
history/        One dead end kept as a warning (the libinput matrix attempt).
docs/           The write-ups, including what failed and why.
```

## Quick start

### 1. Firmware (do this first — nothing else matters without it)

```bash
# Either use the blob in this repo (same tablet model):
sudo mkdir -p /lib/firmware/silead
sudo cp firmware/mssl1680.fw /lib/firmware/silead/mssl1680.fw
# ...or rebuild it yourself and confirm you get df1f7d8e... :
cd firmware && ./build-firmware.sh

sudo modprobe -r silead; sudo modprobe silead
# The driver prints the chip ID on probe; check it found the panel:
sudo dmesg | grep -i silead
```

### 2. Calibrated touch

```bash
sudo cp translator/silead_translate.py /opt/fwin232/
sudo cp translator/silead-translate.service /etc/systemd/system/
sudo cp translator/99-silead-ignore.rules /etc/udev/rules.d/
sudo systemctl daemon-reload && sudo systemctl enable --now silead-translate
sudo udevadm control --reload-rules
```

Then **recalibrate for your own panel** — the constants shipped here are for one
specific unit. `docs/02-calibration.md` has the 9-dot procedure; it takes about a
minute and the daemon logs each touch as `raw=(x,y) px=(px,py)` so you can verify
it as you go.

### 3. UI scale

```bash
cp ui/ui-scale.sh ~/touch-fw/ && bash ~/touch-fw/ui-scale.sh 200
```

## What is in here, licence-wise

- Code written for this project: **MIT** (see [LICENSE](LICENSE)).
- `firmware/tools/` — `fwtool` and `Firmware/Silead.pm` are third-party, from
  [onitake/gsl-firmware](https://github.com/onitake/gsl-firmware), whose tools are
  **GPLv2**. See [firmware/tools/README.md](firmware/tools/README.md).
- `firmware/mssl1680.fw` and `firmware/WB_SF133A3692_*.h` are **vendor-derived**
  (compiled from / extracted from an OEM driver package published by Weibu/Silead).
  They are included so that someone with this tablet can get a working touchscreen
  instead of a brick, in the same spirit as the gsl-firmware project, which
  redistributes vendor firmware images for hundreds of devices with the same
  caveat: *the original manufacturer may assert rights over them.*

## Credits

- **[onitake/gsl-firmware](https://github.com/onitake/gsl-firmware)** — `fwtool`,
  without which the ODM header could not have been turned into anything the chip
  accepts. Everything about *how* to build the blob came from that project.
- The OEM driver package itself, found via the **Microsoft Update Catalog**
  (search `MSSL1680`) and mirrored at oemdrivers.com. It is the only source of the
  panel config header that actually matches this screen.

## Verified on

The state described here was confirmed on the device: touch calibrated and
surviving a cold reboot, raw device hidden from X by udev, auto-login working,
and the UI at 200%. Nothing here is theoretical.
