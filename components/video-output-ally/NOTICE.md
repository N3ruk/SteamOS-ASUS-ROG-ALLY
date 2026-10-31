# Attribution and provenance

**Video Output ALLY for DOCKs** is a locally maintained derivative by N3ruk
(2026), based on **Output Manager** by joeatethebeans:
https://github.com/joeatethebeans/OutputManager

The original copyright notices and BSD-3-Clause conditions are retained in
LICENSE. The new name does not imply endorsement by the upstream authors,
ASUS, Valve, or Decky.

This adaptation supplies a new video-only TypeScript panel, a small backend
adapter, cached monitor-name presentation, atomic settings handling and the
local EDID/MST selection architecture documented in README.md. The upstream
compiled frontend, audio controller and management/about/settings pages are
not part of this build. The video engine from the preceding local repair is
preserved without algorithm changes.

The frontend uses the public Decky API/UI and build tools. Dependencies and
exact build versions are recorded in package-lock.json; their respective
licenses remain applicable. The monitor icon is a new simple SVG for this panel.
