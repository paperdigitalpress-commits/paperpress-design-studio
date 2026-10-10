#!/bin/bash
# Installs the PaperPress toolchain inside the Claude Code cloud container only.
# Idempotent: skips anything already present. Never runs on the user's machine.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  echo "setup.sh: not a Claude Code cloud session; nothing installed." >&2
  exit 0
fi

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo -n"

APT_PKGS=(ghostscript inkscape qpdf potrace poppler-utils librsvg2-bin imagemagick
          tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng fonts-noto-core fonts-noto-extra)
missing=()
for p in "${APT_PKGS[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
done
if [ ${#missing[@]} -gt 0 ]; then
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "${missing[@]}" >/dev/null
fi

PY_PKGS=(pymupdf pikepdf scikit-image opencv-python-headless cairosvg reportlab numpy pillow)
if ! python3 -c "import pymupdf, pikepdf, skimage, cv2, cairosvg, reportlab, numpy, PIL" 2>/dev/null; then
  pip install -q --break-system-packages "${PY_PKGS[@]}"
fi

echo "setup.sh: toolchain ready."
