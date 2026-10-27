"""CITATION.cff and .zenodo.json must stay parseable and consistent with pyproject."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)


def test_citation_cff_parses_and_matches_version():
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    assert cff["cff-version"] == "1.2.0" and cff["type"] == "software"
    assert cff["version"] == _pyproject_version()
    assert [a["family-names"] for a in cff["authors"]] == ["Golden", "Indelicato", "Varshney", "Thornsbury"]
    assert cff["repository-code"].startswith("https://github.com/")
    assert cff["preferred-citation"]["journal"] == "Communications Engineering"


def test_zenodo_json_parses_and_matches_cff():
    z = json.loads((REPO / ".zenodo.json").read_text(encoding="utf-8"))
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    assert z["upload_type"] == "software" and z["access_right"] == "open"
    assert z["version"] == cff["version"] and z["title"] == cff["title"]
    assert [c["name"].split(",")[0] for c in z["creators"]] == [a["family-names"] for a in cff["authors"]]
