# Minimal — a skin for foobar2000 mobile

A quiet now-playing screen: the full format line where you can actually read it,
a large cover, a seekbar that tells you what's left, and three buttons.

<img src="screenshots/portrait-rounded.png" width="300" alt="Minimal, portrait">
<img src="screenshots/landscape-rounded.png" width="640" alt="Minimal, landscape">

More in [`screenshots/`](screenshots) — the square-corner variant, and a track
with no embedded artwork.

Built on **[NewMoon 2.0](#attribution)** by TAOKA-Daiki. What's original here is
the layout, the format line, and the generator that produces every canvas.

---

## Install

1. Download `Minimal-r2.0.0.fbskin` (rounded artwork corners) or
   `Minimal-s2.0.0.fbskin` (square) from [Releases](../../releases).
2. Open it on your device and let foobar2000 mobile import it, or drop it into
   foobar's Skins folder via the Files app.
3. foobar2000 mobile → Settings → Skin → **Minimal**.

Skin format 2, so it needs a foobar2000 mobile version that supports it (v1.5 or
newer). Both normal and status-bar-hidden canvases ship, so it works either way.

---

## What it changes

- **Full format line** — `ALAC · 840 kbps · 16-bit · 44.1 kHz`, at a readable
  size: above the art in portrait, beside it in landscape
- **Large album art**, with album (italic) and year with it
- **Title and artist**, centred
- **Seekbar with elapsed left, remaining right**, on the same row
- **Transport only** — prev / play / next. Shuffle, repeat and next-track are gone
- No position dot, no clipped text

---

## Device coverage

Nineteen canvases, registered by aspect ratio rather than by device, so a phone
that finds a NewMoon canvas finds a Minimal one too:

- **Portrait** 9:16, 9:18, 9:19.5, 9:20, 9:21, 9:22 · status-bar-hidden 9:16 and
  9:19.5 · tablet 12:16, 12:18
- **Landscape** 16:9, 17:9, 19.5:9, 20:9, 21:9, 22:9, 23:9 · tablet 16:12, 18:12

If your device lands on something unlisted, open an issue with the model and the
display info from **Tools → Console**, and it's a one-line addition.

---

## Build from source

```bash
python gen_format2.py
```

Produces both variants from `NewMoon2.0_unpacked/` (assets and LICENSE come from
it). `--source` points elsewhere if you keep it somewhere else.

**`assets/` wins over the source package.** Three seekbar images are ours, not
NewMoon's — a plain **white** played-bar and a **fully transparent** marker (no
dot). NewMoon ships a rainbow `dawn` gradient and a visible marker under the same
filenames, so a build that takes everything from the source package comes out
with a dotted, multicoloured timeline. Keep those three in `assets/`.

### How the layouts are generated

`gen_format2.py` holds the design once and emits all 19 canvases from it.

- **Sizes scale with width** (the cover has to stay square and fit), and the
  leftover height splits evenly into the two breathing gaps — above the title and
  above the seekbar.
- **Landscape** puts a square, vertically centred cover on the left with an info
  column to its right. The cover is height-driven but **also capped by width** —
  on a squarish tablet canvas (16:12) a full-height square swallows the row and
  pushes the transport buttons off the right edge. It's inset from the left by the
  same margin it has above and below, so the rounded corners have black to round
  against.
- **The codec/album/year block is anchored to the cover top**, flush with it, so
  it stays with the cover when the width cap moves it.

---

## Notes for anyone writing a format-2 skin

Not documented anywhere I could find, and each one cost me time:

- **A `.fbskin` is a plain ZIP** with **one** top-level folder named after the
  skin. No custom container tool — just `zip`/`unzip`.
- **Every text file is UTF-16** (LE, with BOM). Write UTF-8 and foobar silently
  ignores the file; the skin loads looking like it did nothing.
- The definition file is **`skindef.txt`** and must declare **`skin-format: 2`**.
- Canvases are registered **per aspect ratio at a canonical width**
  (`skin: 1125x2500 portrait-9-20-1125x2500.txt`), not per device. Tablet entries
  take a `-tablet` suffix on the size key.
- Colours come from named font keys (`[font-info]`, `[font-artist]`) defined in
  `skindef.txt`, rather than format 1's inline `[rgb-r-g-b]`.
- **Format 2 seats label text lower inside the same box than format 1 did.** If
  you're porting a hand-tuned format-1 layout, reproducing its coordinates isn't
  enough — trust your eyes over the numbers.

### Sample rate in kHz

The obvious titleformatting for a `44.1 kHz` readout kept erroring — there's no
`$concat` to glue the pieces. Integer division for the whole part and mod for the
decimal works:

```
$div(%samplerate%,1000).$div($mod(%samplerate%,1000),100) kHz
```

`44100` → `44.1`. The literal `.` between the two `$div` calls does the
concatenation. (NewMoon 2.0 solves the same problem a different way, with
`$insert` — either is fine.)

---

## Repo layout

| Path | What |
|---|---|
| `gen_format2.py` | the generator — design lives here, emits all 19 canvases |
| `assets/` | our seekbar images + artwork placeholder; override the source package |
| `NewMoon2.0_unpacked/` | NewMoon 2.0, unzipped — asset and LICENSE source |
| `*.fbskin` | built skins |

---

## Status

Generated, geometrically validated (no overlaps, no out-of-bounds, cover square
and vertically centred on all 19 canvases), and **confirmed on device** in
portrait and landscape (iPhone, 19.5:9).

**The tablet canvases (12:16, 12:18, 16:12, 18:12) have not been loaded on real
hardware.** They're where the width cap changes the layout, and they've needed two
corrections already. Please report anything that sits wrong.

---

## Attribution

Built on **NewMoon** for foobar2000 mobile by **TAOKA-Daiki**. The artwork frames,
icons, transport glyphs and seekbar images are theirs; the layouts, format line
and generator are mine (Eric Zhang).

NewMoon 2.0 ships this licence, and a copy travels inside every Minimal build as
required:

> Copyright (c) 2024 TAOKA-Daiki
>
> Permission is hereby granted, free of charge … to deal in the Software,
> including the **non-commercial** rights to use, copy, modify, merge, publish,
> distribute, and/or sublicense copies … The above copyright notice and this
> permission notice shall be included in all copies or substantial portions of
> the Software.

Non-commercial, modified, redistributed, with the notice included — so this is in
the clear.

My own contributions (`gen_format2.py`, the generated layouts): MIT.
