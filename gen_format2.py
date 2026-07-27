#!/usr/bin/env python3
"""Minimal — skin format 2 generator.

Emits the Minimal layout across every canvas NewMoon 2.0 registers, then packs
the two variants (r = rounded artwork corners, s = square) as .fbskin zips.

Format-2 notes that bit me, so they're written down:
  * a .fbskin is a plain ZIP with ONE top-level folder named after the skin
  * every text file is UTF-16 (LE, with BOM) — not UTF-8
  * the definition file is `skindef.txt` and must declare `skin-format: 2`
  * canvases are registered per ASPECT RATIO at a canonical width, not per
    device; tablet entries take a `-tablet` suffix on the size key

Usage:  python gen_format2.py [--source "/path/to/NewMoon 2.0 (unzipped)"]
                             [--no-codec]
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

VERSION = "2.1.0"
AUTHOR = "Eric Zhang"

# ---------------------------------------------------------------- canvases
# (skindef size key, filename, width, height). Mirrors NewMoon 2.0's set so a
# device that finds a NewMoon canvas finds a Minimal one too.
PORTRAIT = [
    ("1125x1930", "portrait-notHSB-9-16-1125x1930.txt", 1125, 1930),
    ("1125x2166", "portrait-notHSB-9-19.5-1125x2166.txt", 1125, 2166),
    ("1125x2000", "portrait-9-16-1125x2000.txt", 1125, 2000),
    ("1125x2250", "portrait-9-18-1125x2250.txt", 1125, 2250),
    ("1125x2436", "portrait-9-19.5-1125x2436.txt", 1125, 2436),
    # iPhone 17 / 17 Pro / Air / 16 Pro / 15 Pro — 402x874 pt, 1206x2622 px.
    # 0.4% off the 9:19.5 canvas, so those phones already landed on 2436 and
    # rendered fine; an exact entry just stops the layout being stretched.
    ("1125x2446", "portrait-9-19.57-1125x2446.txt", 1125, 2446),
    ("1125x2500", "portrait-9-20-1125x2500.txt", 1125, 2500),
    ("1125x2625", "portrait-9-21-1125x2625.txt", 1125, 2625),
    ("1125x2750", "portrait-9-22-1125x2750.txt", 1125, 2750),
    ("1500x2000-tablet", "portrait-12-16-1500x2000.txt", 1500, 2000),
    ("1500x2250-tablet", "portrait-12-18-1500x2250.txt", 1500, 2250),
]

LANDSCAPE = [
    ("2000x1125", "landscape-16-9-2000x1125.txt", 2000, 1125),
    ("2125x1125", "landscape-17-9-2125x1125.txt", 2125, 1125),
    ("2436x1125", "landscape-19.5-9-2436x1125.txt", 2436, 1125),
    ("2446x1125", "landscape-19.57-9-2446x1125.txt", 2446, 1125),
    ("2500x1125", "landscape-20-9-2500x1125.txt", 2500, 1125),
    ("2625x1125", "landscape-21-9-2625x1125.txt", 2625, 1125),
    ("2750x1125", "landscape-22-9-2750x1125.txt", 2750, 1125),
    ("2875x1125", "landscape-23-9-2875x1125.txt", 2875, 1125),
    ("2000x1500-tablet", "landscape-16-12-2000x1500.txt", 2000, 1500),
    ("2250x1500-tablet", "landscape-18-12-2250x1500.txt", 2250, 1500),
]

# Assets copied from the NewMoon 2.0 package. LICENSE is mandatory — its terms
# require the notice to travel with any copy.
ASSETS = [
    "LICENSE",
    "noart.png",
    "transparent-500.png",
    "position-marker-50.png",
    "position-1000-50-black.png",
    "position-1000-50-dawn.png",
    "skipback-500.png",
    "skipnext-500.png",
    "play-500.png",
    "pause-500.png",
]

# Seekbar images that are OURS, not NewMoon's, and must win over the source
# package: a plain white played-bar and a fully transparent marker. NewMoon
# ships a rainbow "dawn" gradient and a visible dot — taking those by mistake
# is exactly how the timeline came out dotted and multicoloured.
LOCAL_ASSETS = [
    "position-marker-50.png",
    "position-1000-50-black.png",
    "position-1000-50-dawn.png",
    # Our "ALBUM ART MISSING" card. NewMoon's default art is TRANSPARENT, which
    # on a black background means a track with no cover shows nothing at all.
    "noart.png",
]
ROUNDED_ONLY = ["artwork-frame-950-950-black.png"]
ICON_GLOB = "Icon-*.png"

CODEC = (
    "[font-info]%codec% · %bitrate% kbps · %__bitspersample%-bit · "
    "$div(%samplerate%,1000).$div($mod(%samplerate%,1000),100) kHz"
)

# The release date, verbatim from the tag. Nothing parses it, which is the whole
# point: this used to be $year($if2(%year%,%date%)), and $year() only reads a
# LEADING four-digit year. Hand it a slash-formatted tag — 07/17/2020, which is
# how plenty of people date their libraries — and it reads "07/1", fails, and
# returns foobar's "0000" sentinel, which then went on screen as the release
# year of every such album.
#
# %date% comes first deliberately. If foobar derives %year% from the date with
# that same parser, %year% is *itself* "0000" for a slash-formatted tag, and
# $if2 would happily take it. Reading the raw tag first can't lose that way, and
# it also shows the full date rather than throwing the month and day away.
#
# The trailing empty argument is the other half of it. foobar prints an
# undefined field as "?", and $if2(%date%,%year%) leaves %year% sitting in the
# OUTPUT position — so an untagged track rendered a literal question mark. The
# fields are still evaluated as falsy correctly, so what's needed is an empty
# final branch for the output to land in. $if3 takes one, which is how NewMoon
# writes the same guard.
RELEASE = "[font-info]$if3(%date%,%year%,)"

# --------------------------------------------------------------- safe areas
# A format-2 canvas is the WHOLE screen, camera housing included — foobar does
# not inset it and does not expose the safe area to the skin, so clearance is
# ours to hard-code. Apple's published safe-area insets are the number to use:
# they already account for the Dynamic Island plus its breathing room, and they
# are per-device, whereas a skin canvas is shared by every device of that
# aspect ratio. So each clearance below is the WORST CASE across the phones
# that can land on an island-class canvas.
#
# One canvas unit is the short axis over 1125, so units = pt * 1125/short_pt,
# and the worst case is whichever phone maximises that. Working, from Apple's
# per-device insets:
#
#   portrait top      Air (420pt, T68)  68*1125/420 = 182  <- worst
#                     17 (402pt, T62)   62*1125/402 = 174
#                     13 (390pt, T59)   59*1125/390 = 170
#                     X  (375pt, T44)   44*1125/375 = 132
#   portrait bottom   X  (375pt, B34)   34*1125/375 = 102  <- worst
#                     17 (402pt, B34)   34*1125/402 =  95
#   landscape side    Air (420pt, L68)  68*1125/420 = 182  <- worst
#                     17 (402pt, L62)   62*1125/402 = 174
#   landscape top     17 (402pt, T20)   20*1125/402 =  56  <- worst
#   landscape bottom  Air (420pt, B29)  29*1125/420 =  78  <- worst
#
# Landscape gained top and bottom insets with the iPhone 17 — the 16 and
# earlier reported T:0 there — so a layout that only inset the sides was right
# for one generation and is not any more.
#
# Only tall canvases need any of this. The 9:16 and 9:18 ones are pre-notch
# phones, the notHSB ones already exclude the system chrome, and tablets have
# neither island nor home indicator — padding those would just waste screen.
ISLAND_ASPECT = 2.05
SAFE_TOP = 190          # portrait: below this the format line clears the island
SAFE_BOTTOM = 105       # portrait: home indicator
SAFE_SIDE = 190         # landscape: island, on whichever short edge you rotated to
SAFE_LAND_TOP = 60
SAFE_LAND_BOTTOM = 80

# Pre-notch phones keep the original margins exactly, so those canvases come out
# bit-identical to the layout that was confirmed on device.
PLAIN_TOP = 18          # the format line's original y
PLAIN_ART_GAP = 77      # format line (42) + 35 of air, down to the artwork


def n(value: float) -> str:
    """Coordinates: integers stay integral, halves keep their .5."""
    rounded = round(value * 2) / 2
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


# ---------------------------------------------------------------- portrait
def portrait(w: int, h: int, framed: bool, codec: bool) -> str:
    """Minimal, portrait.

    Sizes scale with WIDTH (art must stay square and fit), and the leftover
    height is split evenly into the two breathing gaps — above the title and
    above the seekbar. At 1125x2166 this reproduces the original format-1
    layout to within a pixel.

    The format line sits above the artwork, where it has always been — but on
    an island-class canvas the whole top block starts at SAFE_TOP instead of
    unit 18, which is what used to put it behind the camera housing. The
    artwork follows it down, so it stops losing its top edge too.
    """
    s = w / 1125
    island = h / w >= ISLAND_ASPECT
    top = (SAFE_TOP if island else PLAIN_TOP) * s
    # The transport's box already carries 23 units of air below the glyph.
    bottom = max(0, SAFE_BOTTOM - 23) * s if island else 0
    # 680 = every vertical band except the artwork, the two gaps and the margins
    # (603 below the artwork, plus the format line and its air above it).
    slack = h - 680 * s - top - bottom
    min_gap = 40 * s
    art = min(1040 * s, slack - 2 * min_gap)
    gap = (slack - art) / 2

    art_x, art_y = (w - art) / 2, top + PLAIN_ART_GAP * s
    col_x, col_w = 62.5 * s, 1000 * s
    meta_bottom = art_y + art + 114 * s     # below the album / release date
    title_y = meta_bottom + gap
    artist_y = title_y + 93 * s
    seek_y = artist_y + 60 * s + gap
    play_y = h - 198 * s - bottom

    L = [
        "//Background",
        "[rectangle]",
        "0,0,0",
        f"0,0,{n(w)},{n(h)}",
        "",
    ]
    if codec:
        L += [
            "//Format line (above the artwork, below the camera housing)",
            "*if playing",
            "[label]",
            f"{n(col_x)},{n(top)},{n(col_w)},{n(42 * s)}",
            "centered",
            CODEC,
            "",
            "*end",
            "",
        ]
    L += [
        "//Album artwork",
        "[albumart]",
        f"{n(art_x)},{n(art_y)},{n(art)},{n(art)}",
        "main",
        "",
    ]
    if framed:
        L += [
            "[image]",
            "artwork-frame-950-950-black.png",
            f"{n(art_x)},{n(art_y)},{n(art)},{n(art)}",
            "",
        ]
    L += [
        "*if playing",
        "",
        "//Album and release date",
        "[label]",
        f"{n(col_x)},{n(art_y + art + 20 * s)},{n(col_w)},{n(46 * s)}",
        "centered",
        "[i][album][-i]",
        "",
        "[label]",
        f"{n(col_x)},{n(art_y + art + 74 * s)},{n(col_w)},{n(40 * s)}",
        "centered",
        RELEASE,
        "",
        "//Title and artist",
        "[label]",
        f"{n(col_x)},{n(title_y)},{n(col_w)},{n(100 * s)}",
        "centered",
        "[b][title][-b]",
        "",
        "[label]",
        f"{n(col_x)},{n(artist_y)},{n(col_w)},{n(60 * s)}",
        "centered",
        "[font-artist][artist]",
        "",
        "*else",
        "",
        "[label]",
        f"{n(col_x)},{n(title_y)},{n(col_w)},{n(100 * s)}",
        "centered,noreducesize",
        "[font-info]Not Playing",
        "",
        "*end",
        "",
        "//Menu (over the title block)",
        "[button]",
        f"{n(art_x)},{n(title_y)},{n(art)},{n(160 * s)}",
        "menu",
        *(["transparent-500.png"] * 4),
        "",
        "//Seekbar — times inline at both ends",
        "[label]",
        f"{n(42.5 * s)},{n(seek_y + 4 * s)},{n(100 * s)},{n(42 * s)}",
        "left",
        "[font-info][currentposition]",
        "",
        "[position]",
        f"{n(147.5 * s)},{n(seek_y)},{n(830 * s)},{n(50 * s)}",
        "position-marker-50.png",
        "position-1000-50-black.png",
        "position-1000-50-dawn.png",
        "",
        "[label]",
        f"{n(982.5 * s)},{n(seek_y + 4 * s)},{n(100 * s)},{n(42 * s)}",
        "right",
        "[font-info][remaining]",
        "",
        "//Transport",
        "[button]",
        f"{n(250 * s)},{n(play_y + 25 * s)},{n(125 * s)},{n(125 * s)}",
        "skipback",
        *(["skipback-500.png"] * 4),
        "",
        "[button]",
        f"{n(475 * s)},{n(play_y)},{n(175 * s)},{n(175 * s)}",
        "playnpause",
        "play-500.png",
        "play-500.png",
        "pause-500.png",
        "pause-500.png",
        "",
        "[button]",
        f"{n(750 * s)},{n(play_y + 25 * s)},{n(125 * s)},{n(125 * s)}",
        "skipnext",
        *(["skipnext-500.png"] * 4),
        "",
    ]
    return "\n".join(L)


# --------------------------------------------------------------- landscape
def landscape(w: int, h: int, framed: bool, codec: bool) -> str:
    """Minimal, landscape: square cover on the left, info column on the right.

    The cover is height-driven, but it is ALSO capped by width: on a squarish
    tablet canvas (16:12) a full-height square would swallow the row and push
    the transport buttons off the right edge. 800*t is the narrowest the info
    column can be and still seat the seekbar and the three buttons.

    The metadata block is anchored to the COVER TOP, not the canvas top: when
    the width cap shrinks the cover on a squarish tablet the cover drops, and
    metadata pinned to the canvas would float above it.

    It starts FLUSH with the cover top (offset 0), not at the +42 the
    hand-built format-1 canvas used. Format 1's box positions are reproduced
    here to within 3 px, but format 2 seats the text lower inside the same
    box, so carrying +42 over left the block visibly below the cover on
    device. The line is meant to start level with the artwork; 57/62 below it
    are format 1's own inter-line steps.

    The cover is inset by at least the margin it has above and below rather
    than sitting flush at x=0 — the rounded-corner mask needs black to round
    *against*, and hard against the canvas edge the left corners just read
    square. The width cap has to allow for that inset too.

    Rotating an island-class phone moves the camera housing onto a short edge —
    WHICH edge depends on which way you turned it, so both sides get the inset.
    From the iPhone 17 on there is a top and bottom inset in landscape as well,
    so the vertical margin has a floor and the bottom row lifts.
    """
    t = h / 1290
    island = w / h >= ISLAND_ASPECT
    # The cover is centred, so its top and bottom margins are the same number and
    # that number has to clear the LARGER of the two insets. Costs ~6% of the
    # cover on an island phone, which is the price of the bottom edge not running
    # under the home indicator.
    mv = max(55 * t, max(SAFE_LAND_TOP, SAFE_LAND_BOTTOM) if island else 0)
    ml = SAFE_SIDE if island else 55 * t               # left of the cover
    mr = SAFE_SIDE if island else 48 * t               # right of the info column
    # The transport already sits (h - 1242*t) clear of the bottom on its own.
    lift = max(0, SAFE_LAND_BOTTOM - (h - 1242 * t)) if island else 0
    art = min(h - 2 * mv, w - 800 * t - ml)
    art_x = ml
    art_y = (h - art) / 2          # stays centred when width is the binding limit
    info_x = art_x + art + 56 * t
    info_r = w - mr
    info_w = info_r - info_x
    cx = info_x + info_w / 2
    # The cover top carries the metadata block; the format line takes the first
    # slot when it's on, and album/date shuffle down to make room for it.
    meta_y = art_y + (57 if codec else 0) * t

    L = [
        "//Background",
        "[rectangle]",
        "0,0,0",
        f"0,0,{n(w)},{n(h)}",
        "",
        "//Album artwork (square, inset left, vertically centred)",
        "[albumart]",
        f"{n(art_x)},{n(art_y)},{n(art)},{n(art)}",
        "main",
        "",
    ]
    if framed:
        L += [
            "[image]",
            "artwork-frame-950-950-black.png",
            f"{n(art_x)},{n(art_y)},{n(art)},{n(art)}",
            "",
        ]
    L += [
        "*if playing",
        "",
        "//Info column",
    ]
    if codec:
        L += [
            "[label]",
            f"{n(info_x)},{n(art_y)},{n(info_w)},{n(48 * t)}",
            "left",
            CODEC,
            "",
        ]
    L += [
        "[label]",
        f"{n(info_x)},{n(meta_y)},{n(info_w)},{n(53 * t)}",
        "left",
        "[i][album][-i]",
        "",
        "[label]",
        f"{n(info_x)},{n(meta_y + 62 * t)},{n(info_w)},{n(46 * t)}",
        "left",
        RELEASE,
        "",
        "[label]",
        f"{n(info_x)},{n(501 * t)},{n(info_w)},{n(115 * t)}",
        "centered",
        "[b][title][-b]",
        "",
        "[label]",
        f"{n(info_x)},{n(630 * t)},{n(info_w)},{n(69 * t)}",
        "centered",
        "[font-artist][artist]",
        "",
        "*else",
        "",
        "[label]",
        f"{n(info_x)},{n(501 * t)},{n(info_w)},{n(115 * t)}",
        "centered,noreducesize",
        "[font-info]Not Playing",
        "",
        "*end",
        "",
        "//Menu",
        "[button]",
        f"{n(info_x)},{n(501 * t)},{n(info_w)},{n(221 * t)}",
        "menu",
        *(["transparent-500.png"] * 4),
        "",
        "//Seekbar",
        "[label]",
        f"{n(info_x)},{n(942 * t - lift)},{n(115 * t)},{n(42 * t)}",
        "left",
        "[font-info][currentposition]",
        "",
        "[position]",
        f"{n(info_x + 120 * t)},{n(938 * t - lift)},{n(info_w - 240 * t)},{n(57 * t)}",
        "position-marker-50.png",
        "position-1000-50-black.png",
        "position-1000-50-dawn.png",
        "",
        "[label]",
        f"{n(info_r - 115 * t)},{n(942 * t - lift)},{n(115 * t)},{n(42 * t)}",
        "right",
        "[font-info][remaining]",
        "",
        "//Transport (centered under the info column)",
        "[button]",
        f"{n(cx - 300 * t)},{n(1070 * t - lift)},{n(143 * t)},{n(143 * t)}",
        "skipback",
        *(["skipback-500.png"] * 4),
        "",
        "[button]",
        f"{n(cx - 100 * t)},{n(1041 * t - lift)},{n(201 * t)},{n(201 * t)}",
        "playnpause",
        "play-500.png",
        "play-500.png",
        "pause-500.png",
        "pause-500.png",
        "",
        "[button]",
        f"{n(cx + 158 * t)},{n(1070 * t - lift)},{n(143 * t)},{n(143 * t)}",
        "skipnext",
        *(["skipnext-500.png"] * 4),
        "",
    ]
    return "\n".join(L)


# ----------------------------------------------------------------- skindef
def skindef(skin_name: str, icons: list[str]) -> str:
    L = [
        "//General Information",
        "skin-format: 2",
        f"name: {skin_name}",
        f"author: {AUTHOR}",
        f"version: {VERSION}",
        "",
        "//Images",
        "defaultart: noart.png",
        "iconplay: play-500.png",
        "iconpause: pause-500.png",
    ]
    for icon in sorted(icons):
        key = icon[len("Icon-"):-len("-250.png")].lower()
        L.append(f"iconfolder-{key}: {icon}")
        if key == "folder":
            L[-1] = f"iconfolder: {icon}"
    L += [
        "",
        "//Colors and Fonts",
        "backgroundcol: 0,0,0",
        "genericfont: 240,240,240",
        "artistfont: 175,175,175",
        "titlefont: 240,240,240;bold",
        "albumfont: 240,240,240",
        "font-default: 240,240,240",
        "font-artist: 175,175,175",
        "font-info: 130,130,130",
        "font-label: 240,240,240",
        "font-value: 175,175,175",
        "",
        "//Portrait",
    ]
    L += [f"skin: {key} {fn}" for key, fn, _, _ in PORTRAIT]
    L += ["", "//Landscape"]
    L += [f"skin: {key} {fn}" for key, fn, _, _ in LANDSCAPE]
    L.append("")
    return "\n".join(L)


def write_utf16(path: Path, text: str) -> None:
    """Format 2 reads UTF-16; writing UTF-8 yields a silently ignored file."""
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-16")


def build(source: Path, out_dir: Path, variant: str, codec: bool) -> Path:
    framed = variant == "r"
    # The suffix keeps the two builds apart in foobar's skin picker, and stops a
    # --no-codec run from silently overwriting the standard .fbskin.
    skin_name = f"Minimal-{variant}{'' if codec else '-plain'}{VERSION}"
    stage = out_dir / skin_name
    if stage.exists():
        shutil.rmtree(stage)
    (stage / skin_name).mkdir(parents=True)
    root = stage / skin_name

    local_dir = Path(__file__).resolve().parent / "assets"
    wanted = ASSETS + (ROUNDED_ONLY if framed else [])
    for name in wanted:
        # Our own seekbar art wins; everything else comes from NewMoon.
        src = local_dir / name if name in LOCAL_ASSETS else source / name
        if not src.exists():
            raise SystemExit(f"missing asset: {src}")
        shutil.copy2(src, root / name)
    icons = [p.name for p in source.glob(ICON_GLOB)]
    for icon in icons:
        shutil.copy2(source / icon, root / icon)

    for _, fn, w, h in PORTRAIT:
        write_utf16(root / fn, portrait(w, h, framed, codec))
    for _, fn, w, h in LANDSCAPE:
        write_utf16(root / fn, landscape(w, h, framed, codec))
    write_utf16(root / "skindef.txt", skindef(skin_name, icons))

    out = out_dir / f"{skin_name}.fbskin"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob("*")):
            z.write(path, path.relative_to(stage))
    shutil.rmtree(stage)
    return out


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(here / "NewMoon2.0_unpacked"),
                    help="unzipped NewMoon 2.0 package (asset + LICENSE source)")
    ap.add_argument("--out", default=str(here))
    ap.add_argument("--no-codec", dest="codec", action="store_false",
                    help="omit the codec/bitrate/bit-depth/kHz line, leaving "
                         "album, release date, title and artist")
    args = ap.parse_args()

    source, out_dir = Path(args.source), Path(args.out)
    if not source.exists():
        raise SystemExit(
            f"source package not found: {source}\n"
            "Unzip NewMoon 2.0.fbskin and point --source at the folder inside it."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    for variant in ("r", "s"):
        built = build(source, out_dir, variant, args.codec)
        print(f"packed {built.name} ({built.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
