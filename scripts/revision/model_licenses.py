#!/usr/bin/env python3
"""Per-model license and provenance table from the implementation registry.

Reads ``src/models/implementation_info.py`` (``IMPLEMENTATION_INFO``) and
writes ``docs/revision/model_licenses.md`` with, per model: display name,
implementation modes available, platform, upstream reference, and the
license notes for the upstream model and for the repository's reduction.

Usage::

    python scripts/revision/model_licenses.py --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO_LICENSE_NOTE = (
    "Repository code (adapters, reductions, orchestration) is released under the license stated in the "
    "repository's LICENSE file; vendored upstream models under `Models/` keep their own licenses as listed below."
)


def rows() -> list[dict[str, Any]]:
    from src.models.implementation_info import IMPLEMENTATION_INFO  # noqa: WPS433
    from src.models.registry import build_default_registry, default_config_dir  # noqa: WPS433

    registry = build_default_registry(default_config_dir())
    out = []
    for mid in registry.all_model_ids():
        adapter = registry.get(mid)
        info = IMPLEMENTATION_INFO.get(mid) or adapter.implementation_info
        out.append({
            "model_id": mid,
            "commodity_system": adapter.commodity_system.value,
            "display_name": info.display_name or mid,
            "modes_available": [m.value for m in info.modes_available],
            "platform": info.platform,
            "upstream_reference": info.upstream_reference,
            "license_notes": info.license_notes,
            "status_label": info.status_label,
        })
    return sorted(out, key=lambda r: (r["commodity_system"], r["model_id"]))


def render_markdown(data: list[dict[str, Any]]) -> str:
    lines = ["# Model licenses and upstream references", "", REPO_LICENSE_NOTE, "",
             "| model | system | display name | modes available | platform | upstream reference | license notes |",
             "|---|---|---|---|---|---|---|"]
    for r in data:
        lines.append(f"| `{r['model_id']}` | {r['commodity_system']} | {r['display_name']} | {', '.join(r['modes_available'])} | "
                     f"{r['platform']} | {r['upstream_reference']} | {r['license_notes'] or '-'} |")
    missing = [r["model_id"] for r in data if not r["license_notes"]]
    lines.append("")
    if missing:
        lines.append("Models without license notes in the registry: " + ", ".join(f"`{m}`" for m in missing) + ".")
    else:
        lines.append("Every registered model carries license notes in `src/models/implementation_info.py`.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    data = rows()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model_licenses.md").write_text(render_markdown(data), encoding="utf-8")
    (out / "model_licenses.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {out / 'model_licenses.md'} ({len(data)} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
