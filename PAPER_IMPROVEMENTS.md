# Paper improvement notes -- [Fan26]

Concrete, prioritised editorial / scientific suggestions for the manuscript
*"Resilient OFDMA Scheduling under Reactive Jamming in Industrial IEEE
802.11ax-like Networks: An ns-3 Scheduler-Harness Study"*, after the
simulator-side work documented in `README.md`, `BIBLIOGRAPHY.md`, and
`results/s9_*`.

The goal is **not** to alter the scientific framing or the S9 mechanism --
the policy idea, the 76-symbol cooldown, and the AP-side SNIR-estimate-driven
reallocation stay exactly as the paper presents them. The notes below are
mechanical / editorial improvements that the new code now makes feasible.

---

## Priority A -- Defects in the current PDF that must be fixed before
   resubmission

| ID | Where | Issue | Suggested fix |
|---|---|---|---|
| A1 | §4.3 title | The title line is duplicated as a copy-paste artefact: *"S9/Realloc: AP-Side Instantaneous-SNIR-Driven ReallocationS9/Realloc: AP-Side Estimated-SNIR-Driven Reallocation"*. | Keep the second variant only: *"S9/Realloc: AP-Side Estimated-SNIR-Driven Reallocation"*. The word **estimated** is critical because §4.5 introduces the impairment profiles. |
| A2 | §4.3 body, eq. (3) and surrounding paragraph | The sentence *"At each scheduler step, the AP evaluates the instantaneous SNR/SINR estimate..."* is duplicated, with one variant using "instantaneous" and one using "estimated". Eq. (3) also appears twice (one PER_crit variant, one $\hat{J}$ variant). | Keep only the **estimated** variant of the prose **and** the second variant of Eq. (3) that uses $\hat\gamma_{u,r}(t)$ and $\hat J_r(t)$. Drop the "instantaneous" wording globally. |
| A3 | §4.3, just below Eq. (4) | Same duplication for Eq. (4). | Keep only the variant using $\hat\gamma_{u,r}(t)$ and $\hat J_r(t)$. |
| A4 | §4.4 final paragraph | Italian draft note inside the body: *"Future work should inject estimation noise, bias, quantization, and update delay into $\hat\gamma_{u,r}(t)$. The present harness instantiates $\hat\gamma_{u,r}(t)$ using the simulated per-packet SNIR..."* and a second paragraph that says the same thing in slightly different words. | Merge into a single paragraph using the second variant, which already names the **ideal observability profile** and the moderate/conservative profiles. |
| A5 | §6.7 paragraph above the empty Table 10 | Italian draft note: *"Questa tabella 10 va inserita solo se abbiamo realmente generato i risultati."* | Either generate the table (the simulator now does this -- see `results/s9_estimator_sensitivity/tab10_sensitivity.md`) or move §6.7 to §8 Limitations. The recommended route is to **fill Table 10** because the data are now reproducible. |
| A6 | §6.8 Table 11 | Empty placeholder. | Fill with `results/s9_ablation/tab11_ablation.md`. |
| A7 | §8 Limitations, paragraph about observability | Italian draft note: *"ma se invece aggiungessimo veramnete la sensitivity/ablation... possiamo invece dire questo"* with a candidate replacement paragraph immediately below. | Drop the Italian sentence and keep the replacement paragraph, lightly edited. |
| A8 | §9 Conclusion | Italian draft note: *"con sensitivity e ablation invece potremmo dire:... Future work should extend the estimator-impaired and ablation results with full ns-3 Wi-Fi rows..."* | Once §6.7-§6.8 are populated, use the candidate "Future work should extend the estimator-impaired and ablation results..." sentence directly. |
| A9 | §6.1 first paragraph and §6.10 | The two sentences that introduce the constant-jammer saturation as a boundary appear twice (once in the contributions list and again in §6.10). Keep both, but make the §6.10 one explicitly say "as anticipated in §3.4". | Cross-reference and de-duplicate. |
| A10 | §2.3 contributions list | The third bullet starts *"we compare three transparent scheduler-level policies"* but the second bullet already says *"we compare three transparent policies"*. | Merge into a single bullet and keep the longer text that explicitly limits the claims to resilience / reliability metrics. |

