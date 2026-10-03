"""`astro data …` — research data files: the free Astro-Databank samples and category discovery."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.charts import adb
from astrolog_skills.cli.app import out
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir
from astrolog_skills.ui import rgb

SAMPLE_URL = "https://www.astro.com/adbexport/c_sample.zip"
NOTICE = (
    "Astro-Databank data © Astrodienst AG — for your own research only; don't publish or share it. "
    "Full exports need a licence: https://www.astro.com/adbexport/"
)


def fetch_sample(progress: callable = lambda _m: None) -> Path:  # type: ignore[valid-type]
    target_dir = data_dir() / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "c_sample.zip"
        request = urllib.request.Request(SAMPLE_URL, headers={"User-Agent": "astrolog-skills"})
        try:
            with urllib.request.urlopen(request, timeout=60) as resp, open(archive, "wb") as f:
                shutil.copyfileobj(resp, f)
        except OSError as err:
            raise AstroError(
                f"Couldn't download the sample: {err}.", fix="check your connection and try again"
            ) from err
        with zipfile.ZipFile(archive) as z:
            xml_names = [n for n in z.namelist() if n.endswith(".xml")]
            if not xml_names:
                raise AstroError("The sample archive has no XML file.")
            z.extract(xml_names[0], tmp)
            target = target_dir / "c_sample.xml"
            shutil.move(str(Path(tmp) / xml_names[0]), target)
    return target


def register(app: typer.Typer) -> None:
    data_app = typer.Typer(help="Research data: Astro-Databank samples, categories.", no_args_is_help=True)
    app.add_typer(data_app, name="data")

    @data_app.command("fetch-sample", help="Download the free Astro-Databank sample (~5,700 charts) for research.")
    def fetch(ctx: typer.Context) -> None:
        path = fetch_sample()
        records, stats = adb.load(path)

        def render(c: Console) -> None:
            c.print(f"[{rgb('ok')}]✓[/] {len(records)} usable charts in [bold]{escape(str(path))}[/]")
            c.print(f"  [{rgb('dim')}]{NOTICE}[/]")
            c.print(f"  next: astro set create my-set --adb {escape(str(path))} --rating AA")

        out(ctx).emit({"ok": True, "path": str(path), "stats": stats, "notice": NOTICE}, render)

    @data_app.command("categories", help="List Astro-Databank categories (with counts) to build sets from.")
    def categories(
        ctx: typer.Context,
        file: str = typer.Argument(None, help="ADB XML file (default: the downloaded sample)."),
        grep: str = typer.Option("", "--grep", help="Only categories containing this text, e.g. music."),
        top: int = typer.Option(40, "--top"),
    ) -> None:
        path = Path(file).expanduser() if file else data_dir() / "data" / "c_sample.xml"
        found = adb.categories(path, grep)[:top]

        def render(c: Console) -> None:
            for name, n in found:
                c.print(f"  [{rgb('dim')}]{n:>5}[/] {escape(name)}")

        out(ctx).emit({"file": str(path), "categories": found}, render)
