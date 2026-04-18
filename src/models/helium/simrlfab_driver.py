"""Standalone driver for SimRLFab, invoked by SimRLFabAdapter via subprocess.

This script is *not* imported by the orchestration pipeline. It runs in an
isolated Python environment that has SimRLFab's pinned dependencies
installed (simpy==4.0, tensorforce==0.5.4, numpy==1.17, pandas==1.0.3,
progressbar2==3.51.3 — typically Python 3.6 in a dedicated venv).

The driver:

1. Reads ``inputs.json`` (written by SimRLFabAdapter.translate_inputs_to_dict).
2. Inserts the SimRLFab repo on ``sys.path`` and chdirs into it (SimRLFab
   uses relative paths for its log directory).
3. Monkey-patches ``production.envs.initialize_env.extend_production_parameters``
   and ``extend_agent_parameters`` so that scenario-specific overrides
   (per-machine MTBF / MTOL, per-source MTOG, agent type) are applied
   without touching the upstream SimRLFab source files.
4. Runs the simulation through the Tensorforce ``Runner``.
5. Reads back SimRLFab's KPI log file (``*_kpi_log.txt``) and writes a
   summary JSON to ``outputs.json``.

The driver intentionally has no dependency on the orchestration pipeline so
it can be vendored next to the SimRLFab repo if desired.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SimRLFab subprocess driver.")
    parser.add_argument("--input", required=True, help="Path to inputs.json")
    parser.add_argument("--output", required=True, help="Path to outputs.json")
    parser.add_argument(
        "--simrlfab-path",
        required=True,
        help="Path to SimRLFab repository root (containing run.py)",
    )
    parser.add_argument(
        "--run-dir",
        required=False,
        default=None,
        help="Per-run scratch directory (informational; not currently used)",
    )
    return parser.parse_args()


def _install_overrides(overrides, agent_type, agent_config_path):
    """Monkey-patch SimRLFab's parameter initialization.

    Applies the parameter overrides described in ``overrides`` to every
    SimRLFab simulation created inside this process. Must be called before
    ``ProductionEnv`` is instantiated.
    """
    from production.envs import initialize_env as ie

    original_extend = ie.extend_production_parameters
    original_extend_agent = ie.extend_agent_parameters

    machine_mtbf_overrides = {
        int(k): float(v) for k, v in overrides.get("machine_mtbf_overrides", {}).items()
    }
    machine_mtol_overrides = {
        int(k): float(v) for k, v in overrides.get("machine_mtol_overrides", {}).items()
    }
    mtog_per_source = overrides.get("mtog_per_source")

    def patched_extend(parameters):
        original_extend(parameters)

        if mtog_per_source is not None:
            parameters["MTOG"] = [float(mtog_per_source)] * parameters["NUM_SOURCES"]

        for idx, mtbf in machine_mtbf_overrides.items():
            if 0 <= idx < parameters["NUM_MACHINES"]:
                parameters["MTBF"][idx] = mtbf
        for idx, mtol in machine_mtol_overrides.items():
            if 0 <= idx < parameters["NUM_MACHINES"]:
                parameters["MTOL"][idx] = mtol

        return parameters

    def patched_extend_agent(parameters):
        original_extend_agent(parameters)
        parameters["TRANSP_AGENT_TYPE"] = agent_type
        if agent_config_path:
            parameters["TRANSP_AGENT_CONFIG_PATH"] = agent_config_path
        return parameters

    ie.extend_production_parameters = patched_extend
    ie.extend_agent_parameters = patched_extend_agent

    return {
        "machine_mtbf_overrides": machine_mtbf_overrides,
        "machine_mtol_overrides": machine_mtol_overrides,
        "mtog_per_source": mtog_per_source,
        "agent_type": agent_type,
        "agent_config_path": agent_config_path,
    }


def _resolve_agent_config(agent_type, agent_config_path, simrlfab_path):
    """Pick the Tensorforce agent config JSON.

    For RL agent types ('PPO', 'TRPO') the user can supply a path; otherwise
    we fall back to the bundled ``config/ppo1.json`` or ``config/trpo1.json``.
    For heuristic agents we still need *some* Tensorforce agent so that the
    Runner can pump the simulation, but the action it produces is overridden
    by the heuristic in ``transport.py`` (see SimRLFab's design).
    """
    if agent_config_path and os.path.exists(agent_config_path):
        return agent_config_path

    upper = agent_type.upper()
    if upper == "TRPO":
        candidate = os.path.join(simrlfab_path, "config", "trpo1.json")
    else:
        candidate = os.path.join(simrlfab_path, "config", "ppo1.json")
    if os.path.exists(candidate):
        return candidate
    return None


def _run_simulation(episodes, timesteps, agent_config_path):
    """Drive one SimRLFab training/evaluation run."""
    from tensorforce.environments import Environment
    from tensorforce.execution import Runner

    environment = Environment.create(
        environment="production.envs.ProductionEnv",
        max_episode_timesteps=timesteps,
    )
    runner = Runner(agent=agent_config_path, environment=environment)

    # SimRLFab's ProductionEnv expects a reference to the agent.
    environment.environment.agents = runner.agent

    runner.run(num_episodes=episodes)

    inner_env = environment.environment
    inner_env.statistics["time_end"] = inner_env.env.now

    from logger import export_statistics_logging

    try:
        export_statistics_logging(
            statistics=inner_env.statistics,
            parameters=inner_env.parameters,
            resources=inner_env.resources,
        )
    except Exception:
        # Logger writes a number of optional summary files; if any of them
        # fail (e.g., zero finished orders → division by zero in the order
        # cycle time print) we still want to surface what we have.
        pass

    return inner_env.parameters


def _read_kpi_log(parameters):
    """Parse SimRLFab's KPI log file produced by export_statistics_logging."""
    path_time = parameters.get("PATH_TIME")
    if not path_time:
        return {}, []

    kpi_path = path_time + "_kpi_log.txt"
    episode_log_path = path_time + "_episode_log.txt"

    kpis = {}
    if os.path.exists(kpi_path):
        try:
            import pandas as pd
            df = pd.read_csv(kpi_path, sep=",", header=None, index_col=0)
            kpis = {str(k): _coerce_scalar(v) for k, v in df.iloc[:, 0].to_dict().items()}
        except Exception as exc:  # pragma: no cover - defensive
            kpis = {"_kpi_parse_error": repr(exc)}

    episodes = []
    if os.path.exists(episode_log_path):
        try:
            import pandas as pd
            ep_df = pd.read_csv(episode_log_path, sep=",")
            episodes = ep_df.to_dict(orient="records")
        except Exception as exc:  # pragma: no cover - defensive
            episodes = [{"_episode_parse_error": repr(exc)}]

    return kpis, episodes


def _coerce_scalar(value):
    try:
        f = float(value)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return value


def main() -> int:
    args = _parse_args()

    with open(args.input, "r") as fh:
        config = json.load(fh)

    episodes = int(config.get("episodes", 50))
    timesteps = int(config.get("timesteps_per_episode", 100))
    agent_type = str(config.get("agent_type", "FIFO")).upper()
    agent_config_path = config.get("agent_config_path")
    overrides = config.get("simrlfab_overrides", {})

    simrlfab_path = os.path.abspath(args.simrlfab_path)
    if simrlfab_path not in sys.path:
        sys.path.insert(0, simrlfab_path)

    # SimRLFab writes its log files to a relative ``log/`` directory;
    # changing directory keeps that contained inside the SimRLFab tree.
    original_cwd = os.getcwd()
    os.chdir(simrlfab_path)

    started_at = datetime.utcnow().isoformat() + "Z"
    status = "ok"
    error_message = None
    parameters = {}
    kpis: dict = {}
    episode_log: list = []
    applied_overrides: dict = {}

    try:
        applied_overrides = _install_overrides(overrides, agent_type, agent_config_path)
        resolved_agent_config = _resolve_agent_config(
            agent_type, agent_config_path, simrlfab_path
        )
        if resolved_agent_config is None:
            raise RuntimeError(
                "Could not resolve a Tensorforce agent config JSON. "
                "Provide agent_config_path in SimRLFabConfig or ensure "
                "config/ppo1.json (or trpo1.json) exists in the SimRLFab repo."
            )
        applied_overrides["resolved_agent_config_path"] = resolved_agent_config

        parameters = _run_simulation(episodes, timesteps, resolved_agent_config)
        kpis, episode_log = _read_kpi_log(parameters)
    except Exception as exc:
        status = "failed"
        error_message = "{}: {}".format(type(exc).__name__, exc)
        traceback.print_exc()
    finally:
        os.chdir(original_cwd)

    output = {
        "status": status,
        "error": error_message,
        "metadata": {
            "started_at": started_at,
            "ended_at": datetime.utcnow().isoformat() + "Z",
            "episodes_requested": episodes,
            "timesteps_per_episode": timesteps,
            "agent_type": agent_type,
            "simrlfab_path": simrlfab_path,
            "log_path_prefix": parameters.get("PATH_TIME") if parameters else None,
        },
        "applied_overrides": applied_overrides,
        "kpis": kpis,
        "episode_log": episode_log,
    }

    with open(args.output, "w") as fh:
        json.dump(output, fh, default=str, indent=2)

    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