---

## Priority B -- Substantive improvements enabled by the new infrastructure

### B1. Promote §6.7 from future-work to results

The estimator-sensitivity campaign is now fully reproducible via:

```bash
python3 scripts/run_sweep.py --config configs/s9_estimator_sensitivity.yaml
python3 scripts/aggregate_s9_sensitivity.py
```

The aggregator outputs paper-Table-10-ready markdown in
`results/s9_estimator_sensitivity/tab10_sensitivity.md`. Each row carries the
full estimator parameter vector so a reviewer can verify reproducibility from
the CSV alone. The campaign uses CM8 reactive jamming, 20 dB target SNR,
10 dBm jammer, the three study MCS, three seeds, three payloads, two
distances -- the exact aggregation convention used by Table 8 of the paper.

**What the data say** (paper-grade, 100 000 packets/row, three seeds, three
payloads, two distances; full table in `docs/paper_tables/tab10_sensitivity.md`):

| MCS | Profile | PDR | PDR jammer-ON | # defer events |
|---|---|---|---|---|
| 0 | ideal | 1.0000 | 1.0000 | 27 122 |
| 0 | moderate | 1.0000 | 0.9999 | 31 041 |
| 0 | conservative | 1.0000 | 0.9999 | 35 147 |
| 1 | ideal | 1.0000 | 1.0000 | 29 188 |
| 1 | moderate | 0.9998 | 0.9992 | 32 752 |
| 1 | conservative | 0.9998 | 0.9992 | 37 252 |
| 3 | ideal | 0.9869 | 0.9802 | 51 824 |
| 3 | moderate | 0.9756 | 0.9608 | 54 876 |
| 3 | conservative | 0.9765 | 0.9622 | 58 607 |

**Key narrative arc** that should go into §6.7 once the table is in:

> S9's gain at MCS 0 and MCS 1 is robust to AP-side observability quality:
> all three profiles deliver PDR ~= 1.0000 and jammer-ON PDR >= 0.9992 across
> 32.4 M simulated packets. The estimator profile manifests itself instead
> through the proactive-defer count, which rises monotonically from
> 27 k (ideal) to 35 k (conservative) at MCS 0 and from 52 k to 59 k at
> MCS 3 -- exactly the expected behaviour: noisier SNIR estimates and a
> higher false-alarm jammer probability trip the critical-mask more often.
> At MCS 3 the gain partially erodes under impairment: PDR drops from
> 0.9869 (ideal) to 0.9756 (moderate), and jammer-ON PDR from 0.9802 to
> 0.9608. The conservative profile recovers part of the loss
> (PDR 0.9765, jammer-ON 0.9622) because its over-deferring bias protects
> packets that the moderate profile occasionally clears as safe. This is
> consistent with the paper's claim that S9 is most useful when AP-side
> RU-quality information is sufficiently timely **and** sufficiently
> conservative under uncertainty.

### B2. Promote §6.8 from future-work to results

The ablation campaign is generated via:

```bash
python3 scripts/run_sweep.py --config configs/s9_ablation.yaml
python3 scripts/aggregate_s9_ablation.py
```

The output is in `results/s9_ablation/tab11_ablation.md`. The campaign uses
the six-user round-robin diagnostic subset so the Jain index in Table 11 is
directly comparable to Table 12.

**Headline numbers** (paper-grade, 100 000 packets/row, six-user round-robin
fairness subset; full table in `docs/paper_tables/tab11_ablation.md`):

