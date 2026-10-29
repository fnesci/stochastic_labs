"""Usage: FONT_DIR=path/to/ttfs python3 build_print.py OUTPUT_DIR [--check]

Build the print-tuned Stochastic Labs v2 primary logo as DXF (mm), plus a preview PNG and a thin-feature check.

Geometry is in mm, y up. Every closed loop is a pocket (a recess on the part) except glyph holes,
which follow the font's winding. Loops are lists of (x, y, bulge) for DXF POLYLINE vertices.
"""
import math, sys, json
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

import os
FONTS = os.environ.get("FONT_DIR", "fonts")
GROTESK = os.path.join(FONTS, "SpaceGrotesk-Bold.ttf")
MONO = os.path.join(FONTS, "JetBrainsMono-ExtraBold.ttf")

P = dict(
    target_width=30.0,   # final overall width in mm
    L=11.0,              # baseline length (mark width) before final scaling
    tb=0.36,             # baseline groove thickness
    n_bars=8, bar_w=0.46, bar_gap=0.44, bar_r=0.1,
    Hb=4.6,              # bar height scale (height at the mean)
    curve_w=0.36,        # curve groove width
    wall=0.40,           # min wall between curve and bars/baseline
    mu=10.5, sigma=2.96, d0=2.0, d1=19.0,  # data range mapped onto the curve span
    curve_inset=0.25,    # curve ends inset from baseline ends
    gap_mark_text=1.5,
    word="STOCHASTIC", pairs={"TI": 0.06},
    stoch_size=2.8107, stoch_track=0.035,   # em; size keeps the word as wide as mixed-case "Stochastic" at 3.15
    labs_size=2.4, labs_track=0.14,      # em
    line_gap=0.75,       # gap between Stochastic baseline and LABS cap top (mm)
    rule_t=0.32, rule_gap=0.55,
)

def gauss(x, s):
    return math.exp(-x * x / (2 * s * s))

# ---------------------------------------------------------------- shapes
def rounded_rect_open_bottom(x0, x1, ytop, r):
    """Top edge of a bar with rounded top corners, left->right, as (x,y,bulge) points (going up the left side,
    across the top, down the right). Bulge for 90deg arc = tan(pi/8)."""
    b = math.tan(math.pi / 8)
    # CW traversal along the top when the comb outline is traced clockwise
    return [(x0, ytop - r, -b), (x0 + r, ytop, 0), (x1 - r, ytop, -b), (x1, ytop - r, 0)]

def build_mark(p):
    L, tb = p["L"], p["tb"]
    k = (L - 2 * p["curve_inset"]) / (p["d1"] - p["d0"])  # mm per data unit
    cx = L / 2
    sig = p["sigma"] * k
    n, w, g = p["n_bars"], p["bar_w"], p["bar_gap"]
    pitch = w + g
    centers = [cx + (i - (n - 1) / 2) * pitch for i in range(n)]
    heights = []
    for c in centers:
        edge = abs(c - cx) + w / 2
        heights.append(p["Hb"] * gauss(edge, sig))
    # comb: baseline (y 0..tb) with bars rising from tb. Trace clockwise starting bottom-left.
    r_end = tb / 2
    pts = []
    pts.append((r_end, 0, 0))
    pts.append((L - r_end, 0, 1.0))           # semicircle right end (bulge 1 = 180deg, CCW)
    pts.append((L - r_end, tb, 0))
    # go right->left along the top edge, adding bars
    top = []
    for c, h in sorted(zip(centers, heights), reverse=True):
        x0, x1 = c - w / 2, c + w / 2
        top += [(x1, tb, 0)]
        r = min(p["bar_r"], w / 2 - 1e-3)
        b = math.tan(math.pi / 8)
        top += [(x1, tb + h - r, b), (x1 - r, tb + h, 0), (x0 + r, tb + h, b), (x0, tb + h - r, 0), (x0, tb, 0)]
    pts += top
    pts.append((r_end, tb, 1.0))              # semicircle left end
    comb = pts  # traversal is CCW overall (bottom L->R, top R->L)

    # bar rectangles (for clearance checks)
    bars = [(c - w / 2, c + w / 2, tb, tb + h) for c, h in zip(centers, heights)]

    # curve centerline y(x) = tb + D + Hc * g(x)
    half = p["curve_w"] / 2
    need = half + p["wall"]
    xs = np.linspace(p["curve_inset"], L - p["curve_inset"], 600)

    def clearance(D, Hc):
        ys = tb + D + Hc * np.exp(-(xs - cx) ** 2 / (2 * sig * sig))
        dmin = 1e9
        for (x0, x1, y0, y1) in bars + [(-1, L + 1, -1, tb)]:
            dx = np.maximum(np.maximum(x0 - xs, 0), xs - x1)
            dy = np.maximum(np.maximum(y0 - ys, 0), ys - y1)
            dmin = min(dmin, float(np.min(np.hypot(dx, dy))))
        return dmin
    Hc = p["Hb"] * 1.0
    D = need
    while clearance(D, Hc) < need:
        D += 0.005
    ys = tb + D + Hc * np.exp(-(xs - cx) ** 2 / (2 * sig * sig))
    # offset outline
    dy = np.gradient(ys, xs)
    nx, ny = -dy / np.hypot(1, dy), 1 / np.hypot(1, dy)
    upper = list(zip(xs + nx * half, ys + ny * half))
    lower = list(zip(xs - nx * half, ys - ny * half))
    # CCW: lower left->right, round cap, upper right->left, round cap
    curve = [(x, y, 0) for x, y in lower]
    curve[-1] = (curve[-1][0], curve[-1][1], 1.0)
    curve += [(x, y, 0) for x, y in upper[::-1]]
    curve[-1] = (curve[-1][0], curve[-1][1], 1.0)
    info = dict(D=D, bar_heights=heights, sigma_mm=sig, mm_per_unit=k,
                peak=float(ys.max() + half))
    return [comb, curve], info

