# tools/ — third-party, GPLv2

These files are **not** part of this project. They come from
**[onitake/gsl-firmware](https://github.com/onitake/gsl-firmware)**, specifically its
`tools/` directory, which that project publishes under the **GNU General Public
License v2**. They are bundled here only so that `firmware/build-firmware.sh` works
from a clean clone.

| File | Purpose |
|---|---|
| `fwtool` | Converts Silead firmware between formats: builds a blob from an unscrambled `GSL_TS_CFG` header (`-2`), from a scrambled Windows `SileadTouch.fw` (`-3`), and exports plain format (`-x`). |
| `Firmware/Silead.pm` | The perl module `fwtool` loads (it does `use lib dirname(__FILE__)`, so the `Firmware/` directory must sit next to the script). |

Copyright (c) 2016-2017 Gregor Riepl <onitake@gmail.com>. `fwtool` prints its own
notice when run: it is not endorsed by Silead Inc. and is aimed at the gslx680-acpi
driver family.

If you would rather take them from upstream — which is the better habit, since
upstream may have fixes — clone gsl-firmware and point the build script at that copy
instead:

```bash
git clone https://github.com/onitake/gsl-firmware
perl /path/to/gsl-firmware/tools/fwtool -c ...
```

See also: the gsl-firmware README's own note that the **firmware images** in that
repository are vendor-derived and may carry proprietary terms, while the **tools**
are GPLv2. The same split applies to this repository.
