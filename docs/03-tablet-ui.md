# 3. Making the tablet UI actually usable

1920x1200 across a 10.1" panel is **~224 PPI**. At the 96-DPI default everything
renders at roughly **45% of physically comfortable size** — readable at 30 cm, not
tappable with a finger.

There are **three separate mechanisms** involved on a GTK/XFCE desktop, they are not
interchangeable, and getting the wrong one produces bugs that look like app bugs.

## 1. System-wide: `Gtk/WindowScalingFactor`, NOT `Xft/DPI`

| Setting | What it scales | Use it? |
|---|---|---|
| `xsettings/Gtk/WindowScalingFactor = 2` | fonts **and** widget metrics **and window sizes** together | **yes** |
| `xsettings/Xft/DPI = 192` | **fonts only** | **no — not alone** |

Raising DPI alone inflates the text inside windows whose size was computed from 1x
content metrics. Any app that sizes a window from its content then **clips its own
text**. Concrete failures on this device at DPI 192:

- The Whisker start menu drew 2× text into a 460x500 window: the app list was cut
  off and the bottom tab bar was clipped mid-word.
- The mintwelcome dialog clipped its own content and pushed its button out of view.

Switching to the scale factor fixed both, with no per-app work.

**Pin `Xft/DPI` to 96 when you use the scale factor**, because GTK's font size is
`points × dpi/72 × scale` — DPI 192 *plus* scale 2 gives 4×, not 2×.

```
bash ui-scale.sh 200    # recommended for this panel
bash ui-scale.sh 100    # back to desktop density
```

XFCE only offers integer scaling here. Anything between 100% and 200% means going
back to the DPI route and accepting its clipping.

### Per-element follow-ups

- **Panel**: row height is in device pixels — set `xfce4-panel:/panels/panel-1/size`
  to ~56.
- **Clock**: the panel sizes its clock text from **DPI** and does *not* follow the
  scale factor, so at DPI 96 it gets *smaller* than it was. Raise the clock's fonts
  explicitly (`xfce4-panel:/plugins/plugin-N/digital-time-font`).
- **Cursor**: `Gtk/CursorThemeSize` (~36 at 2×).

## 2. Firefox has its own scale, and here it followed nothing

Firefox 142 on this box ignored **both** `Xft/DPI` and the GTK scale factor. Do not
assume; measure. A page containing a div of known CSS width, screenshotted and
compared against the screen's pixel width, showed a 500 CSS px bar drawing **~497
device px** — i.e. `devicePixelRatio 1.0` while the rest of the desktop was at 2×.
That is exactly why the browser chrome looked small next to everything else.

Fix, in `<profile>/user.js` (read at every start, so it survives `prefs.js`
rewrites):

```js
user_pref("layout.css.devPixelsPerPx", "2.0");
```

Re-measured afterwards: the same bar drew ~997 device px (ratio 2.0). This scales
the chrome **and** the page content.

`../ui/dpr-test.html` is the ruler page used for both measurements — keep it, it
settles this question in one screenshot on any machine.

**Dead end:** `browser.uidensity = 2` ("touch" density). Firefox writes it to
`prefs.js` and renders **identically** in 142. Don't reach for it.

## 3. The on-screen keyboard needs docking, not just size

Onboard's default here was a **floating** keyboard (`docking-enabled false`) at a
hard-coded 700x205 in the corner of the screen — useless for typing while looking at
what you type.

```bash
gsettings set org.onboard.window docking-enabled true
gsettings set org.onboard.window.landscape dock-width  1920
gsettings set org.onboard.window.landscape dock-height 420
```

It then docks full-width at the bottom and — usefully — **above the panel**, so the
taskbar stays usable while the keyboard is up. Auto-show still triggers on text-field
focus, and the keys are ~420 px tall, which is a comfortable touch target.

## 4. A screenshot trap worth knowing

**With `xfwm4` compositing on, a full-screen screenshot does not capture the Whisker
menu popup.** The grab comes back with the menu missing or its body blank, which
looks exactly like a rendering bug — the body renders, it just isn't in the grab.
Toggle compositing off for the shot:

```bash
xfconf-query -c xfwm4 -p /general/use_compositing -s false   # take the shot
xfconf-query -c xfwm4 -p /general/use_compositing -s true    # restore
```

## Dead ends recorded so they are not retried

- **Whisker Menu `menu-width` / `menu-height`**: these xfconf properties still
  *exist* in 2.8.3 but are **ignored**. Setting them (900x1000, then 300) changed
  nothing. The menu's apparent clipping was the DPI-vs-metrics problem above, not a
  size setting.
- **`browser.uidensity=2`** — see above, no effect in Firefox 142.
- **Qt / GTK2 / some Electron apps** read DPI only, so they stay small under the
  scale factor. Each needs its own environment variable (`QT_SCALE_FACTOR`, etc.).
  On a Mint/XFCE desktop this barely shows up, since the shipped apps are GTK3.
