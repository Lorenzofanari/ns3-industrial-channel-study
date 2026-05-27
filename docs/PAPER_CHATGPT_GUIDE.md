# Paper revision via ChatGPT — operator guide

This document is a **practical workflow** for applying the simulator-side
work in this repository to the manuscript

> *"Resilient OFDMA Scheduling under Reactive Jamming in Industrial IEEE
> 802.11ax-like Networks: An ns-3 Scheduler-Harness Study"* — [Fan26]

using ChatGPT (any reasoning-capable model: GPT-4o, GPT-5, o1, o3, Claude
Sonnet/Opus equivalently). The simulator already produces the data the paper
needs to fill the two placeholder tables and to clean up the duplicated
prose. This guide is the bridge between the **machine** (this repo) and the
**editorial assistant** (ChatGPT).

Read the companion document `PAPER_IMPROVEMENTS.md` first — it lists every
single issue to fix, indexed A1…A10, B1…B6, C1…C9, D1…D4. The prompts below
reference those IDs verbatim.

---

## 0. Files to attach to the ChatGPT session

Before opening ChatGPT, gather these files. Drag them into the prompt window
(or paste their content if your client has no upload feature).

| File | Why ChatGPT needs it |
|---|---|
| The current PDF or `.tex` source of the paper | Subject under edit |
| `PAPER_IMPROVEMENTS.md` (repo root) | Editorial backlog with priorities |
| `docs/paper_tables/tab10_sensitivity.md` | Camera-ready Table 10 data |
| `docs/paper_tables/tab11_ablation.md` | Camera-ready Table 11 data |
| `BIBLIOGRAPHY.md` (repo root) | Code↔citation mapping |
| `paper.bib` (repo root) | Clean BibTeX entries to import |
| `README.md` (repo root) | Reproducibility statement updates |

If the ChatGPT context window is tight, the **minimum viable set** is the
`.tex` source, `PAPER_IMPROVEMENTS.md`, and the two markdown tables.

---

## 1. The one-shot prompt (use if you trust the model)

Paste this **after** uploading the files above. It instructs the model to
walk the whole `PAPER_IMPROVEMENTS.md` checklist and produce a unified diff /
edited `.tex` in a single pass.

```
You are a senior copy editor for IEEE / Elsevier conference papers in the
wireless networking area. I am submitting a paper titled "Resilient OFDMA
Scheduling under Reactive Jamming in Industrial IEEE 802.11ax-like Networks:
An ns-3 Scheduler-Harness Study". The current draft has the following
known issues and improvement opportunities, all documented in the file
`PAPER_IMPROVEMENTS.md`.

Apply EVERY item with priority A (defect fixes A1-A10) and priority B
(substantive improvements B1-B6). For each priority-A item, produce the
EXACT replacement text. For each priority-B item:
  - For B1 / B2, use the numbers from `docs/paper_tables/tab10_sensitivity.md`
    and `docs/paper_tables/tab11_ablation.md` exactly (do not invent or
    round). Promote the two future-work paragraphs into results paragraphs.
  - For B3, draft the LaTeX figure environments referencing
    `figs/fig9_estimator_sensitivity.pdf` and `figs/fig10_ablation.pdf`
    (the plots themselves will be generated separately) -- give me the
    \begin{figure} blocks with captions, labels, and \ref calls to be
    inserted in §6.7 / §6.8.
  - For B4, replace the current Algorithm 1 listing with the four-switch
    version from PAPER_IMPROVEMENTS.md §B4 verbatim.
  - For B5, insert the listed CSV column inventory into the Data and
    Reproducibility Statement.
  - For B6, insert the footnote at the first mention of S8 / S9.

For each priority-C item (C1-C9), apply the listed surgical edit. For
priority-D, ignore for this revision -- they are out of scope.

Also enforce these global constraints:
  1. Do NOT change the scientific claims, the S9 mechanism, the 76-symbol
     cooldown, or the numerical headline results from §6.1-§6.6.
  2. Do NOT introduce new acronyms.
  3. Keep all section, equation, figure, and table numbers stable. New
     additions must extend the existing numbering.
  4. Keep the policy labels consistent: the paper-facing names are
     "Baseline-PF" (S4), "RTX-Assist" (S8), "Realloc" (S9). The CSV-side
     legacy labels (PLS-RTX, PLS-Realloc) appear only in the footnote
     from B6.
  5. American English; no contractions; passive voice acceptable for
     methods, active voice for results; preserve existing math notation.

Output:
  (a) A unified diff against the current `.tex` source, organised
      section-by-section.
  (b) A short cover note (max 200 words) summarising the edits.
  (c) A bullet list of any remaining manual actions I need to take that
      are outside the scope of a text edit (e.g. compiling figures,
      regenerating the bibliography).
```

