"""Web pages as sources (served locally, no internet) and scanned PDFs read by OCR (a stand-in for ocrmypdf)."""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from astrolog_skills.sources import library, web
from tests.conftest import run_cli
from tests.fakes.mini_pdf import write_pdf

FAKES = Path(__file__).parent / "fakes"
PARA = "Profections move the rising sign forward one sign for every year of life, and its ruler leads the year."
PAGE = f"""<!doctype html><html><head><title>Notes on Timing</title><style>p {{ color: red }}</style></head>
<body><nav><ul><li><a href="/">Home</a></li><li></li></ul></nav>
<main><h1>Notes on Timing</h1><p>{PARA}</p>
<h2>Releasing</h2><p>Releasing runs periods through the signs from the Lot of Spirit or the Lot of Fortune.</p>
<ul><li>Peaks fall in the angles from Fortune.</li><li>The loosing of the bond jumps to the opposite sign.</li></ul>
<script>var x = "never indexed";</script></main><footer>Copyright notice</footer></body></html>"""


def test_html_to_markdown() -> None:
    title, text = web.html_to_markdown(PAGE)
    assert title == "Notes on Timing"
    assert "# Notes on Timing" in text and "## Releasing" in text and "- Peaks fall in the angles" in text
    assert "never indexed" not in text and "Home" not in text and "Copyright" not in text  # outside <main>
    assert "\n-\n" not in text  # empty menu items leave no husks
    assert web.is_url("https://example.org/x") and not web.is_url("notes.md")


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    root = tmp_path / "site"
    root.mkdir()
    (root / "timing.html").write_text(PAGE)
    write_pdf(root / "paper.pdf", [[f"Line {i} of a paper about sect and the lots of the chart." for i in range(12)]])
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def ok(*args: str, env: dict[str, str] | None = None) -> dict:  # type: ignore[type-arg]
    done = run_cli("--json", *args, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def test_add_a_web_page(site: str) -> None:
    added = ok("sources", "add", "mini", f"{site}/timing.html")
    assert added["kind"] == "sections" and added["units"] == "headings" and added["id"] == "notes-on-timing"
    entry = library.list_sources("mini")[0]
    assert entry["url"] == f"{site}/timing.html" and entry["fetched"] and entry["title"] == "Notes on Timing"
    hit = ok("sources", "search", "mini", "loosing of the bond")["hits"][0]
    assert hit["where"].startswith("Notes on Timing, ") and hit["label"].endswith("Releasing")
    paper = ok("sources", "add", "mini", f"{site}/paper.pdf")
    assert paper["kind"] == "pages" and paper["file"].endswith(".pdf")
    missing = run_cli("sources", "add", "mini", f"{site}/nowhere.html")
    assert missing.returncode != 0 and "404" in missing.stdout


def test_a_scanned_pdf_needs_ocr(tmp_path: Path) -> None:
    scan = write_pdf(tmp_path / "scan.pdf", [[] for _ in range(4)])
    refused = run_cli("sources", "add", "mini", str(scan))
    assert refused.returncode != 0 and "ocrmypdf" in refused.stdout and "install" in refused.stdout
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "ocrmypdf"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKES / "fake_ocrmypdf.py"}" "$@"\n')
    shim.chmod(0o755)
    env = {"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}
    added = ok("sources", "add", "mini", str(scan), env=env)
    assert added["ocr"] is True and added["pages"] == 4
    assert library.list_sources("mini")[0]["ocr"] is True
    assert ok("sources", "search", "mini", "Lot of Fortune", env=env)["hits"]
