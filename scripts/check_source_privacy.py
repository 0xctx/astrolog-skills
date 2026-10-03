"""Privacy check before a release: no text from the user's private sources in the repository or its history.

Builds every 12-word run of prose from each indexed source in ~/.astrolog-skills/traditions/*/sources/.index/, then
scans the tracked files and the full git history (every patch) for any of them; and checks that no source file itself
(the PDF or text) is stored anywhere in git's objects. Exit 1 on a match.

    uv run python scripts/check_source_privacy.py
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from astrolog_skills.packs.verify import VERBATIM, tokens
from astrolog_skills.paths import data_dir

REPO = Path(__file__).resolve().parents[1]
PROSE = 10  # a run counts only with this many words in it: tables of numbers (years, ascensional times) are facts


def runs_of(words: list[str]) -> list[tuple[str, ...]]:
    found = (tuple(words[i : i + VERBATIM]) for i in range(len(words) - VERBATIM + 1))
    return [run for run in found if sum(w.isalpha() for w in run) >= PROSE]


def source_runs() -> tuple[set[int], int]:
    runs: set[int] = set()
    count = 0
    for db in sorted((data_dir() / "traditions").glob("*/sources/.index/*.sqlite")):
        count += 1
        with sqlite3.connect(db) as con:
            for (body,) in con.execute("SELECT body FROM pages WHERE matter = ''"):
                runs.update(hash(run) for run in runs_of(tokens(body)))
    return runs, count


def stored_files() -> list[str]:
    """Source files (PDF, text) whose exact bytes are a git object here, committed on any branch or ever."""
    found = []
    for path in sorted((data_dir() / "traditions").glob("*/sources/*")):
        if not path.is_file():
            continue
        sha = subprocess.run(["git", "hash-object", str(path)], cwd=REPO, capture_output=True, text=True, check=True)
        exists = subprocess.run(["git", "cat-file", "-e", sha.stdout.strip()], cwd=REPO, capture_output=True)
        if exists.returncode == 0:
            found.append(path.name)
    return found


def scan(text: str, runs: set[int]) -> int:
    return sum(1 for run in runs_of(tokens(text)) if hash(run) in runs)


def main() -> int:
    runs, sources = source_runs()
    if not sources:
        print("no indexed sources on this computer: nothing to compare against")
        return 0
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    hits: list[str] = []
    for name in files:
        path = REPO / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if n := scan(text, runs):
            hits.append(f"{name}: {n} run(s)")
    history = subprocess.run(
        ["git", "log", "--all", "-p", "--no-color", "--text"], cwd=REPO, capture_output=True, check=True
    ).stdout
    in_history = scan(history.decode("utf-8", errors="replace"), runs)
    stored = stored_files()
    print(f"{sources} source(s), {len(runs):,} {VERBATIM}-word runs; {len(files)} tracked files; history scanned")
    for h in hits:
        print("  match in", h)
    if in_history:
        print(f"  {in_history} run(s) found in the git history")
    for name in stored:
        print("  source file stored in git:", name)
    if hits or in_history or stored:
        return 1
    print("clean: no source text in the repository or its history")
    return 0


if __name__ == "__main__":
    sys.exit(main())
