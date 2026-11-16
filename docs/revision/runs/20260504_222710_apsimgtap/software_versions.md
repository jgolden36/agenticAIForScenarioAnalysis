# Software versions

Collected 2026-11-08T18:36:54.958687+00:00 at commit `None` (branch `None`, describe `None`) on Python 3.11.15 (Linux-6.8.0-138-generic-x86_64-with-glibc2.39).

## Python packages

| package | this environment | cluster pip freeze |
|---|---|---|
| langchain | 1.2.15 | 1.2.15 |
| langchain-core | 1.4.8 | 1.4.8 |
| langgraph | 1.1.8 | 1.1.8 |
| pydantic | 2.13.3 | 2.13.3 |
| pyyaml | 6.0.3 | 6.0.3 |
| numpy | 1.26.4 | 1.26.4 |
| pandas | 3.0.2 | 3.0.2 |
| openpyxl | 3.1.5 | 3.1.5 |
| matplotlib | 3.10.8 | 3.10.8 |
| requests | 2.33.1 | 2.33.1 |
| wandb | 0.26.1 | 0.26.1 |
| tiktoken | 0.12.0 | 0.12.0 |
| juliacall | - | - |
| gamsapi | - | - |
| ogcore | 0.15.10 | 0.15.10 |
| ogusa | - | - |
| cge-modeling | 0.0.6 | 0.0.6 |
| otoole | 1.1.5 | 1.1.5 |
| message-ix | 3.11.1 | - |
| ixmp | 3.11.1 | 3.11.1 |
| pyomo | 6.10.0 | 6.10.0 |
| xlwings | - | - |
| rpy2 | - | - |
| netCDF4 | - | - |
| xarray | 2026.4.0 | 2026.4.0 |
| pytest | 9.0.3 | 9.0.3 |

## Runtime inventories (per node, from the SLURM sidecars)

| run | stage | host | gpu | conda env | python | gams | julia | R | java | cuda |
|---|---|---|---|---|---|---|---|---|---|---|
| 20260504_222710 | stonybrook_ai_cluster_revision_setup | ai01 | no | hormuz | Python 3.11.15 | missing | julia version 1.12.6 | missing | missing | missing |
| 20260504_222710 | stonybrook_ai_cluster_revision_setup | ai01 | no | hormuz | Python 3.11.15 | missing | julia version 1.12.6 (juliaup) | missing | missing | missing |
| 20260504_222710 | stonybrook_ai_cluster_setup | ai04 | yes | hormuz | Python 3.11.15 | missing | missing | missing | missing | nvcc: NVIDIA (R) Cuda compiler driver |

## LLM backends per run

| run | provider | model | base url | temperature | state file |
|---|---|---|---|---|---|
| 20260504_222710 | vllm | meta-llama/Llama-3.1-8B-Instruct | - | 0.0 | found |
