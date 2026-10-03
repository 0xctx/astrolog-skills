"""Render a source page to an image (tables and figures whose text layer is unusable)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from astrolog_skills.errors import AstroError
from astrolog_skills.sources.extract import poppler_hint


def render_page(pdf: Path, pdf_page: int, out_dir: Path, stem: str, dpi: int = 150) -> Path:
    """Write <out_dir>/<stem>-p<pdf_page>.png and return its path."""
    binary = shutil.which("pdftoppm")
    if binary is None:
        raise AstroError("pdftoppm isn't installed — it's needed to render pages.", fix=poppler_hint())
    if pdf.suffix.lower() != ".pdf":
        raise AstroError("Only PDF sources have page images.")
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / f"{stem}-p{pdf_page}"
    args = [
        binary,
        "-png",
        "-singlefile",
        "-r",
        str(dpi),
        "-f",
        str(pdf_page),
        "-l",
        str(pdf_page),
        str(pdf),
        str(prefix),
    ]
    done = subprocess.run(args, capture_output=True, text=True, check=False)
    image = prefix.with_suffix(".png")
    if done.returncode != 0 or not image.is_file():
        raise AstroError(f"Couldn't render page {pdf_page}: {done.stderr.strip()[:200]}")
    return image
