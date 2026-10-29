# Stochastic Labs v2 — 3D-print version (Onshape)

A print-tuned version of the v2 primary logo, for **debossing** (recessing) into 3D-printed parts with a **0.2 mm nozzle** at about **20–40 mm wide**.

![preview](preview.png)

## Files

| File | Use |
|---|---|
| `stochastic-labs-v2-print.dxf` | Import into an Onshape sketch. Units: mm. Drawn 30 mm wide. |
| `stochastic-labs-v2-print.svg` | The same outlines as an SVG, for checking or for other tools |
| `preview.png` | Picture of the outlines |
| `build_print.py` | Regenerates the files from the fonts (see below) |

Every closed outline in the DXF is one pocket. The text and strokes are already converted to filled shapes, so there is nothing to clean up after import.

## Changes from the screen logo

- Removed the dashed line at the mean and the dot at the peak.
- **8 bars instead of 12**, each 0.46 mm wide with 0.44 mm gaps at 30 mm, so the walls between pockets don't break. The bars now join the baseline, making one pocket.
- The curve is lifted so there is at least a 0.4 mm wall between it and the bars and baseline. It is 0.36 mm wide.
- **LABS** is about twice its screen size, in JetBrains Mono Bold, with tighter letter spacing. The rule next to it is 0.32 mm thick.
- "Stochastic" has slightly looser letter spacing so the walls between letters stay printable.
- The curve still follows a normal distribution with mean 10.5 and standard deviation 2.96.

## Importing into Onshape

1. Create a sketch on the face where the logo goes.
2. Click **Insert DXF or DWG**, set **Units: Millimeter** *before* choosing the file, then pick `stochastic-labs-v2-print.dxf`.
3. To resize, add one dimension (for example the overall width). Onshape scales the whole sketch to match.
4. Extrude with **Remove**: select all the logo regions (letters, bars, curve and rule) and cut about 0.4–0.6 mm deep.

## Print notes (0.2 mm nozzle)

- **Mark:** at 30 mm wide, the narrowest pocket is 0.36 mm and the narrowest wall is 0.40 mm. It should print cleanly down to about 25 mm.
- **Text:** at 30 mm wide, the letter strokes are about 0.26–0.4 mm. The narrowest walls are 0.2–0.3 mm, at the openings inside a, s and S and the gap under the i's dot. These print as single lines and may soften. Text looks best at **35–40 mm** wide.
- The tiny point at the top of the A's counter will fill in at any of these sizes. That's expected and the letter still reads as an A.
- Use a slicer with variable-width walls (Arachne in PrusaSlicer, OrcaSlicer or Bambu Studio; Cura 5+) so thin walls aren't dropped.
- Debossing on an **upward-facing top surface** gives the sharpest result. On a vertical wall, sharpness depends on layer height, so use 0.08–0.12 mm layers.
- Smaller than about 25 mm: use the mark without the text.

## Regenerating

You need Python 3 with `numpy` and `fonttools` (plus `matplotlib`, `scikit-image`, `scipy` and `Pillow` for `--check`), and the two font files, both free on Google Fonts: `SpaceGrotesk-Bold.ttf` and `JetBrainsMono-Bold.ttf`.

```
FONT_DIR=path/to/fonts python3 build_print.py OUTPUT_DIR          # writes the DXF and SVG
FONT_DIR=path/to/fonts python3 build_print.py OUTPUT_DIR --check  # also writes check.png marking thin spots
```

Sizes, bar count, wall and groove widths are parameters at the top of the script.
