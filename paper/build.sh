#!/usr/bin/env bash
# Build the OJ-IES manuscript end-to-end.
#
# Auto-detects the available TeX engine:
#   1. tectonic (preferred: single binary, fetches packages on demand,
#                runs bibtex + reruns automatically).
#   2. pdflatex + bibtex (classic TeX Live workflow).
#
# Usage: ./build.sh [--clean]
set -euo pipefail

MAIN=oj_ies_manuscript
cd "$(dirname "$0")"

if [[ "${1:-}" == "--clean" ]]; then
  rm -f "${MAIN}".{aux,bbl,blg,log,out,toc,lof,lot,fls,fdb_latexmk,synctex.gz}
  rm -rf build/
  echo "[build.sh] cleaned auxiliary files and build/."
  shift || true
fi

if command -v tectonic >/dev/null 2>&1; then
  mkdir -p build
  echo "[build.sh] Using tectonic ($(tectonic --version | tr -d '\n')) ..."
  tectonic --keep-logs --outdir build "${MAIN}.tex"
  echo "[build.sh] Done. Output: build/${MAIN}.pdf"
  exit 0
fi

if command -v pdflatex >/dev/null 2>&1 && command -v bibtex >/dev/null 2>&1; then
  echo "[build.sh] Using pdflatex + bibtex ..."
  pdflatex -interaction=nonstopmode "${MAIN}.tex"
  bibtex   "${MAIN}"
  pdflatex -interaction=nonstopmode "${MAIN}.tex"
  pdflatex -interaction=nonstopmode "${MAIN}.tex"
  echo "[build.sh] Done. Output: ${MAIN}.pdf"
  exit 0
fi

echo "[build.sh] ERROR: no TeX engine found." >&2
echo "Install one of:" >&2
echo "  - tectonic   (recommended): https://tectonic-typesetting.github.io/install.html" >&2
echo "  - texlive    (apt install texlive-latex-extra texlive-bibtex-extra texlive-science)" >&2
exit 1
