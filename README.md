# PaperOS

A whole little OS for the M5Stack Cardputer. Launcher, file manager, paint, a text browser, a game emulator, an app store, an offline AI chat, a 3D editor, and a Lua console.

![Desktop](PaperOS_photos/20260723_124152.jpg)
![Paint](PaperOS_photos/20260723_124143.jpg)
![Games](PaperOS_photos/20260723_124230.jpg)
![3D Editor](PaperOS_photos/20260723_124348.jpg)
![myAI](PaperOS_photos/20260723_125135.jpg)
![Lua](PaperOS_photos/20260723_125233.jpg)
![Store](PaperOS_photos/20260726_135402.jpg)

## What's new in v1.3

* Browser rewritten with a small real HTML/CSS layout engine instead of a plain tag-stripper: `<style>` blocks are actually parsed (`tag`/`.class`/`#id` → color/bold/alignment), headings render bigger and bold, lists get real indentation and numbering, table cells are visually separated, `<hr>` draws an actual line.
* Browser: `<meta http-equiv="refresh">` and `location.href = "..."` JS-redirect pages are auto-followed (no JS executed, pattern matching only).
* Browser: 3 tabs with independent back/forward history, find-in-page, an in-app help screen (`?`), and images on a page can be downloaded to SD and opened in the File Manager's viewer.
* Lua: WiFi now powers off automatically while the Lua app is open (reclaims ~40-70KB it otherwise sits on all session on a board with no PSRAM) and reconnects on its own the moment a script actually calls `net.get`/`net.post`/`net.connect`/`net.scan`.
* Lua: dropped unused real-Lua stdlib modules (`package`, the real `os`/`io`, `utf8`, `debug` - none of which this OS ever exposed or needed) for permanent RAM savings, and added `os.stack()` to measure real task-stack headroom.
* Updated Lua reference: `paperos_lua_reference_v1_3.txt`.

## Get it running

Two ways to flash it:

* **No build needed**: search "PaperOS" in the **M5Burner** app and flash straight from there, or flash `PaperOS_full_v1.3.bin` directly from your browser at [esphome.io](https://web.esphome.io/) (Connect → pick the file → address `0x0`).
* **Build it yourself**: build with `pio run -e paperos-cardputer`, run `merge.py` to bundle the bootloader, partitions, firmware, and LittleFS into `PaperOS_full.bin`, then flash to address `0x0`.

If updating from an older build, do a full reflash rather than an incremental update. Keep a FAT32 SD card inserted before first boot.

## Before you touch each app

| App | Needs |
|---|---|
| Games | `.nes`/`.gb`/`.gbc` need `PaperEMU.extension` (or `EmulatorV3.4.extension`) + ROMs in `/PaperOS/games/`. `.ard` (Arduboy) games only require the ROM in `/PaperOS/games/` |
| Store | Needs Wi-Fi. Installs apps directly to `/lua/` |
| myAI | Requires `model.bin` in `/PaperOS/` |
| Music | Opens `.wav`/`.mp3` files from any folder on the SD card |
| 3D Editor | `.obj` files in `/PaperOS/3d/` |
| Browser | Saves pages to `/PaperOS/saved_links/`, downloaded images to `/PaperOS/browser_img/` |
| Paint | Opens/saves images anywhere |

## The apps

**File Manager**: browses storage, opens images in a viewer with zoom/pan/rotate, launches ROMs via emulator, hands audio to Music, and identifies unknown files. Press `M` for the context menu.

**Paint**: Pen, Line, Rect, FillRect, Ellipse, Circle, Triangle, Fill, Eraser, EyeDropper, Outline, Text. Press `Tab` to open tools/colors, Enter to select, `M` for menu options.

**Games**: Runs NES/GB/GBC via PaperEMU extension. Arduboy `.ard` games flash directly to the spare OTA slot.

**Store**: Scrollable list of apps fetched from GitHub. Use `;`/`.` to navigate, Enter to install, `D` to delete, `R` to refresh.

**Music**: Plays WAV/MP3 files from any directory on your SD card.

**Browser**: Text-mode web browser with a small real HTML/CSS layout engine (headings, bold/color from CSS, lists, tables, blockquotes). 3 tabs, back/forward history, bookmarks (`B`/`K`), find-in-page (`F`), page outline (`O`), images list (`I`), save page with `D`, full key reference with `?`.

**myAI**: Offline language model running on TinyStories weights loaded directly from SD card.

**3D Editor**: Orbit and vertex editor for `.obj` files.

**Lua**: Lua 5.4 console with hardware API support. WiFi is off by default to save RAM and comes back automatically the moment a script needs the network.

**Notes / Calculator / Clock / Piano / Settings / SysInfo**: Small built-in utility apps. Settings includes the Wi-Fi network scanner.

## Known issues

* Music player may crash after long sessions due to buffer overflow. Reboot the device if this happens.
* Browser runs slow on heavy web pages, and sites with aggressive bot/CDN protection (e.g. Reddit) may return blocked or garbled responses - no gzip/brotli decompression or browser-fingerprint spoofing.
* myAI text generation speed is limited by SD card read speeds.

## Credits

Built by Artem76228.