| Variant | MCS3 reactive PDR | MCS3 reactive PDR-ON | Jain |
|---|---|---|---|
| `full` | 0.9869 | 0.9802 | 1.0000 |
| `no_jammer_flag` | 0.9869 | 0.9802 | 1.0000 |
| `no_cooldown` | **0.7522** | **0.6739** | 0.9950 |
| `snir_only` | 0.9824 | 0.9826 | 1.0000 |

**Key narrative arc** for §6.8 once the table is in:

> The ablation isolates the **anti-oscillation cooldown** as the dominant
> contributor to the S9 gain. Removing the cooldown collapses MCS 3 PDR from
> 0.9869 to 0.7522 (and the jammer-ON PDR from 0.9802 to 0.6739), even
> though the critical-mask defer still fires. The reason is mechanical:
> without cooldown, the next attempt falls inside the same coherence window
> as the deferred one, so the channel state has not had time to decorrelate.
> Jain's fairness index also drops slightly (0.9950 vs 1.0000) because the
> aggressive re-attempts amplify per-user differences in instantaneous SNIR.
> The jammer-flag check adds zero measurable value in this regime (`full`
> and `no_jammer_flag` are identical to four decimal digits) because the
> SNIR margin alone is already triggered whenever the reactive jammer is
> active. The PER-margin check (`snir_only`) costs only ~0.5 pp of PDR at
> MCS 3 reactive; on the clean baseline it costs ~0.7 pp. We retain the
> full S9 in the recommendation because the additional checks carry
> negligible computational cost (§4.6) and improve robustness on rows where
> the SNIR margin alone is insufficient (e.g. shallow waterfall regions).

### B3. Add Figure 9 and Figure 10 (visual companions)

Two bar plots, one per table, summarising Tab. 10 and Tab. 11 visually.
Suggested layout: 3 subplots side-by-side (one per MCS), with the profile /
variant on the x-axis and PDR / PDR-ON / p95-delay on the y-axes (twin axis).
This mirrors Figure 6 from §6.4. The plot script can reuse
`scripts/plot_results.py` as a starting point.

### B4. Algorithm 1 listing -- include the four ablation switches explicitly

The current Algorithm 1 hides the ablation seams. Suggested revision:

```
Algorithm 1: S9/Realloc AP-side SNIR-estimate scheduler with optional ablation
Input: users U, RUs R, AP-side estimates gamma_hat_{u,r}(t),
       cooldown counters c_u, estimated jammer exposure J_hat_r(t).
       Boolean switches: use_snir_margin, use_per_margin, use_jammer_flag,
       use_cooldown. (Default true; ablation studies toggle individual flags.)

for each scheduling opportunity t do
  for each candidate pair (u, r) do
    compute PER_hat_{u,r}(t) = f_m(gamma_hat_{u,r}(t))
    critical = (use_snir_margin   AND gamma_hat_{u,r}(t) < gamma_out)
            OR (use_per_margin    AND PER_hat_{u,r}(t)  > PER_crit)
            OR (use_jammer_flag   AND J_hat_r(t) = 1)
  end for
  initialize assignments using the Baseline-PF ranking
  for each assigned user u on RU r do
    if critical AND c_u = 0 then
      choose r* = argmin_{r' in R_avail} PER_hat_{u,r'}(t)
      if PER_hat_{u,r*}(t) < PER_hat_{u,r}(t) then
        reassign u to r*
        if use_cooldown then c_u = 76 symbols
      end if
    else if c_u > 0 then
      decrement c_u
    end if
  end for
  update packet-delivery, loss, delay, and recovery metrics
end for
```

This makes the §6.8 ablation table direct and unambiguous.

### B5. Data and Reproducibility Statement -- list the new CSV columns