If you do not have the `.tex` source, replace point (a) with:
*"For each section that changes, provide the FULL revised section text
delimited by `<SECTION N.M>` … `</SECTION N.M>` so I can swap it in by
hand."*

Expect 2–4 messages of output. After the model finishes, **always** run
the verification checklist in §3 below.

---

## 2. Surgical prompts (use if you want fine control)

The one-shot prompt above is convenient but, in practice, IEEE-quality
revisions are easier to review one issue at a time. The prompts below
correspond 1:1 to the items in `PAPER_IMPROVEMENTS.md`.

### 2.1 Priority A — defect fixes (the duplications)

```
The current draft has copy-paste duplications. For each item below, find
the duplicated passage in the .tex source and rewrite it as the single
authoritative variant indicated.

A1: §4.3 title. Current text contains the string
    "S9/Realloc: AP-Side Instantaneous-SNIR-Driven ReallocationS9/Realloc:
     AP-Side Estimated-SNIR-Driven Reallocation".
    Replace with EXACTLY:
    "S9/Realloc: AP-Side Estimated-SNIR-Driven Reallocation".

A2: §4.3 body. The paragraph that begins "At each scheduler step, the AP
    evaluates..." appears twice (one "instantaneous", one "estimated").
    Keep only the "estimated" variant. Eq. (3) also appears twice; keep
    the variant that uses \hat\gamma_{u,r}(t) and \hat J_r(t).

A3: §4.3, just below Eq. (4). Same duplication on Eq. (4). Keep the
    variant using \hat\gamma_{u,r}(t) and \hat J_r(t).

A4: §4.4 final paragraph. The Italian draft note about future estimator
    noise / bias / quantisation appears followed by a near-duplicate. Keep
    only the variant that names the "ideal observability profile" and
    introduces the moderate/conservative profiles.

A5: §6.7 above Table 10. Delete the Italian comment "Questa tabella 10 va
    inserita solo se abbiamo realmente generato i risultati." and fill
    Table 10 with the numbers from docs/paper_tables/tab10_sensitivity.md.

A6: §6.8 Table 11. Fill with docs/paper_tables/tab11_ablation.md.

A7: §8 Limitations, paragraph about observability. Drop the Italian comment
    "ma se invece aggiungessimo veramnete la sensitivity/ablation..." and
    keep the candidate replacement paragraph immediately below.

A8: §9 Conclusion. Drop the Italian draft note "con sensitivity e ablation
    invece potremmo dire:..." and keep the candidate "Future work should
    extend the estimator-impaired and ablation results..." sentence.

A9: §6.1 first paragraph and §6.10. The constant-jammer-saturation
    sentence appears in both. Keep both occurrences but rewrite the §6.10
    one to say "as anticipated in §3.4".

A10: §2.3 contributions list. Bullet 2 and bullet 3 both start "we compare
     three transparent ... policies". Merge into one bullet; keep the
     longer text that limits claims to resilience / reliability metrics.

Output: one unified diff plus a 5-line summary of what each fix did.
```

### 2.2 Priority B1 — promote §6.7 and fill Table 10

