#!/usr/bin/env bash
# One-time toolchain setup for the design report.
#
# Installs, without sudo:
#   * TinyTeX (user-level LaTeX)          -> ~/Library/TinyTeX
#   * the TeX packages the report needs    -> tlmgr
#   * mermaid-cli under Node 22            -> renders assets/diagrams/src/*.mmd
#
# Mermaid uses the Google Chrome already installed on this machine, so puppeteer
# never downloads its own Chromium (~300 MB).
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. bin/env.sh

TEXBIN="$HOME/Library/TinyTeX/bin/universal-darwin"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nGAGAL: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. TinyTeX
if [ -x "$TEXBIN/pdflatex" ]; then
  step "TinyTeX sudah terpasang di $HOME/Library/TinyTeX"
else
  step "Memasang TinyTeX (user-level, tanpa sudo)"
  curl -fsSL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
fi
export PATH="$TEXBIN:$PATH"
command -v pdflatex >/dev/null 2>&1 \
  || fail "pdflatex tidak ditemukan setelah instalasi. Pasang manual: https://yihui.org/tinytex/"

# ---------------------------------------------------------------- 2. packages
PACKAGES=(
  pgf circuitikz pgfplots
  babel-indonesian babel-english hyphen-indonesian
  booktabs tools multirow makecell amsmath graphics
  hyperref geometry xcolor tcolorbox environ trimspaces
  caption float enumitem listings fancyhdr titlesec
  microtype lm needspace adjustbox standalone
  pdflscape setspace tocloft parskip xstring etoolbox
  collection-fontsrecommended
)

step "Memeriksa paket LaTeX"
tlmgr install "${PACKAGES[@]}" || printf 'Peringatan: sebagian paket gagal dipasang (lihat pesan di atas)\n'

REQUIRED_STY=(tikz.sty circuitikz.sty pgfplots.sty booktabs.sty longtable.sty \
              babel.sty etoolbox.sty tcolorbox.sty adjustbox.sty standalone.cls \
              hyperref.sty caption.sty enumitem.sty)
MISSING=()
for sty in "${REQUIRED_STY[@]}"; do
  [ -n "$(kpsewhich "$sty" 2>/dev/null || true)" ] || MISSING+=("$sty")
done
if [ ${#MISSING[@]} -gt 0 ]; then
  fail "paket LaTeX belum lengkap: ${MISSING[*]}
Coba: $TEXBIN/tlmgr install <paket>   (mis. 'tikz' tidak ada — pakai 'pgf')"
fi
printf 'semua paket LaTeX wajib tersedia\n'

# ---------------------------------------------------------------- 3. mermaid
if [ ! -x "$CHROME" ]; then
  fail "Google Chrome tidak ditemukan di:
  $CHROME
Pasang Chrome, atau sunting assets/diagrams/puppeteer-config.json dan arahkan
executablePath ke browser Chromium lain."
fi

step "Memasang @mermaid-js/mermaid-cli (Node $(node -v 2>/dev/null || echo '?'))"
if command -v mmdc >/dev/null 2>&1; then
  printf 'mmdc sudah terpasang: %s\n' "$(command -v mmdc)"
else
  PUPPETEER_SKIP_DOWNLOAD=1 npm install -g @mermaid-js/mermaid-cli
fi
command -v mmdc >/dev/null 2>&1 \
  || fail "mmdc tidak ditemukan. Jalankan manual: npm install -g @mermaid-js/mermaid-cli"

# ---------------------------------------------------------------- 4. summary
step "Ringkasan"
printf 'pdflatex  %s\n' "$(pdflatex --version | head -1)"
printf 'latexmk   %s\n' "$(latexmk -v 2>/dev/null | head -1)"
printf 'mmdc      %s\n' "$(mmdc --version 2>/dev/null || echo installed)"
printf 'node      %s\n' "$(node -v)"
printf 'chrome    %s\n' "$CHROME"
printf '\nToolchain siap. Lanjut: bin/render-diagrams.sh\n'
