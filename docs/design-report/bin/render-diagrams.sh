#!/usr/bin/env bash
# Render semua sumber diagram menjadi aset siap-pakai:
#   assets/diagrams/src/*.mmd  -> assets/diagrams/svg/*.svg + assets/diagrams/pdf/*.pdf
#   assets/tikz/*.tex          -> assets/tikz/build/*.pdf
#
# SVG dipakai untuk copy-paste ke Word/Slides/GitHub; PDF dipakai LaTeX.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. bin/env.sh

MERMAID_CFG="assets/diagrams/mermaid-config.json"
PUPPETEER_CFG="assets/diagrams/puppeteer-config.json"

mkdir -p assets/diagrams/svg assets/diagrams/pdf assets/diagrams/png assets/tikz/build

command -v mmdc >/dev/null 2>&1 || { echo "mmdc tidak ada — jalankan bin/bootstrap-tools.sh" >&2; exit 1; }
command -v pdflatex >/dev/null 2>&1 || { echo "pdflatex tidak ada — jalankan bin/bootstrap-tools.sh" >&2; exit 1; }

mmdc_() {
  mmdc -q -c "$MERMAID_CFG" -p "$PUPPETEER_CFG" -b white "$@"
}

render_mermaid() {
  local src="$1"
  local base
  base="$(basename "$src" .mmd)"
  local svg="assets/diagrams/svg/$base.svg"
  local pdf="assets/diagrams/pdf/$base.pdf"
  local png="assets/diagrams/png/$base.png"

  printf '  mermaid  %-34s' "$base"

  if ! mmdc_ -i "$src" -o "$svg" 2>/tmp/mmdc.err; then
    printf 'GAGAL(svg)\n'
    sed -n '1,12p' /tmp/mmdc.err | sed 's/^/           /'
    return 1
  fi

  if ! mmdc_ -i "$src" -o "$pdf" 2>/tmp/mmdc.err; then
    printf 'pdf->png '
    if ! mmdc_ -i "$src" -o "$png" -w 2400 2>>/tmp/mmdc.err; then
      printf 'GAGAL(png)\n'
      sed -n '1,12p' /tmp/mmdc.err | sed 's/^/           /'
      return 1
    fi
    sips -s format pdf "$png" --out "$pdf" >/dev/null
  fi

  printf 'ok  %8s\n' "$(wc -c <"$pdf" | tr -d ' ')B"
}

render_tikz() {
  local src="$1"
  local base
  base="$(basename "$src" .tex)"
  local out="assets/tikz/build/$base.pdf"

  printf '  tikz     %-34s' "$base"
  rm -f "$out"
  if ! latexmk -pdf -interaction=nonstopmode -halt-on-error \
        -outdir=assets/tikz/build "$src" >"/tmp/tikz-$base.log" 2>&1; then
    printf 'GAGAL\n'
    grep -nE '^!|^l\.[0-9]+' "/tmp/tikz-$base.log" | head -12 | sed 's/^/           /'
    return 1
  fi
  printf 'ok  %8s\n' "$(wc -c <"$out" | tr -d ' ')B"
}

status=0

echo "Mermaid:"
shopt -s nullglob
for src in assets/diagrams/src/*.mmd; do
  render_mermaid "$src" || status=1
done

echo
echo "TikZ:"
for src in assets/tikz/*.tex; do
  render_tikz "$src" || status=1
done

echo
if [ "$status" -ne 0 ]; then
  echo "Ada diagram yang gagal. Perbaiki sumbernya lalu ulangi." >&2
  exit 1
fi
echo "Semua diagram berhasil dirender."
