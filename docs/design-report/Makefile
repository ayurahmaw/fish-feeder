# Build dokumen desain sistem.
#
#   make tools     pasang TinyTeX + mermaid-cli (sekali saja)
#   make           render diagram, build dua PDF, verifikasi
#   make diagrams  render diagram saja
#   make clean     hapus artefak build

SHELL := /bin/bash
.PHONY: all tools diagrams build verify clean pdf

all: diagrams pdf verify

tools:
	bin/bootstrap-tools.sh

diagrams:
	bin/render-diagrams.sh

pdf: diagrams
	latexmk -pdf -interaction=nonstopmode -halt-on-error main-standalone.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error main-appendix.tex
	mkdir -p out
	cp main-standalone.pdf out/laporan-desain-sistem.pdf
	cp main-appendix.pdf out/lampiran-desain-sistem.pdf

build:
	bin/build.sh

verify:
	bin/verify-facts.sh

clean:
	latexmk -C main-standalone.tex main-appendix.tex >/dev/null 2>&1 || true
	find . -maxdepth 2 \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
		-o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.synctex.gz' \) | xargs -r rm -f
