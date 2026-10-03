"""A character canvas (char, fg, bg, bold per cell) serialised with the fewest possible escape codes.

Claude Code truncates `!` output around 30,000 characters; emitting only the SGR parameters that change keeps a
full-colour chart near 20 KB (a naive per-cell encoding measured 51 KB).
"""

from __future__ import annotations

from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass
class Cell:
    ch: str = " "
    fg: RGB | None = None
    bg: RGB | None = None
    bold: bool = False


class Canvas:
    def __init__(self, width: int, height: int, bg: RGB | None = None) -> None:
        self.width, self.height = width, height
        self.cells = [[Cell(bg=bg) for _ in range(width)] for _ in range(height)]

    def put(self, x: int, y: int, text: str, fg: RGB | None = None, bg: RGB | None = None, bold: bool = False) -> None:
        for i, ch in enumerate(text):
            if 0 <= x + i < self.width and 0 <= y < self.height:
                cell = self.cells[y][x + i]
                cell.ch, cell.bold = ch, bold
                if fg is not None:
                    cell.fg = fg
                if bg is not None:
                    cell.bg = bg

    def fill(self, x: int, y: int, w: int, h: int, ch: str = " ", fg: RGB | None = None, bg: RGB | None = None) -> None:
        for yy in range(y, y + h):
            self.put(x, yy, ch * w, fg, bg)

    def center(
        self, x: int, y: int, w: int, text: str, fg: RGB | None = None, bg: RGB | None = None, bold: bool = False
    ) -> None:
        text = text[:w]
        self.put(x + (w - len(text)) // 2, y, text, fg, bg, bold)

    def box(self, x: int, y: int, w: int, h: int, fg: RGB, bg: RGB | None = None) -> None:
        self.put(x, y, "╔" + "═" * (w - 2) + "╗", fg, bg, True)
        self.put(x, y + h - 1, "╚" + "═" * (w - 2) + "╝", fg, bg, True)
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, "║", fg, bg, True)
            self.put(x + w - 1, yy, "║", fg, bg, True)

    def paste(self, other: Canvas, x: int, y: int) -> None:
        for dy, row in enumerate(other.cells):
            for dx, cell in enumerate(row):
                if 0 <= x + dx < self.width and 0 <= y + dy < self.height:
                    self.cells[y + dy][x + dx] = Cell(cell.ch, cell.fg, cell.bg, cell.bold)

    def plain(self) -> str:
        return "\n".join("".join(c.ch for c in row).rstrip() for row in self.cells)

    def render(self) -> str:
        """ANSI truecolor, emitting only the SGR parameters that change between neighbouring cells."""
        lines = []
        for row in self.cells:
            out: list[str] = []
            bold: bool | None = None
            fg: RGB | None = None
            bg: RGB | None = None
            fresh = True
            for cell in row:
                want_fg = fg if cell.ch == " " else cell.fg  # spaces never need a foreground change
                want_bold = bold if cell.ch == " " else cell.bold
                params: list[str] = []
                if want_bold is not None and (fresh or want_bold != bold):
                    params.append("1" if want_bold else "22")
                if want_fg is not None and (fresh or want_fg != fg):
                    params.append(f"38;2;{want_fg[0]};{want_fg[1]};{want_fg[2]}")
                if cell.bg is not None and (fresh or cell.bg != bg):
                    params.append(f"48;2;{cell.bg[0]};{cell.bg[1]};{cell.bg[2]}")
                if params:
                    out.append("\x1b[" + ";".join(params) + "m")
                    fresh = False
                bold, fg, bg = want_bold, want_fg, cell.bg
                out.append(cell.ch)
            lines.append("".join(out) + "\x1b[0m")
        return "\n".join(lines)


def stack(canvases: list[Canvas], gap: int = 1, bg: RGB | None = None) -> Canvas:
    """Views one under another, each centred, with `gap` blank rows between them."""
    if not canvases:
        return Canvas(0, 0)
    width = max(c.width for c in canvases)
    height = sum(c.height for c in canvases) + gap * (len(canvases) - 1)
    out = Canvas(width, height, bg)
    y = 0
    for c in canvases:
        out.paste(c, (width - c.width) // 2, y)
        y += c.height + gap
    return out