```
Currently §6.7 of the paper hosts an empty Table 10 with the caption
"Estimator-impairment sensitivity at MCS 3" and an Italian draft note above
it. Replace the empty table with the Table 10 from the simulator output
(file: docs/paper_tables/tab10_sensitivity.md, "Reactive jamming" section).

  - Use a three-column-group LaTeX table with MCS as the row group and
    Profile as the inner row, columns: PDR, PLR/PER, PDR jammer-ON,
    p95 delay [ms], proactive defer events.
  - Cite the data source as "this work, ns-3 core-harness, 100k packets/row,
    3 seeds, 3 payloads, 2 distances, CM8 reactive jammer at 10 dBm, 20 dB
    target SNR".
  - Insert immediately after the table the narrative paragraph from
    PAPER_IMPROVEMENTS.md §B1 ("Key narrative arc..."). Keep the
    monotonicity argument intact: ideal -> moderate -> conservative
    increases the proactive-defer count monotonically while PDR at MCS 0/1
    stays at 1.0000.
  - Also extend §6.7 with a one-sentence pointer to the clean-baseline
    sub-table (docs/paper_tables/tab10_sensitivity.md "Clean baseline"
    section), which should appear as Table 10b in the appendix.

Output: the revised §6.7 LaTeX, the LaTeX for Table 10 (and 10b), and a
diff-style summary of what changed.
```

### 2.3 Priority B2 — promote §6.8 and fill Table 11

```
Same task as 2.2 above, applied to §6.8. The source is
docs/paper_tables/tab11_ablation.md. Use four columns: Variant (full,
no_jammer_flag, no_cooldown, snir_only), PDR, PDR jammer-ON, p95 delay,
Jain. Insert the narrative paragraph from PAPER_IMPROVEMENTS.md §B2.

KEY FINDING (do not lose this): removing the cooldown collapses MCS 3
reactive PDR from 0.9869 to 0.7522 and jammer-ON PDR from 0.9802 to 0.6739.
This is the single most important number in §6.8 -- bold it in the table
and call it out in the narrative.

Also include the second key finding: full and no_jammer_flag are
bit-identical to four decimal digits because the SNIR margin is already
tripped whenever the reactive jammer is active. This justifies keeping the
jammer-flag check in the recommendation (low cost, useful as belt-and-
braces) without inflating its empirical importance.
```

### 2.4 Priority B3 — figure environments for Fig. 9 and Fig. 10

```
Draft the LaTeX figure environments for Fig. 9 (estimator sensitivity)
and Fig. 10 (component ablation). The plots themselves will be generated
later by `scripts/plot_results.py` and saved as
figs/fig9_estimator_sensitivity.pdf and figs/fig10_ablation.pdf.

Each figure should be a 1-row-3-column subplot (one column per MCS in
{0, 1, 3}), with the estimator profile / ablation variant on the x-axis
and PDR on the y-axis. Add a twin y-axis for jammer-ON PDR (dashed bars)
and a third subplot row for p95 delay if vertical space allows; otherwise
fold p95 delay into Table 10 / Table 11 as a separate column.

Output: the two \begin{figure*}...\end{figure*} blocks with captions,
labels, \cite calls (cite this work and the relevant CSV archive folders),
and \ref pointers from §6.7 / §6.8.
```

### 2.5 Priority B4 — Algorithm 1 with ablation switches

```
Replace the current Algorithm 1 listing in §4.3 with the four-switch
version below (from PAPER_IMPROVEMENTS.md §B4). Reformat it as an IEEE
"algorithmic" environment with proper \STATE, \IF, \FOR markers. Keep the
mathematical notation aligned with §4.3 (\hat\gamma_{u,r}(t),
\hat J_r(t), \mathrm{PER_{crit}}, \gamma_{\mathrm{out}}, 76-symbol
cooldown c_u).

[paste the listing from PAPER_IMPROVEMENTS.md §B4]
```

### 2.6 Priority B5 / B6 — Reproducibility Statement and policy-label footnote

```
In §9 (Data and Reproducibility Statement), add the paragraph from
PAPER_IMPROVEMENTS.md §B5 that lists the new CSV columns by exact name.
The first column to mention is `s9_estimator_profile`; the last group is
the four `s9_ablation_disable_*` flags.

At the first mention of S8 / S9 in the body of the paper (§2.3 or §4.1
depending on the draft), insert the footnote from PAPER_IMPROVEMENTS.md
§B6 explaining the legacy `PLS-` prefix in the CSV archive and pointing
at the `policy_paper_label` column.
```

