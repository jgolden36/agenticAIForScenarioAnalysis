"""Excel adapter base class for spreadsheet-based models.

Supports two modes:
- openpyxl: headless, no recalculation (reads cached values only)
- xlwings: full recalculation via Excel engine (requires Excel installed)

Applies to: LNGST, MarketSim, Energy Flux models.
"""

from __future__ import annotations

import shutil
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.base import ModelAdapter, ModelOutput


class ExcelConfig(BaseModel):
    """Configuration for Excel-based model adapters."""

    workbook_path: Path = Field(description="Path to the source Excel workbook")
    use_xlwings: bool = Field(
        default=False,
        description=(
            "Use xlwings (requires Excel installed, Windows/macOS only) "
            "for full recalculation and VBA macro execution. "
            "If False, uses openpyxl (headless, no recalculation)."
        ),
    )
    run_macros: list[str] = Field(
        default_factory=list,
        description="VBA macro names to execute after injecting parameters (xlwings only).",
    )
    timeout_seconds: int = 600


class CellMapping(BaseModel):
    """Maps a parameter name to a specific cell in the workbook."""

    sheet: str
    cell: str
    param_name: str


class ExcelAdapter(ModelAdapter):
    """Base class for Excel/spreadsheet-based model adapters.

    Subclasses implement:
    - input_mappings(): define which parameters map to which cells
    - output_mappings(): define which cells contain output values
    - validate_inputs(): parameter validation

    IMPORTANT: openpyxl CANNOT recalculate formulas. If you change an
    input cell with openpyxl, downstream formula results remain stale.
    Use xlwings if the model depends on Excel's calculation engine.

    WARNING: xlwings requires a licensed Excel installation and only works
    on Windows/macOS. It will NOT work on Linux servers or in Docker.
    """

    def __init__(self, config: ExcelConfig | None = None) -> None:
        self._config = config

    @property
    def excel_config(self) -> ExcelConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires an ExcelConfig. "
                "Pass it via __init__ or override excel_config."
            )
        return self._config

    @property
    @abstractmethod
    def input_mappings(self) -> list[CellMapping]:
        """Define which parameters map to which input cells."""

    @property
    @abstractmethod
    def output_mappings(self) -> list[CellMapping]:
        """Define which cells contain output values to extract."""

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the spreadsheet model by injecting parameters and reading outputs."""
        config = self.excel_config

        if config.use_xlwings:
            return self._execute_xlwings(inputs)
        else:
            return self._execute_openpyxl(inputs)

    def _execute_openpyxl(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute using openpyxl (headless, no recalculation).

        WARNING: This reads cached formula values only. If input cells are
        changed, downstream formula results will be STALE unless the workbook
        was pre-calculated with those inputs in Excel.
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError(
                "openpyxl is not installed. Install with: pip install openpyxl"
            )

        config = self.excel_config

        # Work on a copy to preserve the original
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{self.model_id}_"))
        workbook_copy = tmp_dir / config.workbook_path.name
        shutil.copy2(config.workbook_path, workbook_copy)

        # Inject parameters
        wb = load_workbook(str(workbook_copy))
        for mapping in self.input_mappings:
            if mapping.param_name in inputs:
                ws = wb[mapping.sheet]
                ws[mapping.cell] = inputs[mapping.param_name]
        wb.save(str(workbook_copy))
        wb.close()

        # Read results (data_only=True reads cached values)
        wb_results = load_workbook(str(workbook_copy), data_only=True)
        results = {}
        for mapping in self.output_mappings:
            ws = wb_results[mapping.sheet]
            results[mapping.param_name] = ws[mapping.cell].value
        wb_results.close()

        return ModelOutput(
            model_id=self.model_id,
            outputs=results,
            metadata={
                "engine": "openpyxl",
                "warning": "Formula values are cached; no recalculation performed",
                "workbook_copy": str(workbook_copy),
            },
        )

    def _execute_xlwings(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute using xlwings (full recalculation, VBA macro support).

        Requires a licensed Excel installation (Windows/macOS only).
        """
        try:
            import xlwings as xw
        except ImportError:
            raise ImportError(
                "xlwings is not installed. Install with: pip install xlwings\n"
                "Note: xlwings requires a licensed Excel installation (Windows/macOS only)."
            )

        config = self.excel_config

        # Work on a copy
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{self.model_id}_"))
        workbook_copy = tmp_dir / config.workbook_path.name
        shutil.copy2(config.workbook_path, workbook_copy)

        app = xw.App(visible=False)
        try:
            wb = app.books.open(str(workbook_copy))

            # Inject parameters
            for mapping in self.input_mappings:
                if mapping.param_name in inputs:
                    wb.sheets[mapping.sheet].range(mapping.cell).value = inputs[mapping.param_name]

            # Trigger recalculation
            app.calculate()

            # Run VBA macros if specified
            for macro_name in config.run_macros:
                wb.macro(macro_name)()

            # Extract results
            results = {}
            for mapping in self.output_mappings:
                results[mapping.param_name] = (
                    wb.sheets[mapping.sheet].range(mapping.cell).value
                )

            return ModelOutput(
                model_id=self.model_id,
                outputs=results,
                metadata={
                    "engine": "xlwings",
                    "macros_executed": config.run_macros,
                    "workbook_copy": str(workbook_copy),
                },
            )
        finally:
            wb.close()
            app.quit()

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
