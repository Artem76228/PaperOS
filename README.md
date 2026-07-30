# PaperOS

A whole little OS for the M5Stack Cardputer. Launcher, file manager, paint, a text browser, a game emulator, an app store, an offline AI chat, a 3D editor, and a Lua console.

![Desktop](PaperOS_photos/20260723_124152.jpg)
![Paint](PaperOS_photos/20260723_124143.jpg)
![Games](PaperOS_photos/20260723_124230.jpg)
![3D Editor](PaperOS_photos/20260723_124348.jpg)
![myAI](PaperOS_photos/20260723_125135.jpg)
![Lua](PaperOS_photos/20260723_125233.jpg)
![Store](PaperOS_photos/20260726_135402.jpg)

## What's new in v1.2

* Music player update: standard music folder limitations removed. You can now select and play tracks from any folder on the SD card. If the player crashes or freezes after playing a lot of files, it is likely a buffer overflow issue. A quick reboot will fix it for now while a permanent patch is being worked on.
* Wi-Fi scanner in Settings: added an automatic Wi-Fi network scanner so you no longer need to type SSIDs by hand.

## Get it running

Two ways to flash it:

* **No build needed**: search "PaperOS" in the **M5Burner** app and flash straight from there, or flash `PaperOS_full_v1.2.bin` directly from your browser at [esphome.io](https://web.esphome.io/) (Connect → pick the file → address `0x0`).
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
| Browser | Saves pages to `/PaperOS/saved_links/` |
| Paint | Opens/saves images anywhere |

## The apps

**File Manager**: browses storage, opens images in a viewer with zoom/pan/rotate, launches ROMs via emulator, hands audio to Music, and identifies unknown files. Press `M` for the context menu.

**Paint**: Pen, Line, Rect, FillRect, Ellipse, Circle, Triangle, Fill, Eraser, EyeDropper, Outline, Text. Press `Tab` to open tools/colors, Enter to select, `M` for menu options.

**Games**: Runs NES/GB/GBC via PaperEMU extension. Arduboy `.ard` games flash directly to the spare OTA slot.

**Store**: Scrollable list of apps fetched from GitHub. Use `;`/`.` to navigate, Enter to install, `D` to delete, `R` to refresh.

**Music**: Plays WAV/MP3 files from any directory on your SD card.

**Browser**: Lightweight text-only web browser. Save pages with `D`, manage bookmarks with `B`/`L`.

**myAI**: Offline language model running on TinyStories weights loaded directly from SD card.

**3D Editor**: Orbit and vertex editor for `.obj` files.

**Lua**: Lua 5.4 console with hardware API support.

**Notes / Calculator / Clock / Piano / Settings / SysInfo**: Small built-in utility apps. Settings includes the new Wi-Fi network scanner.

## Known issues

* Music player may crash after long sessions due to buffer overflow. Reboot the device if this happens.
* Browser runs slow on heavy web pages.
* myAI text generation speed is limited by SD card read speeds.

## Credits

Built by Artem76228.