class LoopPen(BasePen):
    def __init__(self, gs, scale, dx, dy, steps=10):
        super().__init__(gs); self.loops = []; self.cur = None
        self.s, self.dx, self.dy, self.steps = scale, dx, dy, steps
    def _t(self, pt): return (pt[0] * self.s + self.dx, pt[1] * self.s + self.dy)
    def _moveTo(self, pt): self.cur = [self._t(pt)]; self.last = pt
    def _lineTo(self, pt): self.cur.append(self._t(pt)); self.last = pt
    def _qCurveToOne(self, p1, p2):
        p0 = self.last
        for i in range(1, self.steps + 1):
            t = i / self.steps
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
            self.cur.append(self._t((x, y)))
        self.last = p2
    def _curveToOne(self, p1, p2, p3):
        p0 = self.last
        for i in range(1, self.steps + 1):
            t = i / self.steps; u = 1 - t
            x = u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0]
            y = u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]
            self.cur.append(self._t((x, y)))
        self.last = p3
    def _closePath(self):
        c = self.cur
        if len(c) > 1 and math.dist(c[0], c[-1]) < 1e-9: c = c[:-1]
        self.loops.append([(x, y, 0) for x, y in c]); self.cur = None
    _endPath = _closePath

def text_loops(font_path, text, size, track_em, x, y, pairs=None):
    """pairs: extra spacing in em for specific letter pairs, e.g. {"TI": 0.06}."""
    f = TTFont(font_path); gs = f.getGlyphSet(); cm = f.getBestCmap(); upm = f["head"].unitsPerEm
    s = size / upm; loops = []; cx = x; pairs = pairs or {}
    for i, ch in enumerate(text):
        gn = cm[ord(ch)]
        pen = LoopPen(gs, s, cx, y); gs[gn].draw(pen); loops += pen.loops
        adv = f["hmtx"][gn][0] * s
        if i < len(text) - 1:
            cx += adv + (track_em + pairs.get(text[i:i + 2], 0)) * size
    # tight right edge
    xmax = max(px for l in loops for px, _, _ in l)
    return loops, xmax

def build(p):
    mark, info = build_mark(p)
    mark_top = info["peak"]
    tx = p["L"] + p["gap_mark_text"]
    cap_g = 0.700 * p["stoch_size"]; cap_m = 0.730 * p["labs_size"]
    block_h = cap_g + p["line_gap"] + cap_m
    y_labs = (mark_top - block_h) / 2          # LABS baseline, block centered on the mark
    y_stoch = y_labs + cap_m + p["line_gap"]
    stoch, sx1 = text_loops(GROTESK, p.get("word","Stochastic"), p["stoch_size"], p["stoch_track"], tx - 0.070 * p["stoch_size"], y_stoch, p.get("pairs"))
    labs, lx1 = text_loops(MONO, "LABS", p["labs_size"], p["labs_track"], tx - 0.095 * p["labs_size"], y_labs)
    r0 = lx1 + p["rule_gap"]; rt = p["rule_t"]; ry = y_labs + cap_m / 2 - rt / 2
    rule = [(r0 + rt / 2, ry, 0), (sx1 - rt / 2, ry, 1.0), (sx1 - rt / 2, ry + rt, 0), (r0 + rt / 2, ry + rt, 1.0)]
    loops = mark + stoch + labs + [rule]
    # normalise: origin at bottom-left of bounding box, scale to target width
    allpts = np.array([pt for l in loops for pt in flatten(l, 24)])
    x0, y0 = allpts.min(0); x1, y1 = allpts.max(0)
    sc = p["target_width"] / (x1 - x0)
    loops = [[((x - x0) * sc, (y - y0) * sc, b) for x, y, b in l] for l in loops]
    info.update(scale=sc, width=p["target_width"], height=(y1 - y0) * sc)
    return loops, info

