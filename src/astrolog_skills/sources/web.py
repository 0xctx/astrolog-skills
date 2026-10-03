"""Web pages as sources: fetched once, kept privately in the pack like any file. HTML becomes Markdown with its
headings (so a page is cited by section), a PDF stays a PDF, plain text stays text."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from astrolog_skills import __version__
from astrolog_skills.charts.store import slug
from astrolog_skills.errors import AstroError

LIMIT = 30 * 1024 * 1024  # bytes: larger downloads are refused
SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "template"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "br", "tr", "blockquote", "pre", "table", "dd", "dt", "figure"}


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://", text.strip(), re.I))


@dataclass
class Fetched:
    url: str  # after redirects
    content_type: str
    body: bytes


def fetch(url: str, timeout: float = 30.0) -> Fetched:
    request = urllib.request.Request(url, headers={"User-Agent": f"astrolog-skills/{__version__} (source fetch)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(LIMIT + 1)
            kind = response.headers.get_content_type() or ""
            final = response.geturl()
    except urllib.error.HTTPError as err:
        raise AstroError(
            f"The page answered {err.code} {err.reason}.", fix="check the address opens in a browser"
        ) from err
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise AstroError(
            f"Couldn't fetch {url}: {getattr(err, 'reason', err)}.", fix="check the address and your connection"
        ) from err
    if len(body) > LIMIT:
        raise AstroError(
            f"{url} is larger than {LIMIT // 1024 // 1024} MB.", fix="download it and add the file instead"
        )
    return Fetched(final, kind, body)


class _Text(HTMLParser):
    """HTML → Markdown-ish text: headings as #…, list items as -, paragraphs on their own lines."""

    def __init__(self, main_only: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.main_only = main_only  # the page has <main> or <article>: keep only what's inside
        self.inside = 0
        self.title = ""
        self._in_title = False
        self._heading = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("main", "article"):
            self.inside += 1
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading = int(tag[1])
            self.out.append("\n\n" + "#" * self._heading + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in BLOCK_TAGS:
            self.out.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("main", "article"):
            self.inside = max(0, self.inside - 1)
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self._in_title = False
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading = 0
            self.out.append("\n\n")
        elif tag in BLOCK_TAGS:
            self.out.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if self.skip or (self.main_only and not self.inside):
            return
        text = re.sub(r"\s+", " ", data)
        if self._heading:
            text = text.replace("\n", " ")
        self.out.append(text)

    def markdown(self) -> str:
        text = "".join(self.out)
        lines = [ln.strip() for ln in text.splitlines()]
        # drop the husks of icons and menus: bullets and headings with no words
        text = "\n".join(ln for ln in lines if not re.fullmatch(r"(-|#+)", ln))
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def html_to_markdown(html: str) -> tuple[str, str]:
    """(title, Markdown text) of an HTML page, without scripts, styles and site navigation."""
    lowered = html.lower()
    parser = _Text(main_only="<main" in lowered or "<article" in lowered)
    parser.feed(html)
    parser.close()
    return " ".join(parser.title.split()), parser.markdown()


def save(url: str, folder: Path) -> tuple[Path, str]:
    """Fetch the page into `folder` (the pack's private sources) → (file, title)."""
    got = fetch(url)
    path_part = re.sub(r"^https?://(www\.)?", "", got.url).split("?")[0].rstrip("/")
    stem = slug(path_part.rsplit("/", 1)[-1] or path_part)[:60] or "page"
    folder.mkdir(parents=True, exist_ok=True)
    if got.content_type == "application/pdf" or got.body[:5] == b"%PDF-":
        path = folder / f"{stem}.pdf"
        path.write_bytes(got.body)
        return path, ""
    text = got.body.decode("utf-8", errors="replace")
    if got.content_type in ("text/html", "application/xhtml+xml") or "<html" in text[:2000].lower():
        title, body = html_to_markdown(text)
        stem = slug(title)[:60] if title and slug(title) else stem
        if len(body.split()) < 30:
            raise AstroError(
                f"{url} has almost no readable text.", fix="if it needs a browser to show it, save it as a file"
            )
        path = folder / f"{stem}.md"
        path.write_text(f"# {title or got.url}\n\n{body}", encoding="utf-8")
        return path, title
    path = folder / f"{stem}.txt"
    path.write_text(text, encoding="utf-8")
    return path, ""


def origin(url: str) -> dict[str, str]:
    return {"url": url, "fetched": date.today().isoformat()}