The §9 paragraph already names *"estimator profile, SNIR-estimation noise,
estimation delay, jammer missed-detection probability, jammer false-alarm
probability, cooldown configuration, and enabled S9 components"* as the
contract for future estimator campaigns. The simulator now exports exactly
those columns (`s9_estimator_profile`, `s9_snir_noise_std_db`,
`s9_snir_bias_db`, `s9_snir_staleness_slots`,
`s9_jammer_missed_detection_prob`, `s9_jammer_false_alarm_prob`,
`s9_per_crit`, `s9_gamma_out_db`, four `s9_ablation_disable_*` flags,
`s9_proactive_defer_enabled`, `s9_proactive_defer_count`). A one-sentence
update in §9 turns the contract into a delivered fact:

> Every CSV row in the new estimator-sensitivity and ablation archives carries
> the active estimator profile (`s9_estimator_profile`), the five impairment
> knobs (`s9_snir_noise_std_db`, `s9_snir_bias_db`, `s9_snir_staleness_slots`,
> `s9_jammer_missed_detection_prob`, `s9_jammer_false_alarm_prob`), the two
> critical-mask thresholds (`s9_per_crit`, `s9_gamma_out_db`), and the four
> component-ablation switches (`s9_ablation_disable_jammer_flag`,
> `s9_ablation_disable_cooldown`, `s9_ablation_disable_snir_margin`,
> `s9_ablation_disable_per_margin`).

### B6. Cross-reference the paper-facing policy labels with the CSV archive

The CSV archive retains `PLS-RTX` / `PLS-Realloc` for continuity but exports
the paper-facing labels (`RTX-Assist`, `Realloc`) in the dedicated column
`policy_paper_label`. A footnote at the first mention of S8 / S9 should say:

> The CSV archive keeps the legacy labels `PLS-RTX` and `PLS-Realloc` for
> archive continuity; the paper-facing names ("RTX-Assist", "Realloc") are
> available in every CSV row through the `policy_paper_label` column. The
> archive does **not** export secrecy-capacity, secrecy-outage, or
> Eve-channel quantities; reviewers and future authors should treat the
> "PLS-" prefix purely as an archive identifier.

---

## Priority C -- Smaller editorial polish

| ID | Where | Fix |
|---|---|---|
| C1 | §1 contributions list | The third bullet ("we compare three transparent scheduler-level policies...") duplicates the second. Merge. |
| C2 | §3.1 HE-MCS list | Add a small inline table with the 20 MHz / 1 SS / GI 3.2 us rates: HeMcs0 = 8.6 Mb/s, HeMcs1 = 17.2 Mb/s, HeMcs3 = 51.6 Mb/s. The simulator implements exactly these values (`HeDataRateMbps()` in `src/core-harness/core-harness.cc`). |
| C3 | §3.3 PER thresholds | After the (3.0, 6.0, 15.5) dB triple, add the explicit note: *"These midpoints are exposed as CLI flags `--per-theta-bpsk`, `--per-theta-qpsk`, `--per-theta-16qam` (default 3.0, 6.0, 15.5 dB) and `--per-slope` (default 1.15). They calibrate the sigmoid to the TGax AWGN PER curves [TGax571] and are reproducible from `BIBLIOGRAPHY.md`."* |
| C4 | §3.4 reactive jammer | Cite [Bay08] / [Bay13] for the reactive jammer model. The simulator's reactive-jammer code already credits both references in its header comment. |
| C5 | §4.6 complexity | Add `O(U)` storage for the new per-user cooldown counters `c_u` to the S9 memory bound. Already implicit but worth stating. |
| C6 | §5.4 seed independence | The seed audit script is `scripts/check_seed_independence.py`. Add a one-line citation in the Data and Reproducibility Statement. |
| C7 | §6.6 Fig. 8 | Add the 0 dBm reactive jammer point to the abscissa so the curve covers the full archive range (0, 10, 20 dBm). The simulator already produces those rows under `results/paper_v2`. |
| C8 | §8 Limitations, paragraph 4 | The reactive jammer paragraph cites no reference; add [Bay08] / [Gri21] as anchors for the "waveform-level interference, partial-band jamming, adjacent-channel leakage" sentence. |
| C9 | References | Several bibliography items in the manuscript currently use ad-hoc author lists. `paper.bib` in this repo provides clean BibTeX for [Kho19], [Lop19], [Den20], [Fan24], [Aij20], [Ban18], [Bel19], [Tut21], [Mag21], [Mon24], [Ang22] -- import them to get consistent formatting. |

