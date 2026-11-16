"""SimRLFab is built from simrlfab.yaml with absolute paths.

Before this builder existed the registry instantiated a bare
``SimRLFabAdapter()``, so every run failed with "translate_inputs_to_dict
requires a SimRLFabConfig".
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

from src.models.registry import _build_simrlfab_adapter, build_default_registry


def _write(tmp_path: Path, body: dict) -> Path:
    (tmp_path / "simrlfab.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


def test_no_yaml_gives_bare_adapter(tmp_path):
    a = _build_simrlfab_adapter(tmp_path)
    assert a._sim_config is None


def test_paths_are_made_absolute(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "config" / "ppo1.json").write_text("{}")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HORMUZ_SIMRLFAB_PYTHON", raising=False)
    cfg_dir = _write(tmp_path, {"simrlfab_repo_path": "repo", "python_executable": "env/bin/python",
                                "agent_type": "FIFO", "episodes": 5})
    a = _build_simrlfab_adapter(cfg_dir)
    cfg = a._sim_config
    assert cfg.simrlfab_repo_path.is_absolute() and cfg.simrlfab_repo_path == repo.resolve()
    assert Path(cfg.python_executable).is_absolute()
    assert cfg.episodes == 5


def test_bare_interpreter_name_is_kept(tmp_path, monkeypatch):
    monkeypatch.delenv("HORMUZ_SIMRLFAB_PYTHON", raising=False)
    cfg_dir = _write(tmp_path, {"simrlfab_repo_path": str(tmp_path), "python_executable": "python3.6"})
    assert _build_simrlfab_adapter(cfg_dir)._sim_config.python_executable == "python3.6"


def test_env_var_overrides_interpreter(tmp_path, monkeypatch):
    monkeypatch.setenv("HORMUZ_SIMRLFAB_PYTHON", str(tmp_path / "py36" / "python"))
    cfg_dir = _write(tmp_path, {"simrlfab_repo_path": str(tmp_path), "python_executable": "python"})
    assert _build_simrlfab_adapter(cfg_dir)._sim_config.python_executable == str(
        (tmp_path / "py36" / "python").resolve()
    )


def test_default_registry_uses_shipped_yaml():
    reg = build_default_registry(Path("configs/model_configs"))
    assert reg.get("simrlfab")._sim_config is not None


def test_driver_has_no_python37_only_future_import():
    src = Path("src/models/helium/simrlfab_driver.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            assert all(alias.name != "annotations" for alias in node.names)


_EPISODES = [
    {"episode_counter": 1, "machines_working": 0.8, "machines_broken": 0.0, "machines_idle": 0.2,
     "finished_orders": 16, "processed_orders": 16.0, "order_waiting_time": 46.0, "alpha": 0.37, "inventory": 25.0},
    {"episode_counter": 2, "machines_working": 0.6, "machines_broken": 0.1, "machines_idle": 0.3,
     "finished_orders": 12, "processed_orders": 12.0, "order_waiting_time": 50.0, "alpha": 0.40, "inventory": 27.0},
]


def test_headline_kpis_come_from_the_episode_log_when_driver_kpis_are_empty():
    from src.models.helium.simrlfab import SimRLFabAdapter

    raw = {"status": "ok", "kpis": {}, "applied_overrides": {}, "metadata": {}, "episode_log": _EPISODES}
    o = SimRLFabAdapter().parse_outputs(raw).outputs
    assert o["machines_working"] == 0.7
    assert o["machines_broken"] == 0.05
    assert o["finished_orders"] == 14.0
    assert o["n_episodes"] == 2 and o["_kpi_source"] == "episode_log_mean"


def test_driver_kpis_and_episode_log_give_the_same_keys():
    """Cluster run supp_full_20260504_222710: the driver returned averaged KPIs."""
    from src.models.helium.simrlfab import SimRLFabAdapter
    from src.synthesis.templated import HEADLINE_KEYS

    raw = {"status": "ok", "applied_overrides": {}, "metadata": {}, "episode_log": _EPISODES,
           "kpis": {"machines_working": 0.83, "machines_broken": 0.16, "finished_orders": 50.5,
                    "order_waiting_time": 356.2, "alpha": 0.10}}
    o = SimRLFabAdapter().parse_outputs(raw).outputs
    assert o["_kpi_source"] == "driver_kpis" and o["machines_working"] == 0.83
    assert all(k in o for k in HEADLINE_KEYS["simrlfab"])
