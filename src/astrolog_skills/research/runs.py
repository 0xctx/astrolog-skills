"""Saved research runs: results plus everything needed to reproduce them."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astrolog_skills import __version__
from astrolog_skills.astrolog import locate
from astrolog_skills.charts import sets
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.loader import Pack
from astrolog_skills.paths import data_dir
from astrolog_skills.research.sweep import SweepResult


def runs_dir() -> Path:
    return data_dir() / "research"


def save(result: SweepResult, pack: Pack) -> Path:
    s = sets.load(result.set_name)
    found = locate.find()
    method_file = pack.directory / "method.toml"
    meta = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "toolkit": __version__,
        "astrolog": locate.version_text(locate.version(found.path)) if found else None,
        "set": {"name": s.name, "kind": s.kind, "path": s.path, "charts": s.charts, "filter": s.filter.__dict__},
        "pack": {"name": pack.name, "method_sha256": hashlib.sha256(method_file.read_bytes()).hexdigest()},
        "params": result.params,
    }
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = runs_dir() / f"{stamp}-{s.name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"meta": meta, "result": result.to_dict()}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return path


def list_runs() -> list[dict[str, Any]]:
    out = []
    for path in sorted(runs_dir().glob("*.json"), reverse=True) if runs_dir().is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        meta, result = data["meta"], data["result"]
        out.append(
            {
                "id": path.stem,
                "created": meta["created"],
                "set": meta["set"]["name"],
                "count": result["count"],
                "range": meta["params"]["range"],
                "pack": meta["pack"]["name"],
            }
        )
    return out


def load(run_id: str) -> dict[str, Any]:
    matches = sorted(runs_dir().glob(f"{run_id}*.json")) if runs_dir().is_dir() else []
    if not matches:
        raise AstroError(f"No research run '{run_id}'.", fix="see `astro research list`")
    data: dict[str, Any] = json.loads(matches[-1].read_text(encoding="utf-8"))
    return data
