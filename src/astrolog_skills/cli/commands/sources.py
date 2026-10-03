"""`astro sources …` — a pack's private books and texts: add, search, cite pages, render tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.cli.app import out
from astrolog_skills.errors import AstroError
from astrolog_skills.sources import index, library, render
from astrolog_skills.ui import rgb


def _about(pack: str, sid: str) -> tuple[str, str]:
    """(kind, title) of a source: "pages" or "sections", and its title (or id)."""
    row = next((r for r in library.list_sources(pack) if r.get("id") == sid), {})
    return str(row.get("kind", "pages")), str(row.get("title") or sid)


def _cite(kind: str, title: str, number: int | None, label: str) -> dict[str, str]:
    """`cite`: the short form checked by the pack builder ("p. 488", "§ 12"); `where`: what a reading shows a person
    ("p. 488", or "<title>, lesson 3, 41:10")."""
    short = library.cite(kind, number)
    return {"cite": short, "where": f"{title}, {label}" if kind == "sections" and label else short}


def register(app: typer.Typer) -> None:
    src_app = typer.Typer(help="A pack's private source texts: add, search, pages, page images.", no_args_is_help=True)
    app.add_typer(src_app, name="sources")

    @src_app.command(
        "add",
        help="Add a book (PDF, scanned ones read by OCR), notes (.md, .txt), a course transcript (.txt, .srt, .vtt) or"
        " a web page (its address) to a pack's private sources and index it. Books are cited by printed page; notes,"
        " transcripts and pages by section (timestamp, lesson, heading).",
    )
    def add_cmd(
        ctx: typer.Context,
        pack: str = typer.Argument(..., help="Pack name, e.g. hellenistic (created if new)."),
        file: str = typer.Argument(..., help="The PDF, text, Markdown or caption file — or a web page's address."),
    ) -> None:
        from astrolog_skills.sources import web

        if web.is_url(file):
            saved, title = web.save(file, library.sources_dir(pack))
            added = library.add(pack, saved, web.origin(file))
            if title:
                library.set_title(pack, added.id, title)
        else:
            added = library.add(pack, Path(file))
        data = {
            "pack": pack,
            "id": added.id,
            "file": str(added.file),
            "pages": added.pages,
            "printed_offset": added.offset,
            "matter": added.matter,
            "index": str(added.index),
            "replaced": added.replaced,
            "kind": added.kind,
            "units": added.how,
            "ocr": added.ocr,
        }

        def show(c: Console) -> None:
            again = " (replaced the earlier copy)" if added.replaced else ""
            again += " — read by OCR" if added.ocr else ""
            if added.kind == "sections":
                c.print(
                    f"[{rgb('ok')}]✓[/] {escape(added.id)}: {added.pages} sections indexed, by {added.how}{again}",
                    soft_wrap=True,
                )
                c.print(f"  [{rgb('dim')}]cited as § N with its label · private: {escape(str(added.file))}[/]")
                return
            c.print(f"[{rgb('ok')}]✓[/] {escape(added.id)}: {added.pages} pages indexed{again}", soft_wrap=True)
            c.print(
                f"  [{rgb('dim')}]printed page = PDF page − {added.offset} · "
                f"front {added.matter['front']}, contents {added.matter['contents']}, back {added.matter['back']} "
                f"(ranked below the body in searches)[/]",
                soft_wrap=True,
            )
            c.print(f"  [{rgb('dim')}]private: {escape(str(added.file))}[/]", soft_wrap=True)

        out(ctx).emit(data, show)

    @src_app.command("list", help="A pack's sources.")
    def list_cmd(ctx: typer.Context, pack: str = typer.Argument(...)) -> None:
        rows = library.list_sources(pack)

        def show(c: Console) -> None:
            if not rows:
                c.print(f"No sources yet — astro sources add {escape(pack)} <file>")
            for r in rows:
                unit = "sections" if r.get("kind") == "sections" else "pages"
                state = f"{r.get('pages', '?')} {unit}" if r.get("indexed") else "not indexed"
                c.print(
                    f"  [bold]{escape(str(r['id']))}[/] {escape(str(r.get('title', '')))} · {state}", soft_wrap=True
                )

        out(ctx).emit({"pack": pack, "sources": rows}, show)

    @src_app.command("search", help='Ranked passages with their page or section, e.g. "under the beams".')
    def search_cmd(
        ctx: typer.Context,
        pack: str = typer.Argument(...),
        query: str = typer.Argument(..., help='Words (all required) and "quoted phrases".'),
        source: str = typer.Option(None, "--source", help="Only this source (default: every source in the pack)."),
        limit: int = typer.Option(8, "--limit", min=1, max=50),
        raw: bool = typer.Option(False, "--raw", help="Pass FTS5 query syntax through (OR, NOT, NEAR, prefix*)."),
    ) -> None:
        if source:
            ids = [library.resolve(pack, source)]
        else:
            ids = [str(r["id"]) for r in library.list_sources(pack) if r.get("indexed")]
            if not ids:
                library.resolve(pack, None)  # says how to add one
        rows: list[dict[str, Any]] = []
        for sid in ids:
            kind, title = _about(pack, sid)
            for h in index.search(library.index_path(pack, sid), query, limit, raw):
                rows.append({"source": sid, "kind": kind, **h.to_dict(), **_cite(kind, title, h.printed, h.label)})
        rows = sorted(rows, key=lambda r: float(r["score"]))[:limit]  # BM25: lower is better

        def show(c: Console) -> None:
            if not rows:
                c.print("No matches.")
            for r in rows:
                where = r["cite"] or f"PDF page {r['pdf_page']}"
                origin = f"[{rgb('dim')}]{escape(r['source'])}[/] " if len(ids) > 1 else ""
                label = f" [{rgb('dim')}]{escape(r['label'])}[/]" if r["label"] else ""
                note = f" [{rgb('dim')}]({r['matter']})[/]" if r["matter"] else ""
                c.print(f"{origin}[bold]{where}[/]{label}{note}  {escape(r['snippet'])}", soft_wrap=True)

        out(ctx).emit({"pack": pack, "sources": ids, "query": query, "hits": rows}, show)

    @src_app.command(
        "page",
        help='The full text of one printed page or section: a number, or for sections a timestamp ("41:10",'
        ' "lesson 3, 41:10") or words from a heading. --pdf: a PDF page number.',
    )
    def page_cmd(
        ctx: typer.Context,
        pack: str = typer.Argument(...),
        ref: str = typer.Argument(..., help="Printed page or section number, a timestamp, or heading words."),
        source: str = typer.Option(None, "--source"),
        pdf: bool = typer.Option(False, "--pdf", help="Treat the number as a PDF page."),
    ) -> None:
        sid = library.resolve(pack, source)
        db = library.index_path(pack, sid)
        kind, title = _about(pack, sid)
        if ref.strip().isdigit():
            number = int(ref)
        elif kind == "sections" and not pdf:
            number = index.find(db, ref)
        else:
            raise AstroError(f"'{ref}' isn't a page number.", fix="give the printed page, e.g. 488")
        pdf_page, printed, text, label = index.page(db, number, pdf)
        where = _cite(kind, title, printed, label)

        def show(c: Console) -> None:
            extra = f"({escape(label)})" if kind == "sections" else f"(PDF page {pdf_page})"
            c.print(f"[bold]{where['cite']}[/] [{rgb('dim')}]{extra}[/]")
            c.print(text, markup=False, highlight=False)

        out(ctx).emit(
            {"pack": pack, "source": sid, "kind": kind, "pdf_page": pdf_page, "printed": printed, "label": label,
             **where, "text": text},
            show,
        )  # fmt: skip

    @src_app.command("render", help="Render a page as an image (tables and figures).")
    def render_cmd(
        ctx: typer.Context,
        pack: str = typer.Argument(...),
        number: int = typer.Argument(..., help="Printed page number."),
        source: str = typer.Option(None, "--source"),
        pdf: bool = typer.Option(False, "--pdf", help="Treat the number as a PDF page."),
        dpi: int = typer.Option(150, "--dpi", min=50, max=400),
    ) -> None:
        sid = library.resolve(pack, source)
        if _about(pack, sid)[0] == "sections":
            raise AstroError("Only PDF pages can be rendered as images; this source is a text.")
        pdf_page, printed, _, _ = index.page(library.index_path(pack, sid), number, pdf)
        entry = next(e for e in library.read_toml(pack) if e.get("id") == sid)
        file = library.pack_dir(pack) / str(entry["file"])
        if not file.is_file():
            raise AstroError(f"The source file is missing: {file}.", fix=f"astro sources add {pack} <file>")
        image = render.render_page(file, pdf_page, library.sources_dir(pack) / ".pages", sid, dpi)

        def show(c: Console) -> None:
            c.print(f"[{rgb('ok')}]✓[/] p. {printed} → {escape(str(image))}", soft_wrap=True)

        out(ctx).emit(
            {"pack": pack, "source": sid, "pdf_page": pdf_page, "printed": printed, "image": str(image)}, show
        )