### 2.7 Priority C — polishing

```
Apply the following surgical edits. For each item, locate the exact phrase
in the .tex source and rewrite as instructed.

[paste the C1-C9 table from PAPER_IMPROVEMENTS.md]

Output: one diff per priority-C item.
```

---

## 3. Verification checklist (must run after ChatGPT)

After ChatGPT delivers the revised text, walk this list manually. Do **not**
trust the model to enforce numerical fidelity.

1. **Tab. 10 fidelity.** Open the new Table 10 in the .tex and compare
   value-by-value against `docs/paper_tables/tab10_sensitivity.md`. Look
   particularly for swapped digits in the MCS=3 row.
2. **Tab. 11 fidelity.** Same for Table 11. The `no_cooldown`
   MCS-3-reactive PDR must read **0.7522** and the jammer-ON PDR **0.6739**.
3. **Algorithm 1 ablation switches.** Confirm the new Algorithm 1 lists
   the four boolean switches `use_snir_margin`, `use_per_margin`,
   `use_jammer_flag`, `use_cooldown` and that they map 1:1 to the CSV
   columns `s9_ablation_disable_*`.
4. **Policy labels.** Search the .tex for `PLS-RTX` and `PLS-Realloc`.
   The only legal occurrences are inside the new footnote that defines
   the legacy archive prefix. Every other mention must use `RTX-Assist`
   or `Realloc`.
5. **No Italian text.** Search for any non-ASCII character above 0x7F that
   is not a known mathematical symbol or accented author name in the
   bibliography. Italian draft notes contain "perchè", "veramnete",
   "tabella", etc. -- grep for them.
6. **Equation references.** After deleting the duplicated Eq. (3) and
   Eq. (4), make sure no \ref{eq:...} in §4 or §6 points to a deleted
   label.
7. **`paper.bib` imports.** If you applied C9, run
   `bibtex` (or `biber`) once and confirm there are no "undefined
   citation" warnings for `[Lop19], [Den20], [Aij20], [Ban18], [Bel19],
   [Tut21], [Mag21], [Mon24], [Ang22], [Fan26]`.
8. **CSV column names.** The Data and Reproducibility Statement now lists
   ~12 new column names. Confirm they all appear verbatim in the live
   CSV by running:
   ```bash
   head -1 results/s9_estimator_sensitivity/results.csv | tr ',' '\n' | grep '^s9_'
   ```
   This must return at least 11 column names.
9. **`policy_paper_label` column.** Confirm the column is present and
   populated by checking:
   ```bash
   awk -F',' 'NR==1{for(i=1;i<=NF;i++) if($i=="policy_paper_label") c=i} NR==2{print $c}' \
     results/s9_estimator_sensitivity/results.csv
   ```
   This must print one of `Null`, `Baseline-PF`, `RTX-Assist`, `Realloc`.
10. **Section / figure numbering.** A full LaTeX rebuild must produce a
    clean log. If §6.7 / §6.8 are now results (not future-work) sections,
    the table of contents will reorder slightly -- that is intended.

---

## 4. Numerical highlights to call out in the cover letter

If you are submitting a revised version with a cover letter, surface these
numbers up front. They are the single best evidence that the editorial
revisions are backed by real new computation, not text-shuffling.

| Claim | Where | Number to cite |
|---|---|---|
| S9 PDR robust to AP-side observability at low MCS | §6.7 / Tab. 10 | PDR = 1.0000 across all three profiles at MCS 0 and MCS 1 (jammer-ON PDR >= 0.9992); aggregated over 100 000 packets per row, 18 rows per cell |
| S9 PDR partially degrades at high MCS under impairment | §6.7 / Tab. 10 | MCS 3 reactive PDR drops from 0.9869 (ideal) to 0.9756 (moderate); jammer-ON from 0.9802 to 0.9608 |
| Estimator impairment trades PDR for more defers | §6.7 / Tab. 10 | Proactive-defer count grows monotonically from 27 122 to 35 147 at MCS 0 and from 51 824 to 58 607 at MCS 3, ideal -> conservative |
| **Cooldown is the dominant S9 component** | §6.8 / Tab. 11 | Removing the cooldown collapses MCS 3 reactive PDR from 0.9869 to 0.7522 and jammer-ON PDR from 0.9802 to 0.6739 |
| PER-margin contribution is small but non-zero | §6.8 / Tab. 11 | `snir_only` costs ~0.5 pp at MCS 3 reactive (0.9824 vs 0.9869) |
| Jammer-flag contribution is negligible in this regime | §6.8 / Tab. 11 | `full` and `no_jammer_flag` are identical to four decimal digits |
| Fairness preserved under all ablation variants except `no_cooldown` | §6.8 / Tab. 11 | Jain >= 1.0000 except `no_cooldown` MCS 3 (0.9950) |

---

## 5. End-to-end reproducibility commands

Anything ChatGPT proposes must be reproducible from this repo with the
commands below. If a reviewer asks "where did Table 10 come from?", the
answer is exactly:

```bash
# (one-time) build
make build

