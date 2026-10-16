# firmware/

The touch firmware for this tablet, and everything needed to rebuild it.

| File | What it is |
|---|---|
| `mssl1680.fw` | **The working firmware.** 41184 bytes, plain format, `sha256 df1f7d8e7fe70e0666379b5d5311b21d0c22b6aad6759b8ece703c909d5532ad`. This exact file is running on the device. |
| `WB_SF133A3692_P_X64_JYK_220107.h` | The ODM panel config header it was built from — extracted from the official Weibu/Silead Windows driver package. `WB` = Weibu (the ODM). |
| `build-firmware.sh` | Reproduces `mssl1680.fw` from the header, byte for byte. |
| `tools/` | `fwtool` + `Firmware/Silead.pm`, third-party from [onitake/gsl-firmware](https://github.com/onitake/gsl-firmware) (GPLv2 — see `tools/README.md`). |

## Install

```bash
sudo mkdir -p /lib/firmware/silead
sudo cp mssl1680.fw /lib/firmware/silead/mssl1680.fw
sudo modprobe -r silead; sudo modprobe silead
sudo dmesg | grep -i silead      # expect: Silead chip ID: 0x80360000
```

The filename matters: the kernel requests `silead/<acpi-id>.fw`, and this device's
ACPI ID is `MSSL1680`.

## Rebuild

```bash
./build-firmware.sh              # reproduces mssl1680.fw and checks the hash
```

Verified on the device: building from `WB_SF133A3692_P_X64_JYK_220107.h` with this
command line produced a byte-identical file to the one running in
`/lib/firmware/silead/`, so the recipe above is not approximate — it is the exact
provenance of the working blob.

```bash
perl tools/fwtool -c WB_SF133A3692_P_X64_JYK_220107.h -2 \
     -m 3692 -w 1360 -h 2170 -t 10 -f track out.fw
perl tools/fwtool -x plain.fw out.fw      # -x takes the OUTPUT first!
```

## Two things that will waste your evening

1. **`out.fw` is not the file you install.** The new-style build (20616 bytes here)
   is an intermediate. The chip wants the **plain** export (41184 bytes). Installing
   `out.fw` produces a device that looks alive and behaves badly.
2. **`fwtool -x` takes output before input.** Reversed, it silently gives you
   something that is not what you built.

## Provenance and licensing

`mssl1680.fw` and `WB_SF133A3692_*.h` are **vendor-derived**. The header came out of
a Silead/Weibu MSSL1680 Windows driver package (the one used here was v15.17.3.624,
found via the Microsoft Update Catalog — search `MSSL1680` — and mirrored at
oemdrivers.com; the archive's SHA-256 began `96effc3f…`).

They are included here so that someone holding this tablet can have a working
touchscreen instead of a brick — the same call the gsl-firmware project makes when it
redistributes vendor firmware images. **The original manufacturer may assert rights
over these files.** If you are the rights holder and want them removed, say so and
they will be.

The tooling in `tools/` is a different matter: it is GPLv2 and freely redistributable
(see `tools/README.md`).
