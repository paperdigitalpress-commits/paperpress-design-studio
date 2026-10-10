#!/usr/bin/env python3
"""Report what actually arrived for an input file (reference, attachment, logo).

Used to check that an attachment reached the container at its original quality:
compare the printed SHA-256, byte size and pixel/page dimensions with the values
of the original file on the sender's side.

Usage: python3 -I tools/inspect_file.py FILE [FILE ...]
"""
import hashlib
import os
import sys

MM_PER_PT = 25.4 / 72


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def box_mm(rect):
    return f"{rect.width * MM_PER_PT:.2f} x {rect.height * MM_PER_PT:.2f} mm"


def inspect_pdf(path):
    import pymupdf

    doc = pymupdf.open(path)
    print(f"  pages: {doc.page_count}")
    for i, page in enumerate(doc):
        print(f"  page {i + 1}: media {box_mm(page.mediabox)}, trim {box_mm(page.trimbox)}, "
              f"bleed {box_mm(page.bleedbox)}")
        fonts = page.get_fonts(full=True)
        for f in fonts:
            embedded = f[1] not in ("n/a", "")
            print(f"    font: {f[3]} ({'embedded' if embedded else 'NOT embedded'})")
        for img in page.get_images(full=True):
            xref, w, h, cs = img[0], img[2], img[3], img[5]
            rects = page.get_image_rects(xref)
            if rects:
                r = rects[0]
                ppi = min(w / (r.width / 72), h / (r.height / 72))
                print(f"    image xref {xref}: {w}x{h}px, {cs}, effective {ppi:.0f} ppi")
            else:
                print(f"    image xref {xref}: {w}x{h}px, {cs}")


def inspect_image(path):
    from PIL import Image

    with Image.open(path) as im:
        print(f"  format: {im.format}, mode: {im.mode}, pixels: {im.width}x{im.height}")
        dpi = im.info.get("dpi")
        if dpi and dpi[0]:
            print(f"  dpi tag: {dpi[0]:.0f} -> {im.width / dpi[0] * 25.4:.1f} x "
                  f"{im.height / dpi[1] * 25.4:.1f} mm at that dpi")
        else:
            print("  dpi tag: none (physical size unknown)")
        print(f"  embedded ICC profile: {'yes' if im.info.get('icc_profile') else 'no'}")
        print(f"  size at 300 ppi: {im.width / 300 * 25.4:.1f} x {im.height / 300 * 25.4:.1f} mm")


def main(paths):
    if not paths:
        print(__doc__)
        return 2
    for path in paths:
        print(path)
        print(f"  bytes: {os.path.getsize(path)}")
        print(f"  sha256: {sha256(path)}")
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in (".pdf", ".ai"):
                inspect_pdf(path)
            elif ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"):
                inspect_image(path)
            else:
                print("  (no format-specific checks for this type)")
        except Exception as e:  # report and continue with the next file
            print(f"  could not inspect: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
