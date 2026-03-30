"""GAMS adapter base class for optimization and partial equilibrium models.

Supports both the Control API (GamsWorkspace → GamsJob → .run()) and the
Transfer API (Container for high-performance DataFrame-based data exchange).

Applies to: World Fertilizer Model, POLES-JRC, GGM, CAPRI, MAgPIE, SIMPLE-G.
"""

from __future__ import annotations

import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.base import ModelAdapter, ModelOutput


class GAMSConfig(BaseModel):
    """Configuration for GAMS-based model adapters."""

    gams_system_dir: Path = Field(
        description="Path to GAMS system directory (e.g., /opt/gams/46.1.0)"
    )
    model_gms_path: Path = Field(
        description="Path to the main .gms model file"
    )
    solver: str = Field(
        default="CONOPT",
        description="GAMS solver to use (CONOPT for nonlinear, CPLEX for LP/MIP)",
    )
    timeout_seconds: int = 3600
    working_directory: Path | None = None
    extra_defines: dict[str, str] = Field(
        default_factory=dict,
        description="Additional GAMS defines to pass via options",
    )

    # Acceptable model status codes (1=optimal, 2=locally optimal)
    acceptable_model_statuses: list[int] = Field(default=[1, 2])


class GAMSAdapter(ModelAdapter):
    """Base class for GAMS-based model adapters.

    Subclasses implement:
    - populate_database(): inject scenario parameters into a GamsDatabase
    - extract_results(): read results from the output database
    - validate_inputs(): check parameter validity

    The execute() method handles workspace creation, job execution,
    convergence checking, and error capture.

    IMPORTANT: GamsWorkspace objects are NOT thread-safe. Each execution
    uses a separate working directory for isolation.
    """

    def __init__(self, config: GAMSConfig | None = None) -> None:
        self._config = config

    @property
    def gams_config(self) -> GAMSConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires a GAMSConfig. "
                "Pass it via __init__ or override gams_config."
            )
        return self._config

    def _get_run_dir(self, scenario_id: str) -> Path:
        """Create an isolated working directory (thread safety requirement)."""
        run_dir = Path(
            tempfile.mkdtemp(prefix=f"{self.model_id}_{scenario_id}_")
        )
        return run_dir

    @abstractmethod
    def populate_database(self, db: Any, params: dict[str, Any]) -> None:
        """Inject scenario parameters into a GamsDatabase object.

        Args:
            db: A gams.GamsDatabase instance.
            params: Validated parameter dictionary.
        """

    @abstractmethod
    def extract_results(self, out_db: Any) -> dict[str, Any]:
        """Extract results from the GAMS output database.

        Args:
            out_db: The output GamsDatabase from job execution.

        Returns:
            Dict of result variable name -> value.
        """

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the GAMS model with scenario parameters.

        Creates an isolated workspace, injects parameters, runs the job,
        checks convergence status, and extracts results.
        """
        try:
            from gams import GamsWorkspace
        except ImportError:
            raise ImportError(
                "gamsapi is not installed. Install with: pip install gamsapi[transfer]\n"
                "Note: gamsapi version must match the installed GAMS system version."
            )

        config = self.gams_config
        scenario_id = inputs.get("scenario_id", "default") if isinstance(inputs, dict) else "default"
        run_dir = self._get_run_dir(scenario_id)

        ws = GamsWorkspace(
            working_directory=str(run_dir),
            system_directory=str(config.gams_system_dir),
        )

        # Create in-memory database for shock parameters
        db = ws.add_database()
        self.populate_database(db, inputs)

        # Configure and execute
        job = ws.add_job_from_file(str(config.model_gms_path))
        opt = ws.add_options()
        opt.defines["solver"] = config.solver
        for key, val in config.extra_defines.items():
            opt.defines[key] = val

        job.run(gams_options=opt, databases=db)

        # Check convergence
        model_status = job.out_db.get_model_status()
        solve_status = job.out_db.get_solve_status() if hasattr(job.out_db, "get_solve_status") else None

        convergence = "optimal" if model_status in config.acceptable_model_statuses else "failed"

        if convergence == "failed":
            # Capture the listing file for diagnostics
            lst_files = list(run_dir.glob("*.lst"))
            lst_content = ""
            if lst_files:
                lst_content = lst_files[0].read_text()[-3000:]

            raise RuntimeError(
                f"GAMS model {self.model_id} did not converge. "
                f"Model status: {model_status}, Solve status: {solve_status}. "
                f"Listing file tail:\n{lst_content}"
            )

        # Extract results
        results = self.extract_results(job.out_db)

        return ModelOutput(
            model_id=self.model_id,
            outputs=results,
            convergence_status=convergence,
            metadata={
                "model_status": model_status,
                "run_dir": str(run_dir),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
