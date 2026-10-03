"""Run Astrolog safely: argv lists only, never a shell; AstroExpression values come back on stderr."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from astrolog_skills.errors import AstroError

EXPRESSION = re.compile(r"Expression returned: (-?\d+(?:\.\d+)?)")
INSTALL_FIX = (
    "build it from the official source with `astro astrolog install --yes`, "
    "or point to yours: `astro config set astrolog.path /path/to/astrolog`"
)


@dataclass(frozen=True)
class Completed:
    stdout: str
    stderr: str
    returncode: int


def run(binary: Path, args: list[str], timeout: float = 30) -> Completed:
    try:
        proc = subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            encoding="latin-1",  # Astrolog output isn't UTF-8
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as err:
        raise AstroError(f"Astrolog isn't at {binary}.", fix=INSTALL_FIX) from err
    except PermissionError as err:
        raise AstroError(f"Astrolog at {binary} isn't executable.", fix=f"chmod +x {binary}") from err
    except subprocess.TimeoutExpired as err:
        raise AstroError(
            f"Astrolog took longer than {timeout:g}s and was stopped.",
            fix="run `astro doctor` to check the installation",
        ) from err
    return Completed(proc.stdout, proc.stderr, proc.returncode)


# Astrolog stops reading a command line after roughly 100 arguments (each `-~ 'expr'` is two), and `-Yq`
# accepts at most 9 lines: one to cast, up to 8 to evaluate.
EXPRS_PER_LINE = 40
MAX_EXPRESSIONS = EXPRS_PER_LINE * 8


def expressions(binary: Path, chart_args: list[str], exprs: list[str], timeout: float = 30) -> list[float]:
    """Cast a chart, then evaluate AstroExpressions against it.

    `-Yq<n>` runs n command lines in sequence: the first casts the chart (`-Y0` hides its text), the
    others evaluate the `-~` expressions in chunks. The strings are built only from our own constants
    and validated numbers — never from user text.
    """
    if len(exprs) > MAX_EXPRESSIONS:
        raise AstroError(f"Too many expressions in one call ({len(exprs)} > {MAX_EXPRESSIONS}).")
    cast = " ".join([*chart_args, "-Y0"])
    chunks = [exprs[i : i + EXPRS_PER_LINE] for i in range(0, len(exprs), EXPRS_PER_LINE)] or [[]]
    lines = [" ".join(f"-~ '{e}'" for e in chunk) + " -Y0" for chunk in chunks]
    done = run(binary, [f"-Yq{1 + len(lines)}", cast, *lines], timeout=timeout)
    values = [float(v) for v in EXPRESSION.findall(done.stderr)]
    if len(values) != len(exprs):
        tail = " | ".join((done.stderr or done.stdout).strip().splitlines()[-3:]) or "no output at all"
        raise AstroError(
            f"Astrolog returned {len(values)} of {len(exprs)} values ({tail}).",
            fix="run `astro doctor` — a too-long install path or missing data files cause this",
        )
    return values
