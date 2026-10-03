"""Generates the Discord Rich Presence art assets from the Nuke logo files."""
from PIL import Image, ImageDraw
import sys

SRC = sys.argv[1]            # logo mark (transparent png)
WORD = sys.argv[2] if len(sys.argv) > 2 else None
OUT = "assets/"
BG, ORANGE = (28, 28, 32, 255), (251, 178, 54, 255)
S, SS = 1024, 4              # output size, supersample


def finish(im, name, size=S):
    im.resize((size, size), Image.LANCZOS).save(OUT + name)


# --- nuke.png: logo on dark, full bleed (Discord rounds/crops it itself)
logo = Image.open(SRC).convert("RGBA")
bb = logo.getbbox(); logo = logo.crop(bb)
m = int(S * 0.74)
logo = logo.resize((m, int(m * logo.height / logo.width)), Image.LANCZOS)
nuke = Image.new("RGBA", (S, S), BG)
nuke.alpha_composite(logo, ((S - logo.width) // 2, (S - logo.height) // 2))
nuke.save(OUT + "nuke.png")


# --- small state icons: orange-ringed dark disc + glyph
def badge():
    N = S * SS
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, N - 1, N - 1], fill=ORANGE)
    r = int(N * 0.05)
    d.ellipse([r, r, N - 1 - r, N - 1 - r], fill=BG)
    return im, d, N


# editing: pencil
im, d, N = badge()
pen = Image.new("RGBA", (N, N), (0, 0, 0, 0)); p = ImageDraw.Draw(pen)
cx, w = N // 2, int(N * 0.10)
top, tip0, tip = int(N * .25), int(N * .62), int(N * .75)
p.rounded_rectangle([cx - w, top, cx + w, top + int(N * .09)], int(N * .03), fill=(251, 178, 54, 255))   # eraser
p.rectangle([cx - w, top + int(N * .11), cx + w, tip0], fill=ORANGE)                                        # body
p.polygon([(cx - w, tip0 + int(N*.015)), (cx + w, tip0 + int(N*.015)), (cx, tip)], fill=ORANGE)             # tip
p.line([(cx, top + int(N*.14)), (cx, tip0 - int(N*.03))], fill=BG, width=int(N * .018))                     # body groove
pen = pen.rotate(-45, resample=Image.BICUBIC, center=(N // 2, N // 2))
im.alpha_composite(pen); finish(im, "editing.png")

# rendering: play triangle inside a progress ring
im, d, N = badge()
c, R = N // 2, int(N * .34)
d.arc([c - R, c - R, c + R, c + R], -90, 200, fill=ORANGE, width=int(N * .045))
d.arc([c - R, c - R, c + R, c + R], 200, 270, fill=(251, 178, 54, 70), width=int(N * .045))
t = int(N * .15)
d.polygon([(c - t * .7, c - t * 1.1), (c - t * .7, c + t * 1.1), (c + t * 1.2, c)], fill=ORANGE)
finish(im, "rendering.png")

# idle: crescent moon + small star
im, d, N = badge()
c, R = N // 2, int(N * .27)
moon = Image.new("L", (N, N), 0); md = ImageDraw.Draw(moon)
md.ellipse([c - R, c - R, c + R, c + R], fill=255)
off = int(R * .55)
md.ellipse([c - R + off + int(N*.04), c - R - off//2, c + R + off + int(N*.04), c + R - off//2], fill=0)
im.paste(ORANGE, (0, 0), moon)
d = ImageDraw.Draw(im)
sx, sy, sr = int(N * .66), int(N * .32), int(N * .035)
d.polygon([(sx, sy - sr*2), (sx + sr*.6, sy - sr*.6), (sx + sr*2, sy), (sx + sr*.6, sy + sr*.6),
           (sx, sy + sr*2), (sx - sr*.6, sy + sr*.6), (sx - sr*2, sy), (sx - sr*.6, sy - sr*.6)], fill=ORANGE)
finish(im, "idle.png")

# --- optional invite cover (1024x576): wordmark on dark
if WORD:
    w = Image.open(WORD).convert("RGBA"); w = w.crop(w.getbbox())
    cv = Image.new("RGBA", (1024, 576), BG)
    k = 760 / w.width; w = w.resize((760, int(w.height * k)), Image.LANCZOS)
    cv.alpha_composite(w, ((1024 - w.width) // 2, (576 - w.height) // 2))
    cv.save(OUT + "cover.png")