# ---------------------------------------------------------------- output
def flatten(loop, seg=12):
    out = []
    n = len(loop)
    for i in range(n):
        x0, y0, b = loop[i]; x1, y1, _ = loop[(i + 1) % n]
        out.append((x0, y0))
        if abs(b) > 1e-9:
            th = 4 * math.atan(b); c = math.dist((x0, y0), (x1, y1))
            r = c / (2 * math.sin(th / 2))
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            ux, uy = (x1 - x0) / c, (y1 - y0) / c
            d = (c / 2) / math.tan(th / 2)
            ccx, ccy = mx - uy * d, my + ux * d
            a0 = math.atan2(y0 - ccy, x0 - ccx)
            for j in range(1, seg):
                a = a0 + th * j / seg
                out.append((ccx + abs(r) * math.cos(a), ccy + abs(r) * math.sin(a)))
    return out

def write_dxf(loops, path):
    L = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4",
         "9", "$MEASUREMENT", "70", "1", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for loop in loops:
        L += ["0", "POLYLINE", "8", "LOGO", "66", "1", "10", "0.0", "20", "0.0", "30", "0.0", "70", "1"]
        for x, y, b in loop:
            L += ["0", "VERTEX", "8", "LOGO", "10", f"{x:.5f}", "20", f"{y:.5f}", "30", "0.0"]
            if abs(b) > 1e-9: L += ["42", f"{b:.8f}"]
        L += ["0", "SEQEND", "8", "LOGO"]
    L += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(L) + "\n")

def write_svg(loops, info, path):
    W, H = info["width"], info["height"]
    d = " ".join("M" + " L".join(f"{x:.4f} {H - y:.4f}" for x, y in flatten(l)) + "Z" for l in loops)
    open(path, "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.4f} {H:.4f}" width="{W:.3f}mm" height="{H:.3f}mm">'
        f'<path d="{d}" fill="#111111" fill-rule="nonzero"/></svg>\n')

def raster(loops, info, px_per_mm):
    import matplotlib; matplotlib.use("Agg")
    from matplotlib.path import Path
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    W, H = info["width"], info["height"]; pad = 0.5
    verts, codes = [], []
    for l in loops:
        f = flatten(l)
        verts += f + [f[0]]; codes += [Path.MOVETO] + [Path.LINETO] * (len(f) - 1) + [Path.CLOSEPOLY]
    fig = plt.figure(figsize=((W + 2 * pad) * px_per_mm / 100, (H + 2 * pad) * px_per_mm / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-pad, W + pad); ax.set_ylim(-pad, H + pad); ax.axis("off")
    ax.add_patch(PathPatch(Path(verts, codes), fc="black", ec="none", antialiased=False))
    fig.canvas.draw(); img = np.asarray(fig.canvas.buffer_rgba())[:, :, 0] < 128
    plt.close(fig); return img

def thin_check(loops, info, groove_min, wall_min, out_png, px_per_mm=200):
    from skimage.morphology import medial_axis
    from PIL import Image
    m = raster(loops, info, px_per_mm)
    report = {}
    canvas = np.where(m[..., None], np.array([40, 40, 40], np.uint8), np.array([245, 242, 234], np.uint8)).copy()
    for name, mask, lim, col in [("groove", m, groove_min, (255, 60, 30)), ("wall", ~m, wall_min, (30, 110, 255))]:
        sk, dist = medial_axis(mask, return_distance=True)
        width = 2 * dist / px_per_mm
        if name == "wall":  # only consider walls inside the logo's bounding area
            pad = int(0.5 * px_per_mm) + 2
            sk[:pad, :] = sk[-pad:, :] = False; sk[:, :pad] = sk[:, -pad:] = False
        vals = width[sk]
        # ignore skeleton spurs running into sharp corners: keep points whose width is below the limit
        thin = sk & (width < lim)
        # spur points near corners have tiny widths but cluster within ~lim of an edge end; count area of thin clusters
        report[name] = dict(min_mm=float(vals.min()), p1_mm=float(np.percentile(vals, 1)), p5_mm=float(np.percentile(vals, 5)),
                            thin_px=int(thin.sum()), total_px=int(sk.sum()))
        from scipy.ndimage import binary_dilation
        canvas[binary_dilation(thin, iterations=2)] = col
    Image.fromarray(canvas).save(out_png)
    return report

if __name__ == "__main__":
    out = sys.argv[1]
    loops, info = build(P)
    write_dxf(loops, f"{out}/stochastic-labs-v2-print.dxf")
    write_svg(loops, info, f"{out}/stochastic-labs-v2-print.svg")
    if "--check" not in sys.argv: sys.exit(0)
    rep = thin_check(loops, info, 0.30, 0.35, f"{out}/check.png")
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items() if k != "bar_heights"}, indent=0))
    print("bar heights", [round(h * info["scale"], 2) for h in info["bar_heights"]])
    print(json.dumps(rep, indent=0))
