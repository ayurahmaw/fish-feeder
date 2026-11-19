# BUILD NOTES — dokumen desain sistem

Catatan teknis untuk membangun ulang PDF. Bukan bagian dari dokumen yang diserahkan.

## Ringkas

```
make tools      # sekali saja: pasang TinyTeX + mermaid-cli
make            # render diagram → build 2 PDF → verifikasi
```

Hasil:

| Berkas | Mode | Keterangan |
|---|---|---|
| `out/laporan-desain-sistem.pdf` | mandiri | cover, daftar isi, bab 1–9, penomoran arabik |
| `out/lampiran-desain-sistem.pdf` | lampiran | tanpa cover/TOC, penomoran A/B/C dan A.1/A.2 |

Kedua PDF dibangun dari sumber yang sama (`report-body.tex` + `chapters/*.tex`);
perbedaannya hanya di wrapper (`main-standalone.tex` / `main-appendix.tex`).

## Toolchain

Mesin ini **tidak** punya LaTeX maupun Graphviz/mermaid-cli sebelumnya. Yang dipasang:

| Alat | Versi terpasang | Lokasi |
|---|---|---|
| TinyTeX (pdfTeX engine) | TeX Live 2026, pdfTeX 1.40.29 | `~/Library/TinyTeX` (user-level, **tanpa sudo**) |
| latexmk | 4.89 | ikut TinyTeX |
| Node | v22.23.2 (nvm) | `~/.nvm/versions/node/v22.23.2` |
| @mermaid-js/mermaid-cli | 12.2.0 | global npm Node 22 |
| Google Chrome | terpasang di sistem | dipakai puppeteer, **tanpa** unduh Chromium |

Paket TeX yang dipasang oleh `bin/bootstrap-tools.sh`:

```
pgf circuitikz pgfplots babel-indonesian babel-english hyphen-indonesian
booktabs tools multirow makecell amsmath graphics hyperref geometry xcolor
tcolorbox environ trimspaces caption float enumitem listings fancyhdr
titlesec microtype lm needspace adjustbox standalone pdflscape setspace
tocloft parskip xstring etoolbox collection-fontsrecommended
```

`hyphen-indonesian` wajib: tanpa itu babel memperingatkan "no hyphenation patterns for
Bahasa Indonesia" dan pemenggalan kata menjadi salah.

## Kenapa hybrid (Mermaid + TikZ)

| Kebutuhan | Pilihan | Alasan |
|---|---|---|
| flowchart, sequence, state, ER | Mermaid | paling cepat diubah; bisa di-preview di GitHub/mermaid.live |
| schematic, pinout, block diagram, timing | TikZ / Circuitikz | presisi posisi, vektor murni, tidak ada artefak render browser |
| urutan langkah `loop()` firmware | **TikZ** (`fw-loop-order.tex`) | Mermaid `TD` selalu menarik rantai lurus menjadi kolom sempit (≈1:3), sehingga di A4 teksnya mengecil di bawah 7 pt; TikZ memberi rasio 16×10 cm dengan teks 9–10 pt |

Catatan penting soal `fw-loop-order`: diagram itu sengaja **tidak** memakai fan-out. Setiap
langkah tersambung sebagai rantai, panah kembali digambar di sisi kiri, dan ada keterangan
"satu thread". Versi Mermaid sebelumnya menggambar tujuh tick sebagai kotak sejajar dengan
satu panah balik, yang terbaca sebagai proses paralel — padahal firmware hanya punya satu
super-loop.

Aset dirender **dua kali**: SVG (untuk di-copy-paste ke Word/PowerPoint/Docs/GitHub) dan
PDF (dipakai `\includegraphics`). Sumbernya `.mmd` / `.tex`, jadi semuanya tetap editable.

## Struktur aset

```
assets/diagrams/src/*.mmd   sumber Mermaid        (di-commit)
assets/diagrams/svg/*.svg   hasil render          (di-commit, copy-paste-able)
assets/diagrams/pdf/*.pdf   hasil render          (di-commit, dipakai LaTeX)
assets/tikz/*.tex           sumber TikZ           (di-commit)
assets/tikz/build/*.pdf     hasil compile         (gitignored, dibuat oleh build)
```

Kalau ingin mengubah gambar: sunting berkas sumber lalu `make diagrams`.
Jangan mengedit SVG/PDF hasil render — akan tertimpa.

## Fallback bila render gagal

`bin/render-diagrams.sh` mencoba berurutan untuk tiap `.mmd`:

1. `mmdc -o .pdf` (vektor, paling bagus)
2. `mmdc -o .png -w 2400` lalu `sips -s format pdf` (raster 300 dpi, tetap aman untuk cetak)
3. Bila keduanya gagal → skrip berhenti dengan pesan galat dan nomor baris sumbernya.

Bila Chrome berpindah lokasi, sunting `assets/diagrams/puppeteer-config.json`
(`executablePath`).

## Verifikasi

`bin/verify-facts.sh` memeriksa:

1. Makro di `preamble/facts.tex` sama persis dengan `#define` di
   `firmware/esp32_feeder/config.h` (pin, timing, kalibrasi, buffer, prefix).
2. Tidak ada sisa angka kalibrasi lama `5.00` / `25.00` / `5/25` di sumber dokumen.
3. Setiap `\mmdfig{...}` / `\tikzfig{...}` punya berkas hasil render.
4. Setiap `.mmd` diawali header `%% title:`.

Skrip ini dipanggil otomatis di akhir `bin/build.sh`, jadi build gagal bila dokumen
menyimpang dari kode.

## Perbaikan kalibrasi (2026-11-19)

Firmware memakai `HOPPER_FULL_CM 3.0` / `HOPPER_EMPTY_CM 17.0`, sedangkan schema dan seed
sebelumnya memakai 5.00 / 25.00 — pada jarak 10 cm keduanya menghasilkan 50 % vs 75 %.
Sudah diselaraskan ke 3.0 / 17.0 di schema, seed, dokumentasi, dan lewat migrasi
`_migrate_hopper_calibration()` di `dashboard/db.py` (hanya menyentuh baris yang masih
persis di nilai default lama).

## Keterbatasan yang diketahui

- PDF dibangun dengan pdfLaTeX + `lmodern`; tidak memakai font sistem.
- Diagram Mermaid dirender oleh Chromium lewat Chrome, jadi hasilnya raster-dalam-vektor
  untuk teks yang memakai `htmlLabels`. Untuk kebutuhan cetak tajam, sumbernya tetap
  tersedia sebagai PDF vektor penuh.
- Nomor halaman pada dua mode berbeda karena lampiran tidak punya cover/TOC.
