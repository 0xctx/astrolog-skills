"""A stand-in for ocrmypdf in tests: writes a PDF with a text layer to the output path (the last argument)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fakes.mini_pdf import write_pdf

BODY = ["The scanned page now reads as text after recognition, line after line of it."] * 6
write_pdf(sys.argv[-1], [[*BODY, "Recognised words about the Lot of Fortune."] for _ in range(4)])
