#!/usr/bin/env python3
"""Phase 1 toolchain checks. Uses only generated dummy content, never client files.

Run: python3 -I tests/test_toolchain.py
Outputs go to tests/out/ (git-ignored) for visual review.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
MM = 72 / 25.4
TRIM_W, TRIM_H = 90, 190      # example trim size from the plan
BLEED_PER_EDGE = 1            # 2 mm total per dimension
AR_TEXT = "مكونات طبيعية"

results = []


def check(name):
    def wrap(fn):
        def run():
            try:
                detail = fn()
                results.append((True, name, detail or ""))
            except Exception as e:
                results.append((False, name, f"{type(e).__name__}: {e}"))
        run.__name__ = fn.__name__
        TESTS.append(run)
        return fn
    return wrap


TESTS = []


def sh(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def out(name):
    return os.path.join(OUT, name)


@check("CLI tools present")
def t_tools():
    tools = ["gs", "inkscape", "qpdf", "potrace", "tesseract", "pdftoppm", "rsvg-convert", "compare"]
    missing = [t for t in tools if shutil.which(t) is None]
    assert not missing, f"missing: {missing}"
    langs = sh("tesseract", "--list-langs")
    assert "ara" in langs and "eng" in langs, "tesseract ara/eng missing"
    return ", ".join(tools)


@check("Bleed geometry: 90x190 trim -> 92x192 media, TrimBox/BleedBox set")
def t_bleed():
    import pikepdf
    import pymupdf
    from reportlab.pdfgen import canvas

    w, h = (TRIM_W + 2 * BLEED_PER_EDGE) * MM, (TRIM_H + 2 * BLEED_PER_EDGE) * MM
    path = out("bleed.pdf")
    c = canvas.Canvas(path, pagesize=(w, h))
    c.setFillColorCMYK(0, 0, 0, 1)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0].obj
        b = BLEED_PER_EDGE * MM
        page.TrimBox = pikepdf.Array([b, b, w - b, h - b])
        page.BleedBox = pikepdf.Array([0, 0, w, h])
        pdf.save(path)
    page = pymupdf.open(path)[0]
    media = (round(page.mediabox.width / MM, 2), round(page.mediabox.height / MM, 2))
    trim = (round(page.trimbox.width / MM, 2), round(page.trimbox.height / MM, 2))
    assert media == (92, 192), media
    assert trim == (90, 190), trim
    sh("qpdf", "--check", path)
    return f"media {media} mm, trim {trim} mm, qpdf OK"


@check("DeviceCMYK K100 stays K-only (no rich black from RGB)")
def t_cmyk():
    cov = sh("gs", "-q", "-o", "-", "-sDEVICE=inkcov", out("bleed.pdf")).split()
    c, m, y, k = map(float, cov[:4])
    assert c == m == y == 0 and k > 0.99, cov[:4]
    return f"C{c:.0%} M{m:.0%} Y{y:.0%} K{k:.0%}"


@check("Arabic text: SVG -> outlined PDF keeps correct shaping (OCR round-trip)")
def t_arabic():
    svg = out("arabic.svg")
    with open(svg, "w", encoding="utf-8") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="700" height="160">'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<text x="350" y="110" font-family="Noto Naskh Arabic" font-size="70" '
                f'text-anchor="middle">{AR_TEXT}</text></svg>')
    pdf = out("arabic.pdf")
    sh("inkscape", svg, "--export-text-to-path", "--export-type=pdf", f"--export-filename={pdf}")
    import pymupdf
    assert not pymupdf.open(pdf)[0].get_fonts(), "text was not converted to outlines"
    sh("pdftoppm", "-r", "150", "-png", "-singlefile", pdf, out("arabic"))
    text = sh("tesseract", out("arabic.png"), "-", "-l", "ara").strip()
    assert text == AR_TEXT, f"OCR read {text!r}"
    return f"outlined, OCR = {text}"


@check("SVG mm size -> PDF exact size (Inkscape)")
def t_svg_size():
    import pymupdf
    svg = out("size.svg")
    with open(svg, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{TRIM_W}mm" height="{TRIM_H}mm" '
                f'viewBox="0 0 {TRIM_W} {TRIM_H}"><rect width="{TRIM_W}" height="{TRIM_H}" fill="#000"/></svg>')
    pdf = out("size.pdf")
    sh("inkscape", svg, "--export-type=pdf", f"--export-filename={pdf}")
    r = pymupdf.open(pdf)[0].rect
    size = (round(r.width / MM, 2), round(r.height / MM, 2))
    assert size == (TRIM_W, TRIM_H), size
    return f"{size} mm"


@check("Client preview: PNG, longest side 2000 px")
def t_preview():
    import pymupdf
    from PIL import Image
    page = pymupdf.open(out("bleed.pdf"))[0]
    zoom = 2000 / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    path = out("example_PREVIEW_NOT_FOR_PRINT.png")
    pix.save(path)
    with Image.open(path) as im:
        assert max(im.size) == 2000, im.size
        return f"{im.size[0]}x{im.size[1]} px"


@check("Comparison: SSIM + diff map detect a small change")
def t_compare():
    import cv2
    import numpy as np
    from skimage.metrics import structural_similarity

    ref = np.full((600, 300), 255, np.uint8)
    cv2.putText(ref, "LABEL 250g", (20, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    same = ref.copy()
    changed = ref.copy()
    cv2.putText(changed, "LABEL 260g", (20, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    s_same = structural_similarity(ref, same)
    s_changed, diff = structural_similarity(ref, changed, full=True)
    cv2.imwrite(out("diff_map.png"), ((1 - diff) * 255).clip(0, 255).astype(np.uint8))
    assert s_same == 1.0
    changed_px = int((ref != changed).sum())
    assert changed_px > 0
    # A one-digit change can still score high: SSIM is a review signal, not approval.
    return f"identical SSIM={s_same:.4f}; one digit changed SSIM={s_changed:.4f}, {changed_px} px differ"


@check("Potrace vectorizes a bitmap shape")
def t_potrace():
    pbm = out("shape.pbm")
    sh("convert", "-size", "200x200", "xc:white", "-fill", "black", "-draw", "circle 100,100 100,30", pbm)
    sh("potrace", "-s", "-o", out("shape.svg"), pbm)
    assert "<path" in open(out("shape.svg")).read()
    return "SVG path produced"


def main():
    os.makedirs(OUT, exist_ok=True)
    for t in TESTS:
        t()
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    failed = sum(1 for ok, *_ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
