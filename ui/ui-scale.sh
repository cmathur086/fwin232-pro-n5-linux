#!/bin/bash
# Set the UI scale on a high-DPI Linux tablet.
#
#   bash ui-scale.sh 200     # recommended on a ~224 PPI panel (e.g. 1920x1200 @ 10.1")
#   bash ui-scale.sh 100     # normal desktop density
#
# WHY NOT Xft/DPI: raising DPI inflates FONTS ONLY, leaving window and widget
# metrics at 1x, so any app that sizes a window from its content clips its own
# text (on this tablet: the Whisker start menu drew 2x text into a 460x500 window
# and cut its own app list and tab bar off; the mintwelcome dialog did the same).
# Gtk/WindowScalingFactor scales fonts, metrics and window sizes together.
#
# Xft/DPI is therefore pinned to 96, because GTK's font size is
# points x dpi/72 x scale - DPI 192 PLUS scale 2 would give 4x, not 2x.
#
# XFCE only offers integer scaling. For a level in between you need the DPI route
# and its clipping trade-off.
#
# Takes effect immediately (the panel restarts itself) and persists in xfconf.
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

case "${1:-200}" in
  100|1) SCALE=1; PANEL=32; CURSOR=24 ;;
  200|2) SCALE=2; PANEL=56; CURSOR=36 ;;
  *) echo "usage: ui-scale.sh [100|200]" >&2; exit 1 ;;
esac

xfconf-query -c xsettings -p /Xft/DPI -n -t int -s 96
xfconf-query -c xsettings -p /Gtk/WindowScalingFactor -n -t int -s "$SCALE"
xfconf-query -c xsettings -p /Gtk/CursorThemeSize -n -t int -s "$CURSOR"
xfconf-query -c xfce4-panel -p /panels/panel-1/size -s "$PANEL"
xfce4-panel -r
sleep 2
echo "UI scale ${1:-200}% (WindowScalingFactor=$SCALE, panel=${PANEL}px, cursor=${CURSOR}px)"
echo
echo "Reminders for this panel:"
echo "  - the panel clock is sized from DPI and does NOT follow the scale factor;"
echo "    raise it explicitly or it gets smaller than it was:"
echo "      xfconf-query -c xfce4-panel -p /plugins/plugin-N/digital-time-font -s 'Sans Bold 11'"
echo "  - Firefox follows NEITHER setting. Set the ratio in the profile's user.js:"
echo "      user_pref(\"layout.css.devPixelsPerPx\", \"2.0\");"
echo "  - the on-screen keyboard should be docked, not floating:"
echo "      gsettings set org.onboard.window docking-enabled true"
echo "      gsettings set org.onboard.window.landscape dock-height 420"