# Tab. 10 -- estimator-impairment sensitivity
python3 scripts/run_sweep.py --config configs/s9_estimator_sensitivity.yaml
python3 scripts/aggregate_s9_sensitivity.py \
  --input-dir results/s9_estimator_sensitivity \
  --output    docs/paper_tables/tab10_sensitivity.md

# Tab. 11 -- component ablation
python3 scripts/run_sweep.py --config configs/s9_ablation.yaml
python3 scripts/aggregate_s9_ablation.py \
  --input-dir results/s9_ablation \
  --output    docs/paper_tables/tab11_ablation.md
```

Wall-clock budget on a stock laptop (Linux x86_64, 8 cores, ns-3 release
build): under 3 minutes for both campaigns at 100 000 packets/row.

The CSV under `results/s9_estimator_sensitivity/results.csv` and
`results/s9_ablation/results.csv` carry every metadata column needed to
re-derive the tables, plus the full S9 parameter vector and ablation
switches for every individual row. See `README.md` §"S9 Estimator
Sensitivity and Ablation" and `BIBLIOGRAPHY.md` for the code↔citation map.

---

## 6. What to avoid asking ChatGPT to do

- **Do not** ask the model to re-derive PER waterfall midpoints or to
  recompute the (3.0, 6.0, 15.5) dB triple. Those are calibrated against
  TGax AWGN curves in `BIBLIOGRAPHY.md` and changing them invalidates the
  archive.
- **Do not** ask the model to invent missing references. `paper.bib` is
  curated by hand and any new citation needs a manual sanity check against
  the original publication.
- **Do not** ask the model to change the S9 mechanism. The base idea (76-
  symbol cooldown, AP-side SNIR-estimate-driven reallocation, critical
  mask) is fixed by §4.3 and reproduced in `src/core-harness/core-harness.cc`.
  Editorial changes only.
- **Do not** ask the model to summarise the paper. The paper exists; the
  task is to improve it, not to retell it.

---

## 7. If something goes wrong

| Symptom | Most likely cause | Fix |
|---|---|---|
| ChatGPT produces numbers that do not match `tab10_sensitivity.md` | Model hallucination | Re-paste the markdown table inline and require literal copy |
| ChatGPT inserts new acronyms (e.g. "PFD-Realloc") | Drift from the policy-label spec | Re-issue the global constraint #4 and the B6 footnote |
| LaTeX fails with "missing \cite key" | C9 import incomplete | Re-import `paper.bib` and rerun `bibtex` |
| Italian text reappears in the diff | Model copied from the duplicated paragraph | Re-issue A4 / A5 / A7 / A8 with the exact Italian sentences in quotes |
| Algorithm 1 lost the four switches | Model collapsed back to the original listing | Re-issue B4 verbatim |

---

Maintainers: keep this guide in sync with `PAPER_IMPROVEMENTS.md`. If a new
priority-A or priority-B item is added there, mirror it as a §2.x prompt
here.
