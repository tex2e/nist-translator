"""Make the site icon: a document (a sheet with a folded corner) with an N.

    python scripts/make_favicon.py

Writes static/favicon.svg, static/favicon.ico (16, 32, 48 px) and
static/apple-touch-icon.png (180 px). The N is drawn from simple shapes, not text,
so it looks the same without any particular font. It is a plain serif N, not the
lettering of the NIST logo.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BLUE, PALE, WHITE = "#0b6e99", "#cff4fc", "#ffffff"

# all coordinates in a 32 x 32 grid
PAGE = (3, 1.5, 27, 30.5)          # left, top, right, bottom; bottom corners rounded
PAGE_RADIUS = 2
FOLD = [(20, 1.5), (20, 6.5), (22, 8.5), (27, 8.5)]      # the folded corner
CUT = [(20, 1.5), (27, 1.5), (27, 8.5)]                  # removed from the page
N_SHAPES = [
    [(8.4, 11.6), (12.6, 11.6), (21.6, 25.4), (17.4, 25.4)],   # thick diagonal
    [(8.7, 11.6), (10.5, 11.6), (10.5, 25.4), (8.7, 25.4)],    # left stem
    [(19.8, 11.6), (21.6, 11.6), (21.6, 25.4), (19.8, 25.4)],  # right stem
    [(6.6, 11.6), (12.6, 11.6), (12.6, 12.9), (6.6, 12.9)],    # serifs
    [(6.6, 24.1), (12.6, 24.1), (12.6, 25.4), (6.6, 25.4)],
    [(17.8, 11.6), (23.6, 11.6), (23.6, 12.9), (17.8, 12.9)],
]


def svg():
    left, top, right, bottom = PAGE
    r = PAGE_RADIUS
    page = ("M%g %gH20L%g 8.5V%gA%g %g 0 0 1 %g %gH%gA%g %g 0 0 1 %g %gV%gA%g %g 0 0 1 %g %gZ"
            % (left + r, top, right, bottom - r, r, r, right - r, bottom, left + r, r, r, left, bottom - r,
               top + r, r, r, left + r, top))
    fold = "M" + "L".join("%g %g" % point for point in FOLD) + "Z"
    letter = "".join("M" + "L".join("%g %g" % point for point in shape) + "Z" for shape in N_SHAPES)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            '<path d="%s" fill="%s"/><path d="%s" fill="%s"/><path d="%s" fill="%s"/></svg>\n'
            % (page, BLUE, fold, PALE, letter, WHITE))


def raster(size, background=None, padding=0.0):
    """Draw at 16x and scale down, so small sizes stay smooth."""
    scale = 16
    big = size * scale
    image = Image.new("RGBA", (big, big), background or (0, 0, 0, 0))
    inner = big * (1 - 2 * padding)
    offset = big * padding
    unit = inner / 32
    at = lambda points: [(offset + x * unit, offset + y * unit) for x, y in points]
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = PAGE
    draw.rounded_rectangle([offset + left * unit, offset + top * unit, offset + right * unit, offset + bottom * unit],
                           radius=PAGE_RADIUS * unit, fill=BLUE)
    draw.polygon(at(CUT), fill=background or (0, 0, 0, 0))
    draw.polygon(at(FOLD), fill=PALE)
    for shape in N_SHAPES:
        draw.polygon(at(shape), fill=WHITE)
    return image.resize((size, size), Image.LANCZOS)


def main():
    static = ROOT / "static"
    (static / "favicon.svg").write_text(svg(), encoding="utf-8")
    raster(48).save(static / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # iOS shows the touch icon on a rounded tile: give it a white background and some margin
    raster(180, background=WHITE, padding=0.1).convert("RGB").save(static / "apple-touch-icon.png")
    print("Wrote favicon.svg, favicon.ico, apple-touch-icon.png")


if __name__ == "__main__":
    main()
