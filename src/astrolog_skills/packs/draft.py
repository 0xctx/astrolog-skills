"""A pack's draft: Claude edits `traditions/<pack>/draft/`, the user sees a diff, and only an approved apply changes
the live files (the old ones are kept in `.history/`)."""

from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from astrolog_skills.sources import library

PACK_FILES = ("method.toml", "meanings.md", "process.md", "REVIEW.md")
EVIDENCE = "evidence.toml"
SKELETON = {
    "method.toml": '# Rules drafted from the sources; each section carries cite = "p. …".\nlabel = "{name}"\n',
    "meanings.md": "# {name} — meanings\n\nWritten in our own words; each entry cites the source's printed pages.\n",
    "process.md": "# {name} — reading process\n\nThe steps a reading follows, in order, with page citations.\n",
    "REVIEW.md": "# {name} — open questions\n\nVariants and anything the source leaves open, for you to decide.\n",
    EVIDENCE: "# Evidence for the draft: a few exact words from each cited page. Private — never shared.\n",
}


def draft_dir(pack: str) -> Path:
    return library.pack_dir(pack) / "draft"


def evidence_live(pack: str) -> Path:
    return library.sources_dir(pack) / EVIDENCE


@dataclass
class Started:
    path: Path
    copied: list[str]
    created: list[str]
    hand_edits: int = 0  # lines you edited in the live pack since the last apply (they carry into the draft)


def start(pack: str) -> Started:
    """Create the draft from your pack's files — or, before you have one, from the built-in pack of that name (a sample
    to cite from your sources) — or skeletons for a new pack; an existing draft is left alone."""
    live, target = library.pack_dir(pack), draft_dir(pack)
    builtin = loader.builtin_dir() / live.name
    if (live / "method.toml").is_file() or not (builtin / "method.toml").is_file():
        builtin = live
    if target.is_dir() and any(target.iterdir()):
        raise AstroError(
            f"Pack '{pack}' already has a draft at {target}.",
            fix=f"keep editing it, or delete it first: astro packs discard {pack}",
        )
    target.mkdir(parents=True, exist_ok=True)
    copied, created = [], []
    for name in (*PACK_FILES, EVIDENCE):
        src = evidence_live(pack) if name == EVIDENCE else (live / name if (live / name).is_file() else builtin / name)
        if src.is_file():
            shutil.copy2(src, target / name)
            copied.append(name)
        else:
            (target / name).write_text(SKELETON[name].format(name=pack), encoding="utf-8")
            created.append(name)
    return Started(target, copied, created, sum(len(v) for v in hand_edits(pack).values()))


def discard(pack: str) -> Path:
    target = draft_dir(pack)
    if not target.is_dir():
        raise AstroError(f"Pack '{pack}' has no draft.", fix=f"astro packs draft {pack}")
    shutil.rmtree(target)
    return target


def _require(pack: str) -> Path:
    target = draft_dir(pack)
    if not target.is_dir():
        raise AstroError(f"Pack '{pack}' has no draft.", fix=f"start one: astro packs draft {pack}")
    return target


@dataclass
class FileDiff:
    name: str
    status: str  # "new" | "changed" | "same"
    added: int
    removed: int
    diff: str
    edits_changed: list[str] = field(default_factory=list)  # lines you edited by hand that the draft changes


def applied_dir(pack: str) -> Path:
    """What the last `packs apply` wrote — the baseline your own edits are measured against."""
    return library.pack_dir(pack) / ".history" / "applied"


def _snapshot(pack: str) -> None:
    folder = applied_dir(pack)
    folder.mkdir(parents=True, exist_ok=True)
    for name in (*PACK_FILES, EVIDENCE):
        src = evidence_live(pack) if name == EVIDENCE else library.pack_dir(pack) / name
        if src.is_file():
            shutil.copy2(src, folder / name)


def hand_edits(pack: str) -> dict[str, list[str]]:
    """Per file, the lines you changed or added in the live pack since the last apply (empty before any apply)."""
    folder = applied_dir(pack)
    out: dict[str, list[str]] = {}
    for name in (*PACK_FILES, EVIDENCE):
        live = evidence_live(pack) if name == EVIDENCE else library.pack_dir(pack) / name
        base = folder / name
        if not (live.is_file() and base.is_file()):
            continue
        before = base.read_text(encoding="utf-8").splitlines()
        after = live.read_text(encoding="utf-8").splitlines()
        added = [ln[1:] for ln in difflib.unified_diff(before, after, lineterm="", n=0)
                 if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip()]  # fmt: skip
        if added:
            out[name] = added
    return out


def diff(pack: str) -> list[FileDiff]:
    """The draft against the live pack, flagging any of your own edits (since the last apply) the draft changes."""
    target, live = _require(pack), library.pack_dir(pack)
    edits = hand_edits(pack)
    out = []
    for name in (*PACK_FILES, EVIDENCE):
        new = target / name
        if not new.is_file():
            continue
        old = evidence_live(pack) if name == EVIDENCE else live / name
        before = old.read_text(encoding="utf-8").splitlines(keepends=True) if old.is_file() else []
        after = new.read_text(encoding="utf-8").splitlines(keepends=True)
        lines = list(difflib.unified_diff(before, after, f"live/{name}", f"draft/{name}"))
        added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
        status = "new" if not old.is_file() else "changed" if lines else "same"
        kept = {ln.rstrip("\n") for ln in after}
        changed = [ln for ln in edits.get(name, []) if ln not in kept]
        out.append(FileDiff(name, status, added, removed, "".join(lines), changed))
    return out


@dataclass
class Applied:
    files: list[str]
    backup: Path | None


def apply(pack: str) -> Applied:
    """Copy the draft over the live pack (callers verify first and have the user's approval)."""
    target, live = _require(pack), library.pack_dir(pack)
    changed = [d.name for d in diff(pack) if d.status != "same"]
    backup = None
    existing = [n for n in changed if (evidence_live(pack) if n == EVIDENCE else live / n).is_file()]
    if existing:
        backup = live / ".history" / datetime.now().strftime("%Y%m%d-%H%M%S")
        backup.mkdir(parents=True, exist_ok=True)
        for name in existing:
            shutil.copy2(evidence_live(pack) if name == EVIDENCE else live / name, backup / name)
    for name in changed:
        dest = evidence_live(pack) if name == EVIDENCE else live / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / name, dest)
    shutil.rmtree(target)
    _snapshot(pack)
    return Applied(changed, backup)
