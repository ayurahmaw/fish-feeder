#!/usr/bin/env bash
# Build lengkap: diagram -> kedua mode PDF -> verifikasi fakta & tautan gambar.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. bin/env.sh

bin/render-diagrams.sh

echo
echo "LaTeX:"
for wrapper in main-standalone main-appendix; do
  printf '  %-20s' "$wrapper"
  latexmk -pdf -interaction=nonstopmode -halt-on-error "$wrapper.tex" >"/tmp/$wrapper.log" 2>&1 \
    || { printf 'GAGAL\n'; grep -nE '^!|^l\.[0-9]+' "/tmp/$wrapper.log" | head -20 | sed 's/^/    /'; exit 1; }
  printf 'ok\n'
done

mkdir -p out
cp main-standalone.pdf out/laporan-desain-sistem.pdf
cp main-appendix.pdf out/lampiran-desain-sistem.pdf

echo
bin/verify-facts.sh

echo
printf 'Selesai:\n'
for pair in "out/laporan-desain-sistem.pdf:main-standalone" "out/lampiran-desain-sistem.pdf:main-appendix"; do
  f="${pair%%:*}"
  stem="${pair##*:}"
  printf '  %-38s %s halaman / %s\n' "$f" \
    "$(grep -oE '\([0-9]+ pages?' "$stem.log" | tail -1 | grep -oE '[0-9]+')" \
    "$(du -h "$f" | cut -f1)"
done
