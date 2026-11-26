# Reviewer Response: Results and What We Learned

Computed evidence for the revision of Communications Engineering manuscript 28847ff1 (Reviewer 1 minor, Reviewer 2 major). This document says what each result is, which reviewer comment it answers, and what failed along the way. It is the source for the rebuttal letter, not the letter itself.

> **Status (3 November 2026):** All planned runs are finished and every number below comes from a file in this repository. Checkpoints were auto-approved in batch, so nothing here has had analyst review. Four findings change claims in the current draft and need author decisions before anything is cited: see [Decide before citing](#decide-before-citing).
>
> **Update (8 November 2026, evening):** APSIM-GTAP (AgResilience) was added as a 35th model and run on copies of May's and Run A's state, and three robustness checks from AgResilience were run ([details](#apsim-gtap-and-robustness-checks-november-2026)). Scenario orderings hold under elasticity perturbation, so the cross-scenario patterns come from the extracted inputs.
>
> **Update (8 November 2026):** MAM's May cells contain no macro data (wrong EIA table), so May ran one full model, not two ([R1.1](#r11-which-models-ran-full-or-simplified)). Fixes for OpenCGE, Energy Flux LNG profits, SimRLFab and MAM, plus observed World Bank prices, are ready for two supplementary runs that have not run yet ([details](#supplementary-full-model-runs-and-observed-prices-november-2026)).
>
> **Update (14 November 2026):** Both supplementary runs are complete, with 65 of 65 cells each. Energy Flux LNG profits, SimRLFab and OpenCGE (OG-Core) ran their own code in all five scenarios, and MAM reports the AEO2025 baseline. Across all result sets, **5 models ran their own code**, 1 contributes a published baseline and 16 are closed-form approximations ([counts](#what-we-can-tell-reviewers)). Three cautions before citing them:
>
> - **OpenCGE:** cite its pattern, not its magnitudes. An unsourced coefficient makes its GDP losses 3–4× the literature-calibrated estimates, and its LNG input was the wrong quantity in both runs ([OpenCGE](#opencge)).
> - **LNG profits:** cite the windfall from the scenario's price rise. Most of the reported total reflects the workbook's starting prices ([LNG profits](#energy-flux-lng-war-profits)).
> - **Observed prices (run 2):** they change price levels but not the modelled percent responses ([run 2](#run-2-results-observed-pre-crisis-prices)).

---

## Table of contents

1. [Summary](#summary)
2. [Decide before citing](#decide-before-citing)
3. [Result sets](#result-sets)
4. [What we learned from the failures](#what-we-learned-from-the-failures)
5. [Reviewer 1](#reviewer-1)
6. [Reviewer 2](#reviewer-2)
7. [Data-integrity checks on the draft](#data-integrity-checks-on-the-draft)
8. [Supplementary full-model runs and observed prices](#supplementary-full-model-runs-and-observed-prices-november-2026)
9. [APSIM-GTAP and robustness checks](#apsim-gtap-and-robustness-checks-november-2026)
10. [Disclosures for the rebuttal](#disclosures-for-the-rebuttal)
11. [Open items only the authors can fill](#open-items-only-the-authors-can-fill)
12. [Regenerating the results](#regenerating-the-results)

---

## Summary

**The orchestration held up. The weak link is what the LLM feeds into the models.**

- **Model outputs are reproducible.** Rerunning the May configuration gave 5 of 5 identical scenario narratives and 163 of 169 identical parameter sets. 24 of 24 re-executed cells reproduce every shared number, and none of the 5 cells with matching recorded inputs gave different outputs. This shows reproducibility with one model at temperature 0, not robustness to the choice of LLM.
- **Most failures were in the plumbing around the models.** Uneven coverage came from a file-naming bug. The "Sonnet 18 runs" figure came from a silent output cap. Failed backends stopped on API compatibility before any model ran.
- **LLM input errors are the main scientific risk.** The domain models faithfully compute whatever they are given, and some of what they were given is wrong. The clearest case is Scenario E, where a vocabulary mismatch means destroyed water infrastructure registers as intact. Correcting it in a sensitivity replay makes E worse than D on GDP, which reverses the published ordering.
- **Automated checks caught less than we assumed.** The audits written for this revision found most of these problems. The pipeline's own checks missed several, and flags they did raise had no reader because checkpoints were auto-approved.

---

## Decide before citing

These four findings change claims in the draft. The revision stays light-touch either way, but each needs an author decision.

| # | Finding | Evidence | Options |
|---|---|---|---|
| 1 | **Scenario E water shock is understated, and pycge did not apply it at all.** E looks milder than D on GDP in both CGE reductions. | [Water under E](#water-linkage-under-scenario-e) | **Recommended:** keep May, disclose, and stop describing E as milder than D. Alternative: fix the two inputs and rerun E only. |
| 2 | **The −15.7 was never a model output.** It appears in LLM commentary. No rerun was needed to change the model's value, which is −0.157 throughout. | [R1.4](#r14-the-scenario-a-gdp-value) | Rewrite the R1.4 account. Only the authors know how the number reached the draft. |
| 3 | **"Helium essentially undisrupted" comes from an extraction default.** The input was a low-confidence 0% in A, B and C. | [R2.3](#r23-uneven-scenario-coverage) | Withdraw the claim rather than restricting it to B and C. |
| 4 | **The main run does not meet the paper's own clean-synthesis definition.** May has 7 of 30 synthesis sections failed. | [R1.5](#r15-clean-synthesis-and-runtime) | State this next to the definition. Model numbers are unaffected. |

---

## Result sets

| Result set | Run or batch ID | Job | Code | Use it for | Location |
|---|---|---|---|---|---|
| **May main run** | `20260504_222710` | 25807 | May code, Llama-3.1-8B-Instruct on vLLM, temperature 0 | Basis of the manuscript, Figs 3–5 | `data/20260504_222710/`, `docs/revision/fidelity/20260504_222710/` |
| **May, filled** | `fill_may_20260504_222710` merged into May | 87629 | Current adapters, May's saved parameters, no LLM | Coverage only. **Not fidelity:** May's synthesis never saw these cells | `docs/revision/runs/20260504_222710_filled/` |
| **Run A** | `rev_20261102_llama8b_r2` | 87298 | Current code, same model and temperature as May | Reproducibility, **not** robustness to LLM choice | `docs/revision/runs/rev_20261102_llama8b_r2/` |
| **Deterministic baseline** | `baseline_rev_llama8b` | 87298 | Current code, analyst YAML, no LLM | R2.1 comparator | `docs/revision/runs/rev_20261102_llama8b_r2/baseline/` |
| **July backends** | `20260701_020011` | 44917 | July code, not in the current tree | Original 8 backends × 8 weeks in the manuscript | `docs/revision/runs/backend_comparison_20260701_020011/` |
| **Reruns of July failures** | `fill_20261102` | 87632, 88042, 88132 | Current code, per-run overrides | Reruns of July's failures | `docs/revision/runs/backend_comparison_fill_20261102/` |
| **Added backends** | `alt_20261102` | 88132 | Current code | Added in revision for retired models, never in their rows | `docs/revision/runs/backend_comparison_alt_20261102/` |
| **Backend status** | all three batches | 88225 | n/a | Before and after, per backend and week | `docs/revision/runs/backend_status_20261102/` |

Scenario letters: A = `swift_contained`, B = `prolonged_contained`, C = `swift_escalated`, D = `prolonged_escalated`, E = `infrastructure_collapse`. File paths below that start with `runs/` are under `docs/revision/`.

**Backend behind Figs 3–5 (checklist item 0):** `meta-llama/Llama-3.1-8B-Instruct` on vLLM, job 25807, node `quadro1`.

---

## What we learned from the failures

Each row says who actually caught the problem, so the letter does not credit the framework with something an audit found.

| # | What failed | Why | Caught by | Lesson | Answers |
|---|---|---|---|---|---|
| 1 | **Records lost.** May kept 99 of 170 records, July 100 of 170 per run | Task indices restart per tier, so macro files overwrote commodity files | Audit | Coverage must come from a ledger of every expected cell. Fixed with tiered file names | R1.2, R2.3, R2.5 |
| 2 | **Empty runs marked `ok`.** 5 Sonnet weeks generated 0 scenarios | Output hit the 16,000 token cap, and tool-call parsing returned an empty list with no error | Audit, then a probe | "No silent omissions" was broken. The pipeline now stops on a short scenario set | R2.5, R1.5 |
| 3 | **Backends rejected before any model ran.** 37 July runs | Providers rejected structured output or temperature | Audit | Failures measured API compatibility, not analytic quality | R2.5 |
| 4 | **Models retired.** 25 failed runs can no longer be retried | Groq withdrew 4 models between July and November | Rerun attempt | Hosted-model results may not be reproducible, so pin versions and keep raw output | R2.5, code availability |
| 5 | **A status of `ok` hides thin runs.** Qwen3.8 ran 8 of 8 weeks | Parameter extraction returned nothing for most cells: 134 of 170 in the week inspected, 0 outcomes in all 8 weeks | Clean-synthesis definition | Report quality measures, not run status. Here the definition did its job | R2.5, R1.5 |
| 6 | **Structured output breaks in model-specific ways** | Opus omitted `scenarios` (2 weeks). Haiku put pseudo-XML in `observed_indicators` (7). Qwen3.6 returned 4 of 5 scenarios (6) | Schema and count checks | Validation works as a gate. A one-off probe does not predict a batch | R2.5 |
| 7 | **Water infrastructure read as intact under E** | The LLM wrote `damaged`, which is not in CWatM's vocabulary. Unknown values default to 1.0 with only a warning | Audit | Categorical inputs need enforced enumerations | R2.3, R2.4 |
| 8 | **Water shock dropped by pycge under E** | `pycge.yaml` overrides the default commodity mapping and omits `water`, so the shock is discarded silently | Audit and replay | A forwarding record proves a value was sent, not that it was used | R2.3 |
| 9 | **Percent written as a fraction** | "30% of global helium supply" extracted as `0.3` under E, at high confidence | Audit | Units need range checks at extraction | R2.4, R1.4 |
| 10 | **Missing information became a confident assumption** | `rerouting_via_cape=false` at high confidence in all 5 scenarios, while the notes say the narrative is silent | Audit | Confidence labels did not separate "stated" from "assumed" | R2.4, R1.3 |
| 11 | **LLM commentary rescaled a model number** | "15.7% decline" for −0.157, and "6.9%" for −0.6953 in the same passage | Audit written for this revision | Stage 5 commentary sat outside the fidelity audit | R1.4, R2.4 |
| 12 | **Flags raised, nobody read them** | Forwarding flagged 200% deviations, but checkpoints were auto-approved | Audit | Batch mode removes the reader that the flags depend on | R1.5, R2.4 |
| 13 | **Provenance claims more than happened** | Saved `config.llm` recorded the cluster default rather than the backend. Traces print "analyst validation: approved" for auto-approval | Audit | Provenance must record what actually ran and who approved it | R1.3, R2.5 |

One check did work as designed at run time: the new scenario-count check stopped Qwen3.6 in 6 weeks. Its probe stopped normally at 14,459 tokens without Scenario E, so a run like that would otherwise have continued without the tail-risk scenario. The error text says the reply "may have been truncated", which is misleading in that case.

---

## Reviewer 1

### R1.1 Which models ran, full or simplified

**Finding.** In May with the lost cells filled, 18 models produced a completed record: 16 calibrated closed-form approximations, 1 published-output ingestion (MAM) and 1 full upstream model (Energy Flux gas power). **Only Energy Flux gas power produced model results.** MAM's completed cells contain no macro data (corrected 8 November 2026, see below).

- **MAM ingested the wrong table.** The cluster job downloaded `.../aeo/excel/aeotab_19.xlsx`, a legacy URL that serves AEO2021 Table 19 (CO2 emissions by end use), not AEO2025 macro indicators. MAM's outputs hold only metadata and the CO2 row labels. The oil price path shown under `mam` in the May synthesis (`synthesis.json`, swift_contained and infrastructure_collapse) is POLES-JRC's forwarded path, taken from MAM's `_upstream_overrides` audit record. It is not a MAM result.
- **Most stand-ins do not use the named model's parameters.** 11 of the 16 approximations take every parameter from other literature (e.g. the POLES-JRC slot uses Hamilton 2009 and Baumeister & Peersman 2013 elasticities). 5 mix in some of the named model's published numbers (fed_oil, world_helium_model, argonne_abm, nrel, cwatm). The inventory now records this as `parameter_provenance` and prints each approximation under its own name.
- 17 models completed in all 5 scenarios. Energy Flux gas power completed in A–D, and E has no parameter record.
- The draft's count of 16 reflects surviving records. `argonne_abm` is among the 18 only through the fill, since it never ran in May.
- `energy_flux_lng_profits` failed validation in all 5, because Llama did not extract the required prices. The draft's "Energy Flux" can only mean gas power.
- SimRLFab and NEMS completed in no scenario.

**Files:** `runs/20260504_222710_filled/model_inventory_20260504_222710.{md,tex}`, `coverage/coverage_ledger.csv`.

**Status:** Answered. One table also serves R2.2.

### R1.2 Why model counts vary by scenario

**Finding.** The variation came from lost records, not model relevance or a design choice. The commodity tier ran in every scenario, but its records were overwritten by the macro tier.

- **Macro inputs were not affected.** May's macro models read upstream values before the overwrite, and 73 of 73 identity-transform overrides match the re-executed cells (15 others use transforms and were not checked).
- **Filling the gaps.** 70 cells were added: 40 completed, 14 failed, 16 skipped. Of these, 60 had lost records and 10 (`argonne_abm`, `simrlfab`) never ran in May because no downstream manifest existed.
- **Result.** May now has 169 records and 89 completed cells. Run A has 170 records with none missing.

| Why a cell did not complete (May, filled) | Cells |
|---|---|
| Missing data or binary | 29 |
| Stub | 14 |
| Missing configuration | 10 |
| Runtime error | 10 |
| Runtime or licence missing | 10 |
| Validation failed | 7 |
| Parameter extraction missing | 1 |
| **Total not completed** | **81 of 170** |

The missing parameter cell is Energy Flux gas power under E. The same cell failed in Run A at the 8,192 token cap, so May's gap is probably the same failure.

**Files:** `runs/20260504_222710_filled/refilled_cells.md`, `coverage/`.

**Status:** Answered. **Disclose** that added cells ran on current adapter code and that May's synthesis saw only the 99 original records.

### R1.3 Worked provenance example

Scenario C oil impulse, as seen by MPSGE.jl in the May run:

| Step | Content |
|---|---|
| 1. Narrative | "The closure disrupts approximately 21% of global oil supply and 25% of global LNG trade." |
| 2. Extracted parameter | `oil_price_shock_pct` = 0, confidence low |
| 3. Forwarding override | LLM 0 replaced by 58.25 from `poles_jrc.peak_price_change_pct`, deviation 200%, flagged at the 50% threshold. POLES itself ran on an extracted `supply_loss_mbd` of 4.32 |
| 4. Model output | `mpsge_jl.oil_price_shock_pct` = 58.25 |
| 5. Synthesis | "The oil price shock is expected to be 58.25% due to the Strait of Hormuz closure." |

Fed oil gives a second complete chain: LLM 25 replaced by 58.25, deviation 79.88%, flagged. The POLES trace is incomplete at step 5 because no synthesis outcome cites POLES directly, so use MPSGE.jl or Fed oil in the paper.

**Two cautions.** The trace prints "analyst validation: approved", which was auto-approval and should not be presented as human review. And this same chain shows that the "Swift" scenario's narrative says the closure "lasted for 4 months", against the framework's 4–6 weeks.

**Files:** `runs/20260504_222710/provenance/`.

**Status:** Answered.

### R1.4 The Scenario A GDP value

**Finding.** −15.7 was never recorded as a model output, and the evidence points to LLM commentary rescaling −0.157.

- **Not in the records.** None of 24,509 JSON state and report files has `gdp_impact_pct` of −15.7.
- **Not in the code.** Three May commits and the working tree all replay to −0.157 from the recorded inputs.
- **It is in the commentary.** May's Stage 5 export says: "The model predicts a 15.7% decline in global GDP" (`data/20260504_222710/qualitative/swift_contained.md:85`, also `cross_scenario.md:464` and `figures/index.html`). The same claim is in reports from three other May runs (`20260504_032106`, `20260524_013035`, `20260525_193731`).
- **The same passage has another error.** It gives "a 6.9% decline in consumption" for a model value of −0.6953.

**What this changes.** The checklist's account of a rerun that corrected a unit error, detected by the consistency pass, is not supported. The consistency module reads model outputs, not commentary, and the model value never changed. The likely account is that an LLM commentary misstated the number and an author caught it.

**What is not proven.** We can show where the number exists, not how it reached the draft.

**Files:** `docs/revision/pycge_swift_contained_replay.md`, `runs/20260504_222710_filled/qualitative_audit_20260504_222710.md`.

**Status:** Evidence complete. **Authors must supply** who noticed it and what changed.

### R1.5 Clean synthesis and runtime

**Definition, as implemented in `src/synthesis/run_health.py`:** a run is clean when (1) the synthesis state was written, (2) every (scenario, section) LLM call completed without an unrecoverable error, (3) no bash-layer failure was recorded for the synthesis stage, and (4) every scenario has at least one completed model and one synthesized outcome.

| Run | Sections failed | Clean |
|---|---|---|
| May | 7 of 30 | No |
| Run A | 10 of 30 | No |
| Deterministic baseline | n/a, templated | Yes |

The May and Run A failures are `LengthFinishReasonError` at the 8,192 token cap. Model numbers are unaffected, but those sections have no outcomes.

**Runtime.** Wall-clock excludes human review, which was not measured because checkpoints were auto-approved (0 seconds recorded). Run A's whole job took 2 h 51 min.

**Checkpoints in batch.** `HORMUZ_AUTO_APPROVE=1` records each checkpoint as approved without analyst input, because a batch job cannot prompt. "No autonomous mode" must be scoped to interactive use. See `checkpoints_in_batch_mode.md`.

**Status:** Answered. The main run being unclean must be stated.

---

## Reviewer 2

### R2.1 Engineering contribution versus workflow systems

**Measured.**

- **What the LLM does:** scenarios, parameter extraction, weekly briefs, prose. **What deterministic code does:** adapters, forwarding, consistency checks, execution.
- **Deterministic baseline:** the same registry with analyst YAML and no LLM completed 90 cells with a clean synthesis, against Run A's 84. Of 1,800 output keys, 344 are identical and 1,215 differ, and 0 of 90 cells share identical inputs. **Output differences therefore trace to inputs**, which is the framework's main argument and also its main risk.
- **Baseline as a check on the LLM:** the baseline's `ais_project` shows +9.5 transit days under E, where the LLM run shows 0.
- **Processing time:** the baseline's stages took about 23 seconds, 20.6 of them model execution. Run A's whole job took 2 h 51 min, including model server start-up and all LLM calls. This excludes the analyst time needed to write the baseline's parameters, which was not measured.
- **Effort:** 34 adapters, 11,130 code lines, 42,388 test lines. Named changes: the infrastructure-collapse scenario (399 lines in 6 files, plus a bulk upload) and the APSIM fertilizer bridge (217 lines in 8 files). Forwarding rules take 7–66 YAML lines per downstream model.

**Files:** `runs/rev_20261102_llama8b_r2/compare_llm_*_vs_baseline_*.md`, `docs/revision/effort_metrics.md`.

**Status:** Partly answered. **Authors to supply:** person-hours and the position against workflow systems (Snakemake, Airflow, CWL, BMI, OpenMI). Phrases such as "costs a weekend" have no measurement behind them and should be qualified.

### R2.2 Identify the models executed

**Finding.** Same inventory as R1.1, with implementation, calibration sources, key equations and limitations per model. Reports mark reductions with † and published-output ingestion with ‡.

**Status:** Answered. Abstract, Fig. 2 and the terminology sweep remain manuscript edits.

### R2.3 Uneven scenario coverage

The cause is R1.2. Filling the cells changes several scenario claims.

**Anchors.** The five anchor models keep their published values, and with the fill 17 models now span all scenarios. Compared with May, Run A's headline MPSGE.jl values move by under 1% and pycge's GDP is identical.

| Output | A | B | C | D | E |
|---|---|---|---|---|---|
| Oil impulse % (Fed oil, forwarded from POLES) | 54.79 | 60.5 | 58.25 | 51.82 | 48.36 |
| GDP % (pycge) | −0.157 | −0.8139 | −0.7889 | −1.0575 | −0.8636 |
| GDP % (MPSGE.jl) | −0.025 | −0.8883 | −0.8695 | −1.4314 | −1.0355 |
| GDP % (NREL) | −0.0407 | −0.4494 | −0.4494 | −0.6599 | −0.5196 |

**Non-monotone oil finding.** It survives the anchor comparison but is not independent evidence. Fed oil's impulse is forwarded from POLES, and the extracted supply loss barely changes across scenarios: 4.38, 4.32, 4.32, 4.30 and 4.20 mb/d. So the differences come mainly from other extracted inputs, such as duration and rerouting. Under E the framework stipulates 4–6 mb/d of Saudi plus 1–2 mb/d of UAE capacity loss, against the 4.2 extracted. Describe this as a property of the extracted inputs and the reduction.

#### Helium and fertilizer

| Output | A | B | C | D | E |
|---|---|---|---|---|---|
| Helium supply gap % | 0 | 0 | 0 | 9.0 | 0.09 |
| Helium price change % | 0 | 0 | 0 | +30 | +0.3 |
| Fertilizer price index % | 0 | +23.76 | +23.76 | +23.76 | +30.32 |

- **Helium.** "Essentially undisrupted" is not a model result. A–C ran on a low-confidence default of 0% ("No information... Defaulting to 0%"), D on 30%, and E on 0.3 for the same stated "30%". Forwarding then replaced the macro models' extracted helium shock of 30 with 0 in A–C, each flagged at 200%. The effect on kernel GDP is small: correcting E moves pycge from −0.8636 to −0.8666.
- **Fertilizer.** "+23.8% wherever resolved" fails for A (0, also from low-confidence defaults) and E (+30.32).

#### Water linkage under Scenario E

The linkage fires, but it does not do what the draft implies.

| Model | Water shock under E | Note |
|---|---|---|
| CWatM | Unmet demand 9.091% | The same as Scenario C |
| MPSGE.jl | Applied, 9.091 | |
| pycge | **Sent but not applied** | Mapping in `pycge.yaml` omits `water` |
| OpenCGE | Sent, model failed | Runtime error in all 5 scenarios |

- **Why 9.091.** `(1.10 − 1.00) / 1.10`. It comes entirely from a low-confidence assumed 10% demand rise. The LLM wrote `damaged`, CWatM reads unknown values as intact, and so destroyed infrastructure contributes nothing.
- **`coverage_facts` overstates this.** Its line that the pycge water shock "was model-computed" describes what was forwarded, not what was used.

**Sensitivity replay, pycge kernel only, not a model result:**

| Case | GDP % |
|---|---|
| Recorded inputs (matches the May run exactly) | −0.8636 |
| Water as forwarded (9.091) | −0.9103 |
| Water with the framework's `severely_damaged` (77.3%) | −1.2606 |
| **Scenario D, recorded** | **−1.0575** |

Correcting the water input alone makes E worse than D, which reverses the published ordering for this kernel.

**Files:** `runs/20260504_222710_filled/scenario_e_input_replay.md`, `docs/revision/anchor_comparison_20260504_222710.md`, `coverage_facts_20260504_222710.md`.

**Status:** Coverage answered. **Scenario claims need the decisions at the top.**

### R2.4 Non-fabrication: enforcement and validation

**Enforcement.** `src/synthesis/fidelity.py` checks every outcome and every prose number against the cited model's outputs. With the validator on, a mismatch is flagged, or blocked, optionally after one re-prompt. May ran without it and Run A with it.

| Synthesis audit | May (no validator) | Run A (validator) |
|---|---|---|
| Outcomes (numeric) | 271 (265) | 296 (259) |
| Value match rate | 0.9585 | 1.0 |
| Strict match rate | 0.9434 | 0.9305 |
| Provenance-complete outcomes | 248 (0.9358) | 241 (0.9305) |
| Prose numbers matched | 376 of 387 | 367 of 371 |
| Unmatched / source not run | 7 / 4 | 0 / 0 |

The strict rate is lower in Run A because 18 outcomes matched a different output of the cited model, so the validator removed unmatched values rather than making everything strict.

| Stage 5 commentary audit (new) | May | Run A |
|---|---|---|
| Numeric tokens | 338 | 551 |
| Exact | 270 | 427 |
| Sign dropped | 23 | 25 |
| Multiplier as percent | 5 | 15 |
| ×100 | 14 | 42 |
| No matching output | 26 | 42 |

Of May's 14 ×100 tokens, 2 are errors, both the 15.7 sentence. The other 12 are shares written as percents or coincidental matches. Run A's 42 and both unmatched sets have **not** been read, and "unmatched" may be a scenario assumption rather than an error.

**Weekly briefs.** Share of substantive numbers found in that week's fetched sources. This is an upper bound: a match means the number appears somewhere in the text, not that it describes the same thing.

| Backend | Batch | Briefs | Found | Rate |
|---|---|---|---|---|
| Sonnet 4.6 | July | 8 | 211 of 219 | 0.964 |
| gpt-oss-120b | July | 6 | 95 of 97 | 0.979 |
| gpt-oss-20b | July | 6 | 59 of 60 | 0.983 |
| Llama 4 Scout | July | 7 | 41 of 41 | 1.0 |
| Opus 4.8 | Rerun | 8 | 170 of 182 | 0.934 |
| gpt-oss-120b | Rerun | 2 | 35 of 37 | 0.946 |
| Qwen3.6 27B | Added | 8 | 236 of 248 | 0.952 |
| Qwen3.8 27B | Added | 8 | 12 of 12 | 1.0 |
| Haiku 4.5 | Added | 1 | 15 of 15 | 1.0 |

**What the claim can honestly be.** No output was found to have been altered in the model records. The LLM did misstate numbers in prose, and it determines model inputs. "Forecloses this structurally" should become a design property plus these measured rates. Input errors found:

| Input | Scenario | Extracted | Problem | Caught downstream? |
|---|---|---|---|---|
| `oil_price_shock_pct` (pycge) | E | 500 | Implausible | Yes, replaced by 48.36 |
| `oil_price_shock_pct` (MPSGE.jl) | C | 0 | Default | Yes, replaced by 58.25, flagged |
| `qatar_helium_supply_loss_pct` | E | 0.3 | Fraction labelled percent | Flagged, but the wrong value won |
| `supply_infrastructure_status` | All | `damaged`, `disrupted`, `partially_disrupted` | Not in vocabulary | Warning only |
| `rerouting_via_cape` | All | false | Assumed at high confidence | **No** |

**The rerouting case shows a gap in the forwarding design.** AIS_project reports a cost multiplier of 1.0 under a closed strait. The current rule averages it with AISdb's 1.1869 to give 1.09345, halving the shock and probably causing most of the 119 small MPSGE.jl differences between May and Run A. The 17.09% gap is under the 30% warning threshold, so nothing flags it. **May is unaffected**, because it used AISdb alone (1.1869).

Backends disagree on this flag. Share of scenario cells with `rerouting_via_cape=true`, pooled across batches:

| Backend | True |
|---|---|
| Sonnet 4.6 | 40 of 40 |
| Haiku 4.5 | 5 of 5 |
| Qwen3.8 27B | 20 of 21 |
| Opus 4.8 | 25 of 30 |
| gpt-oss-120b | 27 of 40 |
| Qwen3.6 27B | 2 of 3 |
| gpt-oss-20b | 11 of 35 |
| Llama 4 Scout | 4 of 35 |
| Llama 3.1 8B on vLLM (May) | 0 of 5 |

**Status:** Answered, with a stronger result than the draft claims and a less flattering one.

### R2.5 Backend comparison

**Why Sonnet showed 18 against 35–39.** (48 × 3) / 8 = 18. In 5 of 8 weeks Sonnet hit the 16,000 token cap, returned 0 scenarios with no parsing error, and was recorded as `ok`. A probe confirmed it: `stop_reason=max_tokens` and 0 scenarios at 16,000, then 5 scenarios at 17,617 tokens with a 32,000 cap. **Sonnet was not slower or less capable.** This contradicts the "no silent omissions" claim and must be disclosed.

**The 35–39 is also too low.** July lost records to the same bug, so 48 is a bookkeeping ceiling: 100 of 170 records per run, with `world_helium_model` surviving only in B and C. On the same grid with the file names fixed, five backends complete 90 models. This difference is code, not backend.

**Denominator.** 34 model specs × 5 scenarios = 170 cells.

| Backend | Group | First batch: recorded ok | First batch: model work | First batch: clean | Now: model work | Now: clean | Principal failure |
|---|---|---|---|---|---|---|---|
| Sonnet 4.6 | Original | 8 | 3 | 3 | 8 | 8 | Silent truncation, fixed |
| gpt-oss-120b | Original | 6 | 6 | 5 | 8 | 7 | JSON generation, fixed on rerun |
| Llama 4 Scout | Retired | 7 | 7 | 6 | 7 | 6 | Brief schema, 1 week |
| gpt-oss-20b | Original | 6 | 6 | 0 | 7 | 0 | Synthesis sections failed in every week |
| Opus 4.8 | Original | 0 | 0 | 0 | 6 | 6 | Temperature deprecated, fixed. 2 weeks omit `scenarios` |
| Llama 3.3 70B | Retired | 0 | 0 | 0 | 0 | 0 | `json_schema` unsupported |
| Llama 3.1 8B Instant | Retired | 0 | 0 | 0 | 0 | 0 | `json_schema` unsupported |
| Qwen3 32B | Retired | 0 | 0 | 0 | 0 | 0 | `json_schema` unsupported |
| Qwen3.8 27B | Added | 8 | 8 | 0 | 8 | 0 | Empty parameter extraction, 0 outcomes |
| Qwen3.6 27B | Added | 1 | 1 | 1 | 1 | 1 | 4 of 5 scenarios (6), parse failure (1) |
| Haiku 4.5 | Added | 1 | 1 | 1 | 1 | 1 | Pseudo-XML in `observed_indicators` (7) |

All counts are out of 8 weeks. "Now" means the latest result per week. Retired backends were not available to rerun (checked 2 November 2026).

**Matched workload.** The checklist's option of a matched rerun is partly met, because the reruns share the 170-cell grid. These are single runs on different weeks, through provider rate limits, and on later code than July.

| Backend | Weeks | Models completed | Parameter LLM time (s) | Total run time (s) | Synthesized outcomes |
|---|---|---|---|---|---|
| gpt-oss-120b | 2 | 90 | 500–525 | 681 | 840–862 |
| gpt-oss-20b | 1 | 90 | 343 | 698 | 659 |
| Qwen3.6 27B | 1 | 81 | 2,892 | 1,428 | 361 |
| Opus 4.8 | 6 | 90 | 1,897–1,999 | 2,227–2,405 | 225–261 |
| Haiku 4.5 | 1 | 90 | 1,740 | 3,339 | 893 |
| Sonnet 4.6 | 5 | 90 | 3,157–3,398 | 4,497–4,718 | 459–508 |

Parameter LLM time sums concurrent calls, so it can exceed total run time. Model execution itself takes under a minute, so **almost all runtime differences are LLM calls.**

**Recommendation.** Retitle as "exploratory end-to-end operating points" and drop "three to four times faster". Sample sizes are too small and uneven for a ranking.

**Checkpoints** were auto-approved in every batch.

**Files:** `runs/backend_status_20261102/backend_status_matrix.md`, `backend_failures.md` in each batch folder.

**Status:** Answered.

---

## Data-integrity checks on the draft

Checklist Section 1, with what the data now shows.

| Draft item | Finding | Action |
|---|---|---|
| "Global" GDP equals ROW | By design. The headline is an OECD/US-calibrated reference economy, not a world aggregate. It matches ROW unless helium or water shocks are present, which explains the D and E mismatches | Relabel. PPP-weighted values for May are below |
| Sharpest C loss is SSA (−1.37%) | Wrong. pycge's sharpest loss is India, −1.6041 (SSA −1.3677, EU −1.3008). MPSGE.jl's is the EU, −1.7942 | Correct the text |
| Scenario A gas +50.93% with no upstream model | LNGST did run in A. May's override shows 50.927 from `lngst`, and only its record was lost | Resolved. State in coverage text |
| Argonne ABM cited as a result source | It never ran in May. The figure in the commentary is World Helium's | Attribute to World Helium |
| SimRLFab and NEMS shown as active | Neither completed in any scenario | Mark in Fig. 2 |
| Energy Flux panel lacks a scenario | Gas power ran in A–D. `energy_flux_lng_profits` never ran | Fix the caption |
| Weekly figure shows 6 of 8 weeks | Missing `gpt-oss-120b` weeks are 2026-03-29 and 2026-04-05, both JSON generation failures. Both now succeed on rerun | Name the weeks |
| Fleet-capacity loss in the weekly figure | July records for `ais_project` survive only in B and C. Values follow LLM inputs: B runs 59.7, 39.7, 29.7, 29.7, 14.7, 0 and C runs 29.7, 0, 29.7, 29.7, 29.7, 9.7 | Define the aggregation. Read the swings as extraction, not shipping dynamics |
| Scenario durations | A reads as 5 days (CWatM), 0.42 months (POLES) and 5 months (World Helium, fertilizer). C's narrative runs 4 months against a "swift" 4–6 weeks, a likely reason B and C are nearly identical | Disclose. The consistency module checks outputs, not inputs |
| APSIM yields | May's fertilizer inputs were 0, so it shows no yield loss. Run A forwards the shock and gives −10.8% in B and −19.2% in C | Do not cite May's APSIM yields as a finding |
| LNG shock differs across CGEs | Under E, MPSGE.jl uses 126.39 (from LNGST) and pycge 40 (LLM), because pycge's rule depends on `energy_flux_lng_profits`, which never ran | Note when comparing the two |
| "Never run unattended" | Batches were auto-approved | Scope the claim |

**PPP-weighted world GDP, May regional rows (IMF WEO 2024 shares, derived arithmetic, not a model output):**

| Model | A | B | C | D | E |
|---|---|---|---|---|---|
| pycge | −0.1672 | −0.8788 | −0.8527 | −1.1469 | −0.9489 |
| MPSGE.jl | −0.0270 | −0.9897 | −0.9701 | −1.6036 | −1.1546 |

---

## Supplementary full-model runs and observed prices (November 2026)

**Status (14 November 2026):** Both runs are complete: run 1 including OpenCGE's corrected re-run, and run 2 (cluster jobs 91910, 92051 and 92052, finished 09:19 UTC). Defects found in the results were fixed for future runs on 13–14 November; the recorded outputs are unchanged ([run 2](#run-2-results-observed-pre-crisis-prices)). Nothing here has had analyst review.

### Fixes behind the runs

May stays the basis of the manuscript. These fixes run only in two new runs that reuse May's saved parameters, with no LLM. New outputs go to `data/outputs_supp/<run_id>/`, so May's and Run A's files are not touched.

| Model | Why it never produced results | Fix |
|---|---|---|
| OpenCGE (OG-Core) | Every run failed OG-Core validation: `Z` sent as a flat list, and a scalar replaced the tax-depreciation rate `delta_tau_annual` | `Z` is now a years × industries list. The capital-quality drag goes on economic depreciation `delta_annual` (baseline + adjustment). The baseline transition path is now required, steady-state outputs are read under OG-Core's actual keys (`Y`, `C`), and the YAML includes the water shock. **Second fix, 13 November:** the productivity shock is weighted by the share of each year the disruption covers, and the depreciation drag, which OG-Core applies permanently, is used only under E (see [OpenCGE](#opencge)) |
| Energy Flux LNG War Profits | The extractor never supplied TTF / JKM / Henry Hub prices | Moved to the downstream tier. The prices are forwarded from LNGST's computed hub prices, and a peak below the workbook's spot start is clamped and recorded |
| SimRLFab | The registry never passed it a configuration | Configuration builder and `simrlfab.yaml` added. Needs a Python 3.6 environment on the cluster |
| MAM | Wrong table and edition (see R1.1) | AEO2025 Table 20 is parsed by series key and year column. A file of the wrong table or edition is rejected. Outputs are flagged `_baseline_only`, and shock inputs are listed as ignored |

- **`supp_full_20260504_222710` (run 1):** literature constants, so only the model fixes differ from May.
- **`supp_full_mkt_20260504_222710` (run 2):** observed pre-crisis prices as baselines (below).

Driver: `slurm/jobs/supplementary_full_models.job`. Seeding: `scripts/revision/prepare_supplementary_run.py`. Report: `runs/supp_full_20260504_222710/` (cluster; regenerated after the OpenCGE re-run, 13 November).

### What we can tell reviewers

Across all result sets, 22 of the 35 adapters produced output:

| Category | Count | Models (result set, scenarios) |
|---|---:|---|
| **Upstream model code executed** | 5 | Energy Flux gas power (May, A–D); Energy Flux LNG profits, SimRLFab, OpenCGE (run 1, A–E); APSIM-GTAP (copies of May and Run A, A–E) |
| **Published baseline ingested** | 1 | MAM: EIA's AEO2025 reference case (run 1, A–E) |
| **Calibrated closed-form approximation** | 16 | 5 mix the named model's published numbers with other literature (fed_oil, world_helium_model, nrel, argonne_abm, cwatm); 11 use other literature only |

Each full model carries a qualification the letter should state:

- **Energy Flux gas power:** the crisis enters only through the build scenario and LNG inputs.
- **Energy Flux LNG profits:** its crisis prices are forwarded from the LNGST approximation, so it is a full model fed by an approximation. Most of its total windfall comes from the workbook's starting prices, so cite the windfall from the scenario's price rise ([LNG profits](#energy-flux-lng-war-profits)).
- **SimRLFab:** scenario differences come almost entirely from the LLM-extracted neon status. The helium channel registers only in D.
- **OpenCGE:** OG-Core has no energy or commodity sector. The shocks enter as a temporary productivity loss through coefficients set in `opencge.yaml` without a cited source, and they make its year-one GDP losses 3–4× the literature-calibrated estimates ([OpenCGE](#opencge)).
- **APSIM-GTAP:** the crop side is an emulator of APSIM maize at one site.

**Suggested wording:** "Five models ran their own code, EIA's macroeconomic module contributes its published baseline, and 16 calibrated closed-form approximations occupy the remaining slots." Do not write "22 models ran".

**Can the approximations count as valid exercises?** Yes, with a precise claim:

- **What they do test.** Each approximation runs in a named model's slot. It gets its inputs through the same extraction, validation and forwarding path as a full model. Its outputs go through the same consistency checks and provenance chain. So they test the framework end to end.
- **Why their numbers are defensible.** They are calibrated to published elasticities. Every one moves monotonically with its own inputs and returns zero at zero shock (295 zero-shock checks and 420 dose ladders, [robustness check 1](#robustness-checks-ported-from-agresilience)). Their scenario orderings hold when the calibration constants are scaled by 0.5–1.5× ([check 2](#robustness-checks-ported-from-agresilience)).
- **They feed the full models.** In run 1 they supply the hub prices behind LNG profits, the helium gap behind SimRLFab and the commodity shocks behind OpenCGE.
- **What they cannot do.** They have none of the named models' structure: no inventories, trade re-allocation or general-equilibrium feedback. Against observed 2026 prices they understate Brent and TTF and get the sign of Henry Hub wrong ([observed data](#observed-market-data)).
- **How to describe them.** "First-order estimates from calibrated closed-form approximations", never results of the named models.

### Run 1 results

**Coverage.** 13 models, each completed in all 5 scenarios (65 of 65 cells):

- Upstream code (3): Energy Flux LNG profits, SimRLFab, OpenCGE.
- Published baseline (1): MAM.
- Closed-form approximations (9): ais_project, aisdb, cwatm, futures, lngst, poles_jrc, weap_mena, world_fertilizer and world_helium_model. These are the upstream sources the full models consume. 2 are mixed and 7 use other literature only.

Energy Flux gas power is not in this run, so its May results (A–D) stand. The stand-ins reproduce May's values: for example, POLES-JRC's Brent and LNGST's hub prices match May in every scenario that May's report contains.

**Extracted durations disagree within a scenario.** Each model's `disruption_duration_months` was extracted separately in May:

| Scenario | Range across models | Models |
|---|---|---|
| A swift contained | 0.08–5 months | 5 for OpenCGE, LNG profits and World Helium; 0.17 for LNGST; 0.08 for SimRLFab |
| E infrastructure collapse | 5–12 months | 5 for OpenCGE, LNGST and World Helium; 9 for SimRLFab; 12 for LNG profits |
| B, C, D | consistent | 4, 4 and 7 months |

So "swift" A is longer than "prolonged" B (4 months) for three models. SimRLFab's 0.08 months is replaced by World Helium's forwarded 5 months. The full models compute faithfully from these inputs, and the letter should say so rather than read A versus B as a duration effect.

#### Energy Flux LNG war profits

US LNG export windfall over the crisis. Peak prices are forwarded from LNGST.

| Scenario | Duration (months) | TTF / JKM / Henry Hub peak (USD/MMBtu) | Peak monthly windfall (USD bn) | Total windfall (USD bn) |
|---|---:|---|---:|---:|
| A | 5 | 16.60 / 18.96 / 3.46 | 2.22 (month 1) | 9.63 |
| B | 4 | 24.90 / 28.44 / 5.19 | 3.94 | 14.27 |
| C | 4 | as B | 3.94 | 14.27 |
| D | 7 | as B | 4.69 | 27.60 |
| E | 12 | as B | 4.69 | 47.91 |

- **B–E differ only by duration.** LNGST gives all four the same hub peaks, so the windfall ranking follows the extracted durations.
- **A was clamped.** A's forwarded TTF and JKM peaks (16.60, 18.96) are below the workbook's spot start (16.98, 21.19). The start was clamped to the peak and recorded in `_schedule_start_clamped`.
- **Observed prices would change the result, in an undetermined direction.** Observed TTF rose more (+174% against +126%) and Henry Hub fell (−35% against +73%), which would both widen the European netback. The Japan LNG proxy rose much less than the model's JKM (+47% against +119%).

**Most of the total is not the scenario's doing.** The workbook measures each month's cargo margin against a fixed pre-crisis reference (a 5.91 USD/MMBtu TTF netback, its September 2025 to March 2026 average). It does not measure against its own starting prices. A path that never moves from its start therefore still reports a windfall. In run 1 the start is the workbook's March 2026 spot (TTF 16.98, Henry Hub 3.04), which was already well above that reference. Subtracting a path with prices and freight held at the start leaves the windfall due to the scenario's rise in prices and freight (`windfall_from_price_rise_usd`; the adapter reports it from 14 November).

| Scenario | Run 1 total | Run 1, prices held at start | Run 1, price rise | Run 2 total | Run 2, prices held at start | Run 2, price rise |
|---|---:|---:|---:|---:|---:|---:|
| A | 9.63 | 11.86 | −2.23 | −5.29 | −8.34 | 3.04 |
| B, C | 14.27 | 11.78 | 2.50 | −0.97 | −6.67 | 5.70 |
| D | 27.60 | 20.61 | 6.99 | 4.28 | −11.67 | 15.96 |
| E | 47.91 | 35.33 | 12.58 | 8.72 | −20.01 | 28.73 |

USD bn. Each cell was re-run from its recorded inputs with the 14 November adapter, which reproduced every recorded total exactly.

- **Run 1:** 74–123% of each total is the start-versus-reference gap. A's price-rise windfall is negative because its forwarded TTF and JKM peaks sit below the workbook's spot, so the clamped schedule has only Henry Hub and freight rising.
- **Run 2** starts from observed pre-crisis prices (TTF 10.42, Henry Hub 4.25). Those sit below the reference, so the totals are negative or small. That mixes two baselines and is not a crisis loss.
- **The price-rise windfall does not depend on the reference**, so cite it. It is larger in run 2 because the climb from observed pre-crisis prices to the same peak is larger.
- **The ordering in both runs is A < B = C < D < E**, set by the extracted durations, since B–E share LNGST's peaks.

#### SimRLFab

Fab simulation; recorded run, seed 10. Overrides are `machine: MTBF/MTOL` in minutes, against defaults of 1000/200.

| Scenario | Episodes | Overrides | Machines broken (share) | Order waiting time |
|---|---:|---|---:|---:|
| A | 50 | none | 0.161 | 356 |
| B, C | 40 | neon m3–m4 700/260 | 0.212 | 399 |
| D | 70 | helium m0–m2 910/218; neon 700/260 | 0.222 | 419 |
| E | 50 | helium m0–m2 999.1/200.18; neon 300/500 | 0.263 | 453 |

**Seed band** (10 seeds, each arm against a paired control with no gas shortfall; effect on machines-broken share, mean ± SE; `runs/supp_full_20260504_222710/simrlfab_seed_band.md`):

| Scenario | Neon only | Helium only | Both |
|---|---|---|---|
| B, C | +0.019 ± 0.008 | no override | +0.019 ± 0.008 |
| D | +0.017 ± 0.007 | +0.010 ± 0.005 (about 2 SE) | +0.022 ± 0.011 (under 2 SE) |
| E | +0.099 ± 0.011 | +0.001 ± 0.001 | +0.100 ± 0.012 |

- **Neon drives the scenario differences.** Neon status is LLM-extracted. The helium gap is computed by World Helium and forwarded.
- **The helium gap is non-zero only in D.** It is 9%, and moves the result by about 2 SE.
- **E's helium gap is 0.09%, not 9%.** World Helium's E input is `qatar_helium_supply_loss_pct = 0.3` at high confidence, the percent-as-fraction error in [failure 9](#what-we-learned-from-the-failures). SimRLFab faithfully runs with almost no helium shock under E.
- **A has no overrides.** Its recorded 0.161 is seed noise around the control mean of 0.181.

#### MAM

All five cells hold the same AEO2025 reference case for 2026: real GDP growth 2.32%, CPI inflation 1.76%, unemployment 4.48%, federal funds rate 2.64%, 10-year Treasury 3.28%. That is EIA's published no-crisis baseline. In ingestion mode MAM ignores the scenario shocks (`_ignored_shock_inputs`), so cite it only as the reference that crisis responses are read against.

#### OpenCGE

US overlapping-generations model (OG-Core 0.15.10), full transition path. Corrected re-run, cluster job 91908, finished on the evening of 13 November. All five cells converged: transition-path distance below 1e-5 after 20–23 iterations, resource-constraint error below 1e-6, and solve times of 5.8–10 hours. Values are percent changes from OG-Core's no-shock baseline; year 1 is 2026.

| Scenario | Duration (months) | Year-one productivity (Z) | GDP, year 1 | Wages, year 1 | Consumption, year 1 | GDP, year 2 | GDP, year 50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5 | 0.9836 | −2.14 | −1.59 | −0.36 | −0.08 | −0.0005 |
| B | 4 | 0.9805 | −2.54 | −1.89 | −0.43 | −0.09 | −0.0006 |
| C | 4 | 0.9811 | −2.46 | −1.83 | −0.42 | −0.09 | −0.0006 |
| D | 7 | 0.9663 | −4.37 | −3.26 | −0.74 | −0.16 | −0.001 |
| E | 5 | 0.9732, plus capital drag | −3.76 | −2.87 | −1.20 | −0.45 | −0.91 |

Commodity shocks received (percent price change, forwarded from the approximations): oil 54.8 / 60.5 / 58.3 / 51.8 / 48.4 from POLES-JRC; LNG −11.5 / 15.0 / 15.0 / 23.4 / 24.5 from Energy Flux LNG profits; fertilizer 0 / 23.8 / 23.8 / 23.8 / 30.3 from World Fertilizer; helium 30 in D, 0.3 in E, 0 otherwise; water 9.1 in E only (A / B / C / D / E).

- **A–D return to baseline.** The productivity loss lasts only for the shock year. GDP is within 0.2% of baseline from year 2 and within 0.001% by year 50, which is what the corrected specification should produce.
- **E's lasting loss comes from an input decision, not a model finding.** The capital drag raises economic depreciation by 0.0039 a year, permanently, and only under E. It lowers steady-state GDP by 0.90% and consumption by 1.46%. Consumption rises 1.7% above baseline in year 2 as households run down capital that now depreciates faster.
- **`welfare_pct_change` is a steady-state consumption proxy.** It is 0 in A–D because a temporary shock does not move the steady state, and −1.47% in E. Do not cite it as "no welfare loss" in A–D.
- **The magnitudes depend on an unsourced coefficient.** OG-Core has no energy sector. Each commodity shock becomes a productivity loss through coefficients in `opencge.yaml` (oil −0.08% of productivity per 1% price rise; LNG −0.04%; fertilizer −0.02%; helium −0.01%; water −0.12%). The file attributes them to "BLS factor-share tables" without a citation. Year-one GDP falls about 1.3× the productivity loss, so a year-long doubling of oil would cut GDP about 10%. Hamilton (2003, 2009) and Kilian (2008) put that at 2–3%, the range the closed-form macro kernel uses.
  - On identical shocks, OpenCGE's year-one losses are 3.3–4.4× the kernel's: A −0.66, B −0.78, C −0.75, D −1.05, E −0.85.
  - They are 3–14× May's PyCGE values: A −0.16, B −0.81, C −0.79, D −1.06, E −0.86.
  - The configured consistency rule (OpenCGE against PyCGE, 10% tolerance) would flag every scenario. It did not fire because run 1 has no PyCGE cell.
  - Scaling all coefficients by one factor scales the losses roughly in proportion and leaves the ordering and the return to baseline unchanged. **Cite the pattern, not the magnitudes**, until the coefficients are sourced or varied.
- **The year-one ordering follows the extracted inputs.** D (7 months, plus a 30% helium shock) loses more than E (5 months) in year 1; E is worse only from year 2, through the drag. A (5 months) loses less than B (4 months) because its oil shock is smaller, it has no fertilizer shock, and its LNG shock is negative.
- **The LNG input was the wrong quantity, in both runs.** The forwarding rule read Energy Flux's average TTF netback and converted it to a price change against a fixed 10.0 USD/MMBtu. A netback is a margin: TTF minus 1.15 × Henry Hub, liquefaction and freight.
  - Run 1 therefore fed +15% (B, C), +23% (D), +25% (E) and −11.5% (A). Over the same period LNGST's TTF rose 126% in B–E and 51% in A.
  - A's negative value raised its year-one productivity to 0.9836, against 0.9817 with no LNG shock at all.
  - Fixed 14 November: the macro models now take LNGST's TTF change (`configs/upstream_forwarding_mapping.yaml`).
  - Correcting the input raises OpenCGE's losses rather than lowering them. With the current coefficients, year-one GDP would be roughly −3.4% (A) to −7.4% (D). **A rerun makes sense only together with sourced coefficients.**
- **The nine-region context table was all zeros (fixed).** Each OpenCGE output also carries a closed-form regional table (`regional_context_vars`). The adapter passed it per-commodity records instead of percents, and the kernel silently dropped them. Every `opencge.regional_context_vars` row in run 1's `regional_outcomes_*.csv` and qualitative reports is 0, so do not cite them. Fixed 13 November (`OpenCGEAdapter._kernel_shocks`, with a test). Run 2's cells started before the fix and will carry the same zeros. OG-Core's own output (`regional_vars`, US only) is unaffected.

**First results withdrawn.** The first run 1 results (archived, not for citation, in `slurm/logs/supp_full_20260504_222710/opencge_v1_fullyear_shock_20261113/` on the cluster) had two specification errors:

1. **Year-one productivity loss overstated.** The full productivity shock was applied to every model year the disruption touched, so a 4-month disruption cut a whole year's `Z`. `Z` is now weighted by the share of each year covered. Year-one multipliers: A 0.9836, B 0.9805, C 0.9811, D 0.9663, E 0.9732.
2. **Capital drag made permanent.** OG-Core applies `delta_annual` as one rate for every year, so the capital-quality drag permanently lowered the steady state in every scenario. It now applies only under E, which stipulates lasting infrastructure damage (author decision, 13 November; `capital_drag_scenarios` in `configs/model_configs/opencge.yaml`). In A–D the economy should return to baseline in the long run.

The re-run used the same inputs. Each output records `_capital_drag_applied` and `_z_path_shock_years`, and the values above match the year-one multipliers listed in point 1.

### Run 2 results (observed pre-crisis prices)

`supp_full_mkt_20260504_222710`: the same 13 models and saved parameters as run 1, with market calibration on. All 65 cells completed. POLES-JRC, LNGST, Energy Flux LNG profits, World Fertilizer and futures record `_calibration.source = market_data@2026-11-08` (World Bank Pink Sheet of 3 November 2026).

**What changed from run 1:**

| Model | Run 1 | Run 2 | Why |
|---|---|---|---|
| POLES-JRC, Brent peak | 119–128 USD/bbl (+48 to +61%) | 99–106 USD/bbl (+55 to +66%) | Baseline 80 → 63.6. The percent rise grows because the rerouting and insurance wedges are fixed dollar amounts |
| LNGST hubs | TTF 24.9, JKM 28.4, Henry Hub 5.19 (B–E) | TTF 23.6, JKM 24.8, Henry Hub 7.35 | Baselines replaced; **percent changes identical** (TTF +126%, JKM +119%, Henry Hub +73% in B–E) |
| World Fertilizer | percent index only | same percent, plus USD levels (urea 409 → 613 in B–D, 669 in E) | Levels added; responses unchanged |
| Energy Flux LNG profits | see [split](#energy-flux-lng-war-profits) | total negative in A–C | Schedule starts at observed pre-crisis prices, below the workbook's reference |
| OpenCGE | year-one GDP −2.1 to −4.4% | −1.2 to −3.0% | LNG input became −30 to −66% (netback error, above), not the oil change |
| futures, SimRLFab, MAM and the other approximations | — | identical | No calibrated constants; SimRLFab reproduced its KPIs exactly, with only the wall-clock time differing |

**Run 2's OpenCGE results should not be cited.** Year-one GDP was A −1.20, B −1.68, C −1.58, D −2.98, E −2.92, and −0.74 in E at year 50. Its oil shocks are 3.5–7.4 points larger than run 1's, yet its losses are smaller. That is because the netback rule turned LNGST's +126% TTF rise into LNG price *falls* of 30–66%.

**Against observed prices** (`runs/supp_full_mkt_20260504_222710/observed_vs_scenario.md`, peak change February to October 2026 against the pre-crisis median):

| Variable | Observed | Run 2 (B–E unless noted) |
|---|---|---|
| Brent | +97% (125 USD) | +55 to +66% (99–106 USD) |
| TTF | +174% | +126% (A +51%) |
| Henry Hub | −35% | +73% (A +15%) |
| Japan LNG (JKM proxy) | +47% | +119% (A +46%) |
| Urea | +109% (April) | +50% (E +64%, A 0) |

Observed baselines fix the price levels but not the modelled responses. The approximations still understate Brent, European gas and urea, overstate the Japan proxy and get Henry Hub's sign wrong. That is a property of their elasticities, which calibration to baseline prices cannot change.

**Defects found in the results and fixed for future runs.** None changes a recorded output:

1. **OpenCGE's regional context table was all zeros** (above). `OpenCGEAdapter._kernel_shocks`.
2. **Macro LNG shocks read Energy Flux's netback.** The rules for OpenCGE, PyCGE, MPSGE.jl, NEMS, MarketSim and NREL now take LNGST's hub price change (`ttf_price_change_pct`, `jkm_price_change_pct`). Only OpenCGE in the two supplementary runs actually received a netback value. In May, LNG profits produced nothing, so those rules fell through to their fallbacks.
3. **LNG profits reported only the reference-dependent total.** It now also reports `windfall_at_flat_start_prices_usd` and `windfall_from_price_rise_usd`.
4. **Run 2's first observed-versus-scenario table** measured LNGST's hubs against the literature baselines (3.0 / 11.0 / 13.0), not the run's own. It showed Henry Hub +145% instead of +73%, TTF +114% instead of +126%, and JKM +90% instead of +119%. It was regenerated on 14 November; the first version is in `observed_vs_scenario_v1_fixed_hub_baselines/`. Run 1's table was unaffected.

### Observed market data

**Source:** `scripts/revision/fetch_market_data.py` downloads the World Bank Pink Sheet (monthly, through October 2026), plus EIA weekly spot prices when `EIA_API_KEY` is set. It writes `data/market/{monthly_prices.csv,calibration.json,provenance.json}`.

**Pre-crisis baselines** (median of November 2025 to January 2026):

| Series | Observed baseline | Adapter constant |
|---|---|---|
| Brent | 63.6 USD/bbl | POLES-JRC: 80 |
| Henry Hub | 4.25 USD/MMBtu | LNGST: 3.0 |
| TTF | 10.42 USD/MMBtu | LNGST: 11.0 |
| Japan LNG (JKM proxy) | 11.32 USD/MMBtu | LNGST: 13.0 |
| Urea | 409 USD/t | (percent changes only) |

The median rather than the mean is used because Henry Hub averaged 7.6 USD/MMBtu in January 2026 alone.

**Half-lives are not applied.** AR(1) estimates on 2000–2025 data give 8–29 months (urea 10.7). That measures persistence of deviations from a 3-year trend. The observed 2026 urea spike (+109% in April) was back to +2.6% by October, consistent with the adapters' 3–5 month spike-decay values. The estimates stay in `calibration.json` for reference (`apply_half_lives: false`).

**Observed versus scenario, May (original report CSV, so some filled cells are absent):** `observed_vs_scenario/observed_vs_scenario.md`.

| Variable | Observed peak vs baseline (Feb–Oct 2026) | May model (scenarios present) |
|---|---|---|
| Brent | +97% (125.0 USD, October) | POLES-JRC slot +55% (A), +58% (C) |
| TTF | +174% (28.5 USD, October) | LNGST slot +126% (B, C) |
| Henry Hub | −35% (2.77 USD, April) | LNGST slot +73% (B, C) |
| Urea | +109% (857 USD/t, April), +2.6% by October | World Fertilizer slot +50% (B, C) |
| Wheat, US HRW | +41% (September) | no model counterpart |

The scenarios are conditional paths and these are monthly averages, so this is a plausibility check, not a forecast test. Two patterns are clear:

- The oil and gas stand-ins understate the observed moves.
- Henry Hub fell during the crisis, which the LNGST approximation cannot produce: it applies a positive pass-through to every hub.

### Draft manuscript paragraph

> The framework integrates 35 model adapters. Across the reported run, a supplementary run from the same saved parameters, and a run that adds one model to copies of the reported state, 22 produced output. Five executed the upstream model's own code: the Energy Flux gas power build-out and LNG war-profits models, the SimRLFab semiconductor fab simulator, the OG-Core overlapping-generations model (OpenCGE), and the AgResilience coupling of GTAP with an APSIM maize emulator. EIA's Macroeconomic Activity Module contributes its published AEO2025 reference case as the no-crisis baseline. The other 16 are closed-form approximations calibrated to published elasticities, each occupying the slot of a named model. Eleven take all their parameters from studies other than the named model, and five combine the named model's published estimates with other literature. Their results are first-order estimates, not outputs of the named models. They exercise extraction, upstream forwarding, consistency checking and provenance end to end, and they supply the inputs that the full models consume. OG-Core, which has no energy sector, receives the commodity shocks as a temporary productivity loss through configured coefficients, so its results show the shape of the macroeconomic response rather than its size. A second supplementary run replaces the approximations' baseline prices with observed pre-crisis World Bank prices. This changes the modelled price levels but not the percentage responses, which remain below the observed rises in Brent, European gas and urea and have the wrong sign for Henry Hub.

[If OpenCGE is rerun with sourced coefficients and the corrected LNG input, replace the sentence on OG-Core with that result.]

---

## APSIM-GTAP and robustness checks (November 2026)

**Status (8 November 2026): all runs finished.** Nothing here has had analyst review. May stays the basis of the manuscript: APSIM-GTAP's cells were added to *copies* of May's and Run A's state, from each run's own saved records, with no LLM call.

### APSIM-GTAP added to the fleet

**What it is.** The coupled model from the AgResilience project, integrated as a 35th adapter `apsim_gtap` (`src/models/fertilizer/apsim_gtap.py`, driver `apsim_gtap_driver.py`):

- **Economy:** AgResilience's Julia GTAPv7 levels model (JuMP/Ipopt; 18 regions × 8 sectors; calibration `shock-repair-v2`, zero-shock residual ≤ 1e-4 %).
- **Crop:** AgResilience's APSIM maize emulator, an MLP trained on APSIM runs (held-out R² 0.997, one Iowa site).
- **Coupling:** a GTAP ↔ crop fixed point. The US chemicals-consumption change sets field nitrogen, the emulator's yield ratio is fed back as a US grain productivity shock, and this repeats until the yield stops changing.

**How the Hormuz shock enters GTAP.** All three shocks are scaled by duration/12, because GTAP is annual. The Gulf sits in GTAP's West Asia composite (`wasia`).

- Lost Gulf chemicals output, from World Fertilizer's Middle East production loss.
- Lost Gulf extraction output, from POLES-JRC's supply loss ÷ 28 mb/d.
- A rerouting wedge on Gulf exports, from AISdb's multiplier × an 8% freight share. AISdb alone, `combine: first`, so AIS_project's 1.0 does not halve it.

The existing `apsim` reduction and the `gtap` stub are unchanged. Status label: Real (config-aware), mode `full_upstream`.

**Runs** (cluster jobs 89179 gate, 89182 fill):

| | May | Run A |
|---|---|---|
| Fill run id | `fill_apsimgtap_20260504_222710` | `fill_apsimgtap_rev_20261102_llama8b_r2` |
| Merged state (cluster) | `data/pipeline_state_may_apsimgtap/` | `data/pipeline_state_runA_apsimgtap/` |
| Report | `runs/20260504_222710_apsimgtap/` | `runs/rev_20261102_llama8b_r2_apsimgtap/` |
| Cells | 5 of 5 completed, converged, zero-shock residual 0.0 | same |

Every input came from the run's own records; no analyst-baseline value was needed (`apsim_gtap_fill_inputs.json`). Run A's inputs are identical to May's, so its outputs are too.

**Results, May** (percent changes against the GTAP baseline, fixed point):

| Scenario | Inputs: fert. loss / oil loss / months | US GDP | Gulf (`wasia`) GDP | US grain price | US maize yield |
|---|---|---|---|---|---|
| A swift contained | 0 % / 4.38 mb/d / 0.42 | +0.000001 | −0.0012 | +0.0003 | −0.000015 |
| B prolonged contained | 30 % / 4.32 / 4.0 | +0.00012 | −0.262 | +0.037 | +0.00002 |
| C swift escalated | 30 % / 4.32 / 4.0 | +0.00012 | −0.262 | +0.037 | +0.00002 |
| D prolonged escalated | 30 % / 4.30 / 7.0 | −0.00016 | −0.385 | +0.058 | +0.00002 |
| E infrastructure collapse | 30 % / 4.20 / 7.0 | −0.00016 | −0.385 | +0.058 | +0.00002 |

**How to read it:**

- **Effects are small** because of the inputs, not the model:
  - Scenario A carries a 0 % fertilizer loss (the extraction problem in [Helium and fertilizer](#helium-and-fertilizer)) and lasts 0.42 months.
  - The other scenarios lose under a fifth of one sector's annual output in one composite region.
- **B equals C and D ≈ E** because their extracted inputs are identical or nearly so. E's Gulf GDP loss is smaller than D's by 0.0007 pp. This is the same input-driven pattern as [decision 1](#decide-before-citing): APSIM-GTAP does not make E worse than D, because the extraction gave E a smaller oil loss than D.
- **The crop channel is flat.** At the default 190 kg N/ha the emulator is on its yield plateau, so a few-percent nitrogen change moves yield by about 1e-5 %. AgResilience's own E8 sweep found the same (≤ 0.0002 % at 190 N; larger only at 35–50 N).
- **GTAP did not solve the analyst baseline's Scenario E** (85 % fertilizer loss, 13.5 mb/d, 12 months, so about half of Gulf extraction output for a full year). The server returned an HTTP error both at that dose and at 1.6×, which is how an Ipopt failure surfaces; the solver log was not kept. The May and Run A inputs are milder and solved.

**For the reviewers:**

- **R1.1 / R2.2:** May now has a second cell type that runs upstream code end to end. Energy Flux gas power was the first. The crop side is an emulator of APSIM, not APSIM itself, so it should be labelled that way.
- **R2.3:** the fertilizer → crop → food-price chain now runs through a general-equilibrium trade model, not only the reduced-form `apsim` → `pycge` path.

### Robustness checks ported from AgResilience

**What was run.** Three AgResilience checks (E0, E9, E3) were added as Stage 7 steps in `scripts/revision/build_all.py`, plus a separate Armington sweep for APSIM-GTAP.

- **Inputs:** the analyst-baseline inputs (`configs/baselines/hormuz_2026_analyst.yaml`), not LLM-extracted ones. The checks therefore test the models and their couplings with the inputs held fixed.
- **Outputs:** `runs/rev_20261102_llama8b_r2_apsimgtap/robustness/` (zero-shock ladder, elasticity LHS, open-loop gap) and `robustness/apsim_gtap_ssa/` (Armington sweep).

**1. Zero-shock residual and dose ladder** (AgResilience E0; `zero_shock_ladder.md`).

- **Method:** each model runs alone, first with every shock input neutral, then with shocks scaled by 0–1.6×.
- **The 16 runnable models other than APSIM-GTAP:** all 295 zero-shock checks pass (|output| ≤ 1e-4), and all 420 dose ladders are monotone with no sign change.
- **APSIM-GTAP:** all 20 zero-shock checks pass. Gulf GDP falls monotonically with dose in every scenario. US GDP is hump-shaped: slightly positive at small doses, negative at larger ones (3 of 16 ladders; a fourth, for maize yield, steps by about 1e-5 %). That is a general-equilibrium property of a ±0.001 % net effect, not a defect, but the sign of APSIM-GTAP's US GDP response should not be cited.
- **For R2.3:** every model moves in one direction as its own inputs grow, so a non-monotone ordering across scenarios, such as May's oil price, comes from the extracted inputs.

**2. Elasticity Latin hypercube** (AgResilience E9; `elasticity_lhs.md`).

- **Method:** 500 seeded draws, each scaling 12 calibration constants by 0.5–1.5×. The constants are macro-kernel oil, LNG and fertilizer elasticities, POLES-JRC demand and supply elasticities, fertilizer pass-throughs, freight elasticity, MPSGE trade-cost pass-through, and the forwarding rule's 0.35 fertilizer-demand elasticity. Every draw reruns the 15-model analytical chain for all five scenarios with forwarding.
- **Controls:** the point control (all factors 1) reproduces the unmodified run, and the constants are restored after the draws.
- **Orderings:** none of the 80 scenario-pair orderings across eight headline outputs falls below 95 % of draws. Every pair shown for PyCGE GDP, POLES-JRC oil price and APSIM yield holds in 100 % of draws.
- **Bands are wide, orderings are not.**
  - PyCGE GDP under E: −5.10 % (p05 −6.80, p95 −3.33).
  - APSIM mean yield under E: −66.9 % (−76.5 to −58.1).
- **What drives the spread:**
  - The oil-to-GDP elasticity for GDP: first-order index S1 0.89 for PyCGE, 0.96 for Fed oil.
  - The Middle East loss-to-nitrogen pass-through for the fertilizer index: S1 0.96.
  - The forwarding elasticity, then that pass-through, for APSIM yield: S1 0.54 and 0.36.

**3. APSIM-GTAP Armington sweep** (`robustness/apsim_gtap_ssa/`, jobs 89189–89190).

- **Method:** AgResilience's E9 design around May's APSIM-GTAP inputs. 100 seeded draws scale ESUBM and ESUBD for chemicals and grains by 0.5–1.5×, with GTAP re-calibrated per draw.
- **Run health:** 100 of 100 draws complete; no failed case, gate failure or non-converged fixed point.
- **Gulf GDP** under E: −0.38 % (p05 −0.57, p95 −0.26). Its orderings, and those of US chemicals consumption and US grain price, hold in 100 % of draws.
- **US GDP:** its sign is not robust (E: −0.00046 to +0.00004), and its orderings against Scenario A hold in only 84–91 % of draws.
- **Dominant elasticity:** chemicals import substitution (ESUBM for `chm`), S1 0.68–0.98 for GDP, chemicals consumption and grain price.

**4. Open loop versus fixed point, and the forwarding barrier** (AgResilience E3; `open_loop_gap.md`).

- **APSIM-GTAP's one-pass vs fixed-point gap is negligible.** US grain price changes by about 2e-5 pp, at most 0.062 % of the one-pass value in B–E. The reason is the flat crop response above, so this does not show that one-pass coupling is safe in general. AgResilience's E3 found a 7× understatement of the grain price effect with a literature-sized crop response.
- **The step 11 forwarding barrier is not cosmetic** (analyst inputs, barrier on vs off). It changes 25 of 40 downstream headline outputs:
  - PyCGE GDP under A: −0.42 % with forwarding vs −0.29 % without (+47 %).
  - MPSGE.jl GDP under E: −7.92 % vs −4.39 % (+81 %).
  - APSIM yield under E: −66.9 % vs −40.5 % (+65 %).
- **For R2.1:** step 11 is what makes downstream results depend on upstream model outputs rather than on extracted guesses.

**Deterministic baseline with APSIM-GTAP.** The analyst baseline was rerun with APSIM-GTAP as `baseline_rev_apsimgtap_q3` (job 91907, quadro2, 13 November; `runs/rev_20261102_llama8b_r2_apsimgtap/baseline_quadro/`). OpenCGE was left out on purpose: it needs more than the executor's 1-hour timeout per scenario, and a timed-out model blocks the executor's pool (see the defects below). That keeps this baseline like-for-like with the earlier `baseline_rev_llama8b`, in which OpenCGE failed immediately.

| Model | `baseline_rev_llama8b` | `baseline_rev_apsimgtap_q3` | Reason |
|---|---|---|---|
| APSIM-GTAP | not in the fleet | 4 of 5 completed; E failed | new model; GTAP does not solve the analyst's Scenario E |
| MAM | 5 skipped | 5 completed | fix from the supplementary workstream |
| SimRLFab | 5 failed | 5 completed | fix from the supplementary workstream |
| **All models** | **90 of 170 completed** | **104 of 170** (OpenCGE's 5 cells not dispatched) | |

No other model changed its completion count. APSIM-GTAP's analyst-input cells give Gulf GDP of −0.19 % (A), −0.53 % (B), −0.25 % (C) and −0.70 % (D), US grain price +0.02 % to +0.10 %, and US GDP within ±0.0012 %. These are larger than in the runs because the analyst's fertilizer losses are 60–80 %, against 0–30 % extracted in May. The comparison with Run A is `compare_llm_rev_20261102_llama8b_r2_vs_baseline_rev_apsimgtap_q3.md`.

Earlier attempts did not finish and are not results:

- `baseline_rev_apsimgtap` (orion): OpenCGE failed on an NVML driver mismatch and MESSAGEix has no JVM.
- `baseline_rev_apsimgtap_q` (job 89217): cancelled because it shared OG-Core's directory with job 89206.
- `baseline_rev_apsimgtap_q2` (job 89283): hit its 12-hour limit after the executor defect below turned four OpenCGE timeouts into 30 more.

> **Caution for the supplementary run.** From 20:52 to 00:10 the cancelled baseline job wrote OG-Core files (`SS_vars.pkl`, `model_params.pkl`) into `data/opencge/baseline/`. Supplementary job 89206 was using the same directory: its first OpenCGE cell (prolonged_escalated) had been in its baseline solve since 19:08. OG-Core reads `SS_vars.pkl` from disk for the transition path, so that cell may have used a steady state written by the other job. The settings stamp is now missing, so later cells will rebuild the baseline. 89206 was later cancelled at 02:40 on 9 November, after 7 h 40 min (not by this workstream). Check, or rerun, its OpenCGE cells before citing any of them. OG-Core's output directories are shared by every job in this checkout, so never run two OpenCGE jobs at once.

**Defects found, existing before this work and not fixed:**

- `src/synthesis/templated.py` lists `price_change_pct` as Argonne ABM's headline, which its analytical path never emits, so templated synthesis shows nothing for Argonne.
- The forwarding rules for MarketSim never fire, because MarketSim runs in the same tier as POLES-JRC.
- **`ModelExecutor` does not stop timed-out models** (`src/models/executor.py`, lines 380–416 and 451–457). The timeout wraps `asyncio.wait_for(loop.run_in_executor(...))`, which stops waiting but leaves the worker thread or process running. With `max_parallel_models=4`, four timeouts fill the pool. The clock also starts at submission, not at start, so a model that never ran is recorded as `failed: Execution timed out after 3600s`. Job 89283 shows both: OpenCGE timed out in A–D, and from then on 30 models, including millisecond-scale ones such as `aisdb`, were recorded as timeouts, four per hour, until the 12-hour limit. The cited runs are not affected: May and Run A ran each cell as its own SLURM task through `run_model.py`, and the earlier baseline had no model that ran past the timeout.

---

## Disclosures for the rebuttal

1. **Records lost** to a file-naming bug in May and July. 60 May cells re-executed from saved parameters, and 10 cells never ran in May.
2. **Re-executed cells used current adapter code**, and May's synthesis did not see them.
3. **Sonnet's 5 empty weeks** were recorded as `ok`, contradicting "no silent omissions".
4. **The main run is not a clean synthesis** by the paper's definition (7 of 30 sections failed), and neither is Run A (10 of 30).
5. **Checkpoints were auto-approved** in all batch runs, so flags went unread and "approved" in traces does not mean human review.
6. **Reruns are not like-for-like with July:** later code, higher caps, and temperature omitted for Opus. Each record in `runs.json` lists its overrides.
7. **Four Groq models were retired** and 25 failed runs cannot be retried. Added backends are separate and labelled, not substitutes.
8. **The code that produced July's results is not in the current tree.** An upload on 1 November replaced 117 of 118 source files, and neither copy is a working git repository. **Code Availability and the Zenodo release need a reconciled tree.**
9. **Saved `config.llm` is wrong for July runs:** it records the cluster default. Tables use `--backend-map`, and API hosts in the logs confirm the real backends.
10. **Environment change:** `sympy` went from 1.12.1 to 1.13.3 so vLLM could start. Freezes are in `slurm/logs/env_change_20261102/`. `cge_modeling` does not import, so pycge stays analytical (†).
11. **MAM produced no macro data in any run.** Run A's cells were skipped because `mam.yaml` lacked the AEO path. May's cells were marked completed but ingested AEO2021 Table 19 (CO2 emissions) from a legacy EIA URL. The `mam` oil price path in May's synthesis is POLES-JRC's. Fixed on 8 November 2026 (AEO2025 Table 20, table and edition checked on load); the corrected MAM runs only in the supplementary runs.
12. **Known defects left unfixed** to keep May as the basis: the water omission in `pycge.yaml`, CWatM's unenforced vocabulary, no validator on Stage 5 commentary, and the shipping average.
13. **APSIM-GTAP was added after May** and ran only on copies of May's and Run A's state. May's synthesis never saw it. Its crop side is an emulator of APSIM maize at one site, and GTAP is solved annually, so shocks shorter than a year are scaled by duration/12.
14. **The robustness checks hold inputs fixed** at the analyst baseline. They test the models and couplings, not the LLM's extraction.
15. **OpenCGE's first supplementary results were withdrawn** on 13 November. They applied the full productivity shock to every year the disruption touched, and a permanent depreciation drag in every scenario. The corrected cells re-ran from the same inputs, and the first version is archived and marked not for citation.
16. **Extracted durations disagree across models within a scenario.** Under A they range from 0.08 to 5 months, and under E from 5 to 12. For three models "swift" A (5 months) is longer than "prolonged" B (4). The full models inherit these inputs unchanged.
17. **Full models fed by approximations.** Energy Flux LNG profits takes its crisis prices from the LNGST approximation, and SimRLFab its helium gap from the World Helium approximation. OpenCGE's commodity shocks come from approximations too.
18. **OpenCGE's shock coefficients are unsourced.** They make its year-one GDP losses 3–4× the literature-calibrated estimates on the same shocks. The configured OpenCGE–PyCGE consistency rule would flag every scenario, but run 1 had no PyCGE cell, so no flag was raised. Its permanent loss under E comes from the capital drag the authors chose for E.
19. **OpenCGE's LNG input was a netback, not a price,** in both supplementary runs. It received +15 to +25% (−11.5% in A) in run 1 and −30 to −66% in run 2, while LNGST's TTF rose 51–126%. Fixed for future runs on 14 November.
20. **Energy Flux LNG profits' total windfall depends on its reference.** It is measured against the workbook's fixed pre-crisis margin, so 74–123% of run 1's totals comes from its March 2026 starting prices, and run 2's totals are negative. The windfall from the scenario's price rise does not depend on the reference: −2.2 bn (A) to 12.6 bn in run 1, and 3.0–28.7 bn in run 2.

---

## Open items only the authors can fill

- [ ] **R1.4:** how −15.7 reached the draft, who noticed it, and what changed.
- [ ] **R2.1:** person-hours per adapter, and the position against workflow systems and coupling standards.
- [ ] **R2.1:** who wrote `configs/baselines/hormuz_2026_analyst.yaml`. The checklist asks for analyst-authored parameters, so this matters for how the baseline is described.
- [ ] **Scenario E:** the decision in [Decide before citing](#decide-before-citing).
- [ ] **Post-hoc review:** read the scenarios, parameters and synthesis before citing, since no human checkpoint ran.
- [ ] **Read** Run A's 42 ×100 tokens and both runs' unmatched tokens, if Run A's commentary will be cited.
- [ ] **Supplementary runs:** both complete. Read and approve the results and the draft paragraph in [Supplementary full-model runs](#supplementary-full-model-runs-and-observed-prices-november-2026) before citing.
- [ ] **OpenCGE coefficients:** source the commodity-to-productivity coefficients in `opencge.yaml`, or present them as an assumption and report OpenCGE's pattern only.
  - Literature-matched values, as used by the closed-form kernel and divided by OG-Core's ratio of about 1.3 between GDP and productivity: oil −0.00019, LNG −0.00006, fertilizer −0.00004, water −0.00008 and helium about −0.000002 per 1%. The current values are 4–65× these.
  - Matching the kernel makes the OpenCGE–PyCGE agreement true by construction. OG-Core would then add the dynamics, not an independent estimate of size.
  - A rerun of the five cells, with the corrected LNG input, is one overnight array.
- [ ] **LNG profits in the draft:** cite `windfall_from_price_rise_usd` (decomposition table), not the total.
- [ ] **US gas price in the macro rules:** NEMS, MarketSim and NREL take the TTF change for US natural gas. Henry Hub is the US price, but LNGST gets its sign wrong (+73% against an observed −35%). Decide which hub before those models are cited.
- [ ] **OpenCGE regional context zeros:** recompute `regional_context_vars` from each cell's recorded shocks for both supplementary runs, or drop the table from their reports.
- [ ] **Durations:** decide whether to disclose the within-scenario duration disagreement (disclosure 16) or re-extract durations. Re-extracting would break the light-touch decision.
- [ ] **APSIM-GTAP modelling choices:** annual scaling by duration/12, the 8 % freight share, applying the fertilizer loss to all of West Asia's chemicals sector, and the 190 kg N baseline that puts the emulator on its yield plateau. Confirm or change these before citing APSIM-GTAP numbers.
- [ ] **MAM in the draft:** remove any statement that cites MAM output from May, including the oil path shown under `mam`.

**Not determined:** why Qwen3.8 returned empty parameter sets. Also, the 4-of-5 explanation for Qwen3.6 rests on one probe, because failed runs did not save their partial replies.

---

## Regenerating the results

Run on the cluster from the repository root. Comparison scripts and `configs/model_comparison.yaml` exist only there.

```bash
# Backend tables and failure reports, CPU only
sbatch --exclude=orion,tesla1,tesla2,h100 slurm/logs/saved_analysis2_20261102.sh

# Stage 5 commentary audit, filled inventory, search for -15.7
sbatch --exclude=orion,tesla1,tesla2,h100 slurm/logs/saved_analysis3_20261103.sh

# Scenario E sensitivity replay, no cluster needed
python scripts/revision/replay_scenario_e_inputs.py --out-dir docs/revision/runs/20260504_222710_filled
```

Never rerun post-processing or recovery on the May run: it overwrites the original `csv/` and `qualitative/` files on the cluster. The originals are kept at `data/20260504_222710/`.

New scripts for this revision: `scripts/revision/backend_failures.py`, `backend_status_matrix.py`, `audit_weekly_briefs.py`, `audit_qualitative_export.py`, `replay_scenario_e_inputs.py`, `merge_refilled_cells.py`, `rerun_failed_backend_runs.py`. Tests are in `tests/test_revision/`.
