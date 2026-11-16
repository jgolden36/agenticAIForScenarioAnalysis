# Analyst checkpoints in batch runs

Algorithm 1 has three mandatory analyst checkpoints (after scenario generation, after parameter extraction, after synthesis). The SLURM drivers export `HORMUZ_AUTO_APPROVE=1` because a batch job cannot prompt, so each checkpoint is recorded as approved without analyst input and the review happens post hoc on the saved state. The table is generated from the run state files by `scripts/revision/checkpoint_report.py`.

| run | backend | auto-approve | scenarios validated | parameter sets by validation status | synthesis validated | analyst review seconds |
|---|---|---|---|---|---|---|
| `rev_20261102_llama8b_r2` | meta-llama/Llama-3.1-8B-Instruct | True | True | approved: 169, pending: 1 | True | 0.0 |

`?` or `None` means the corresponding state file (`<run_id>_scenarios.json`, `<run_id>_params_*.json`) was not available in the state directory given to the script, so the field could not be read; the synthesis column comes from the report copy of `synthesis.json` in that case.
