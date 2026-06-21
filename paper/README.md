# IEEE Open Journal of the Industrial Electronics Society manuscript

Self-contained LaTeX submission package for the manuscript

> *Resilient OFDMA Scheduling under Reactive Jamming for Industrial
> IEEE 802.11ax Networks: An ns-3 Scheduler-Harness Study with
> Estimator-Impairment and Component Ablation*

targeted at the **IEEE Open Journal of the Industrial Electronics
Society (OJ-IES)**.

This folder is intentionally decoupled from the rest of the repository
so it can be zipped up and submitted directly through the IEEE Author
Portal (ScholarOne).

## Contents

| File / folder | Purpose |
|---|---|
| `oj_ies_manuscript.tex` | Main LaTeX source (uses `IEEEtran.cls`, `journal` option). |
| `oj_ies.bib` | BibTeX entries; mirrored from the repository-root `paper.bib`. |
| `figs/` | Camera-ready figures (PNG + PDF, produced by `regen_figures.py`). |
| `regen_figures.py` | Matplotlib generator with Paul Tol colorblind-safe palette, distinct linestyles per policy, and frame-on legends. Reads `../results/paper_v2/results.csv` and writes ten figures as PNG (300 dpi) + PDF (vector). |
| `build.sh` | Convenience build helper (pdflatex -> bibtex -> pdflatex x2). |
| `REVIEW_WEAKNESSES.md` | Self-review with reviewer-impact triage; updated as items are addressed. |

The numerical content of Table 10 (estimator sensitivity) and Table 11
(component ablation) was lifted verbatim from
`docs/paper_tables/tab10_sensitivity.md` and
`docs/paper_tables/tab11_ablation.md`. No values were rounded, smoothed
or otherwise post-processed: the project `AGENTS.md` policy forbids it.

## Build

The manuscript uses the standard IEEE template:

```bash
cd paper
MPLCONFIGDIR=/tmp/mplconfig python3 regen_figures.py   # optional
./build.sh
# or, equivalently:
pdflatex oj_ies_manuscript
bibtex   oj_ies_manuscript
pdflatex oj_ies_manuscript
pdflatex oj_ies_manuscript
```

Requirements:

- A reasonably recent TeX Live distribution (`pdflatex`, `bibtex`,
  `IEEEtran.cls`, `algorithm`, `algpseudocode`, `booktabs`,
  `siunitx`, `hyperref`, `multirow`, `cite`, `amsmath`).
- For `regen_figures.py`: Python 3.10+, `numpy`, `pandas`,
  `matplotlib` (already used elsewhere in the project).
- The figures under `figs/` (already committed; regenerate only
  when the CSVs change).

Output: `oj_ies_manuscript.pdf`, ~12 pages including references.

## Authorship and submission notes

- Authors:
  - Lorenzo Fanari (EUNEIZ University, Vitoria-Gasteiz, Spain) -- corresponding.
  - Matteo Anedda (DIEE, University of Cagliari, Italy).
- Open-access OJ-IES: the manuscript is formatted for the single-column
  `journal` layout that IEEE Author Portal expects.
- If the editor requests the IEEE Computer Society two-column variant,
  swap the `\documentclass[journal,onecolumn,11pt,a4paper]{IEEEtran}`
  line for the default two-column `\documentclass[journal]{IEEEtran}`
  and re-run `./build.sh`. The figure widths use `\columnwidth`, which
  automatically tracks the active layout.

## Cross-references to the released artefacts

- Reproducibility statement (Section IX) of the manuscript references
  the campaign configuration files and aggregator scripts in the
  repository root.
- All raw CSV/JSON archives live under `../results/paper_v2/`,
  `../results/s9_estimator_sensitivity/` and
  `../results/s9_ablation/`.
- The Yans-Wi-Fi-PHY validation envelope cited in Section VIII is
  reproducible from `../scripts/run_cross_validation.py` and is
  archived at `../results/paper_v2/cross_validation/`.
- The seed-independence audit cited in Section IX is reproducible from
  `../scripts/check_seed_independence.py` and is archived at
  `../results/paper_v2/SEED_AUDIT.md`.

## QuaDRiGa-trace caveat

The QuaDRiGa rows discussed in Section VI rely on a documented
synthetic placeholder trace; the simulator gate
`--requireMeasuredTrace=true` refuses to start a QuaDRiGa run whose
provenance is anything other than `measured`. The camera-ready
pipeline must replace the placeholder before publication and re-run
the affected figures.