---

## Priority D -- Substantive but optional extensions

These are scientifically interesting and now technically cheap, but they
require additional pages and may not fit a tight page budget.

### D1. Sensitivity of the PDR ranking to the PER waterfall midpoints

Sweep `--per-theta-bpsk`, `--per-theta-qpsk`, `--per-theta-16qam` by +/-1 dB
and check whether the S4 < S8 < S9 ranking is preserved. The simulator
already exposes these as CLI flags, so the campaign is one YAML file away.

### D2. Reproducibility of Table 12 fairness numbers

Re-run `configs/fairness_minirun.yaml` and verify that the values in
Table 12 of the paper match the current simulator output. If they do, add a
sentence in §6.9 stating that the Table 12 numbers are reproducible from
the committed CSV; if they don't, document the version that produced them.

### D3. A four-row mini-table inside §4.5 listing the three preset profiles

The numerical content of `ApplyS9EstimatorProfile()` (in
`src/study-parameters.cc`) is currently spread across the prose. A small
inline table would help readers cross-reference the Tab. 10 rows:

| Profile | sigma_SNIR | bias | Delta_t | P_md | P_fa |
|---|---|---|---|---|---|
| ideal | 0 dB | 0 dB | 0 slots | 0 | 0 |
| moderate | 1 dB | 0 dB | 1 slot | 0.05 | 0.05 |
| conservative | 3 dB | 0 dB | 4 slots | 0.20 | 0.10 |

### D4. Add Wi-Fi 7 / 802.11be multi-link as explicit future work

§2.2 mentions multi-link briefly. A one-paragraph extension in §8 stating
*"a future port of the harness to multi-link operation (MLO) would let the
Realloc policy escape across links, not only across RUs; the current
`s9_proactive_defer` flag is the natural extension point"* gives a concrete
path forward.

---

## Verification checklist before submission

- [ ] All Priority A items resolved (no Italian draft notes, no duplicate
      paragraphs/equations).
- [ ] Tables 10 and 11 populated from the freshly run campaigns (10 000
      packets/row, three seeds, three payloads, two distances, fixed 20 dB
      target SNR and 10 dBm jammer).
- [ ] §9 Data and Reproducibility Statement reflects the new CSV columns.
- [ ] `git diff` from the latest tagged release shows only camera-ready
      polish; no scientific drift.
- [ ] `python3 scripts/run_tests.py` passes (study-parameter-tests + the
      lightweight integration tests including the four new S9 tests).
- [ ] BibTeX is consistent with `paper.bib`.

---

## Reproducing every claim from a clean checkout

```bash
# 1. Build.
make -j$(nproc)

# 2. Main paper campaign (CM8, 36 450 rows). Re-uses the existing config.
python3 scripts/run_sweep.py --config configs/paper_v2.yaml      # ~few hours

# 3. Six-user fairness diagnostic (Tab. 12).
python3 scripts/run_sweep.py --config configs/fairness_minirun.yaml

# 4. Estimator sensitivity (Tab. 10).
python3 scripts/run_sweep.py --config configs/s9_estimator_sensitivity.yaml
python3 scripts/aggregate_s9_sensitivity.py

# 5. Component ablation (Tab. 11).
python3 scripts/run_sweep.py --config configs/s9_ablation.yaml
python3 scripts/aggregate_s9_ablation.py

# 6. Seed-independence audit, cross-validation, plots.
python3 scripts/check_seed_independence.py
python3 scripts/run_cross_validation.py
python3 scripts/plot_results.py

# 7. Optional but recommended sanity tests.
python3 scripts/run_tests.py
```
