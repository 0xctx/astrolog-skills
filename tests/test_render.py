from __future__ import annotations

import re
from pathlib import Path

import pytest

from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from astrolog_skills.render import compose, theme
from astrolog_skills.render.canvas import Canvas, stack
from astrolog_skills.render.views import chart as chart_view
from astrolog_skills.render.views.common import ViewData, degree_text, short_name

EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Albert Einstein")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def data(fake_astrolog: Path) -> ViewData:
    return ViewData.build(cast(EINSTEIN, P.load("default")), loader.load("psychological"))


def test_canvas_emits_only_changes() -> None:
    c = Canvas(6, 1, (0, 0, 0))
    c.put(0, 0, "abcdef", fg=(255, 0, 0), bold=True)
    out = c.render()
    assert out.count("38;2;255;0;0") == 1 and out.count("48;2;0;0;0") == 1
    assert ANSI.sub("", out) == "abcdef"


def test_canvas_spaces_keep_colour_state() -> None:
    c = Canvas(5, 1, (0, 0, 0))
    c.put(0, 0, "a b c", fg=(1, 2, 3))
    assert c.render().count("38;2;1;2;3") == 1


def test_stack_centres_and_gaps() -> None:
    a, b = Canvas(10, 2), Canvas(4, 1)
    b.put(0, 0, "xxxx")
    s = stack([a, b], gap=1)
    assert (s.width, s.height) == (10, 4) and s.plain().splitlines()[3] == "   xxxx"


def test_degree_text_truncates() -> None:
    assert degree_text(353.507747) == "23°30′" and degree_text(29.99999) == "29°59′" and degree_text(3.14) == " 3°08′"


def test_theme_loads_and_air_is_not_yellow() -> None:
    t = theme.load("default")
    r, g, b = t.elements["air"]["header_bg"]
    assert b > r and b > g  # lavender, never yellow (user preference)
    assert t.with_letters().glyphs is False


def test_theme_errors_and_user_override(tmp_path: Path) -> None:
    theme.copy_to_user("default", "mine")
    assert theme.load("mine").label == "Pastel sky"
    (theme.user_dir() / "broken.toml").write_text('label = "x"\n[ui]\npage = [1, 2]\n')
    with pytest.raises(AstroError):
        theme.load("broken")
    with pytest.raises(AstroError):
        theme.load("nope")


def test_chart_view_layout(data: ViewData) -> None:
    text = chart_view.draw(data, theme.load("default"), 80).plain()
    lines = text.splitlines()
    assert {len(line) for line in lines} == {77}
    assert "ALBERT EINSTEIN" in text and "ELEMENTS" in text and "PLANET GROUPS" in text
    # rising sign (Cancer) at left-middle, Capricorn opposite, Aries/Pisces on the MC side (top row)
    assert "CANCER" in lines[15] and "CAPRICORN" in lines[8] and "PISCES" in lines[1]
    assert "☉ Sun" in text and "℞" in text


@pytest.mark.parametrize("harmonic", [1, 7])
@pytest.mark.parametrize("width", [80, 120])
def test_balance_bars_match_counts(fake_astrolog: Path, harmonic: int, width: int) -> None:
    data = ViewData.build(cast(EINSTEIN, P.load("default")), loader.load("psychological"), harmonic=harmonic)
    text = chart_view.draw(data, theme.load("default"), width).plain()
    rows = re.findall(r"(Fire|Earth|Air|Water|Cardinal|Fixed|Mutable) +(■*) +(\d+)", text)
    assert len(rows) == 7
    by_count = {}
    for _, blocks, n in rows:
        by_count.setdefault(int(n), set()).add(len(blocks))
    assert all(len(sizes) == 1 for sizes in by_count.values())  # equal counts, equal bars
    if max(by_count) <= 5:
        assert all(sizes == {n} for n, sizes in by_count.items())  # one block per planet when it fits


def test_balance_bars_scale_when_crowded(data: ViewData) -> None:
    for i, p in enumerate(data.chart.points):  # most planets in Aries: fire and cardinal overflow the bar space
        p.lon = 40.0 if i == 0 else 5.0
    text = chart_view.draw(data, theme.load("default"), 80).plain()
    rows = {name: (len(blocks), int(n)) for name, blocks, n in re.findall(r"(Fire|Cardinal|Earth) +(■*) +(\d+)", text)}
    assert rows["Fire"][1] > 5 and rows["Fire"] == (rows["Cardinal"][0], rows["Cardinal"][1])
    assert rows["Earth"] == (1, 1)
    assert {len(line) for line in text.splitlines()} == {77}


def test_chart_view_cusp_labels_are_truthful(fake_astrolog: Path) -> None:
    whole = chart_view.draw(
        ViewData.build(cast(EINSTEIN, P.load("whole-sign")), loader.load("psychological")), theme.load("default"), 80
    ).plain()
    assert re.search(r"CANCER\s+1 ║", whole) and re.search(r"CAPRICORN\s+7 ║", whole)


@pytest.mark.parametrize("width", [80, 120])
@pytest.mark.parametrize("glyphs", [True, False])
@pytest.mark.parametrize("pack", ["psychological", "vibrational"])
def test_all_views_fit_and_align(fake_astrolog: Path, width: int, glyphs: bool, pack: str) -> None:
    data = ViewData.build(cast(EINSTEIN, P.load("default")), loader.load(pack))
    th = theme.load("default") if glyphs else theme.load("default").with_letters()
    for name in compose.VIEWS:
        canvas = compose.compose(data, th, [name], width)
        assert len({len(line) for line in ANSI.sub("", canvas.render()).splitlines()}) == 1, name
        assert max(len(line) for line in canvas.plain().splitlines()) <= width
    names = compose.parse_views("all")
    text, left_out = compose.render_within_budget(data, th, names, width)
    # the aspect trees grow with the chart, so `all` may split: what shows fits, the rest is named to run next
    assert len(text) <= compose.BUDGET and names[: len(names) - len(left_out)][:1] == ["chart"]
    assert left_out == names[len(names) - len(left_out) :]


def test_letters_theme_has_no_astro_glyphs(data: ViewData) -> None:
    text = compose.compose(data, theme.load("default").with_letters(), ["chart", "aspects"], 80).plain()
    assert not set("☉☽☿♀♂♃♄♅♆♇⚷☊☋⚺⚻⚼") & set(text)


@pytest.mark.parametrize("harmonic", [1, 7])
def test_aspect_trees_planets_then_midpoints(fake_astrolog: Path, harmonic: int) -> None:
    data = ViewData.build(cast(EINSTEIN, P.load("default")), loader.load("psychological"), harmonic=harmonic)
    text = compose.compose(data, theme.load("default").with_letters(), ["aspects"], 80).plain()
    assert "ASPECTS & MIDPOINTS" in text and "S NODE" not in text and "MIDHEAVEN" in text
    assert len({len(line) for line in text.splitlines()}) == 1
    # read the left-hand column's trees: each is planets (no "/") then midpoints ("/"), both tightest first
    trees: list[list[tuple[bool, int]]] = []
    for line in text.splitlines():
        left = line[1:40]
        if re.match(r" +\S+ [A-Z ]+ +\d+°", left):
            trees.append([])
        elif (hit := re.match(r" +\S+ +(\S.*?) +(\d+)°(\d\d)′", left)) and trees:
            trees[-1].append(("/" in hit.group(1), int(hit.group(2)) * 60 + int(hit.group(3))))
    assert trees and any(trees)
    for rows in trees:
        kinds = [is_mid for is_mid, _ in rows]
        assert kinds == sorted(kinds)  # planets first
        orbs = [o for is_mid, o in rows if not is_mid]
        assert orbs == sorted(orbs)  # aspects tightest first; midpoints strongest first (orbs differ by aspect)
    if harmonic > 1:
        assert "as measured in the H7 chart" in text  # default display.orbs = harmonic
    # headings aren't cut short, e.g. "MC MIDHEAVEN  12°50′ Pisces"
    for p in data.chart.points:
        if p.key != "south_node":
            name = short_name(p.key, p.name).upper()
            assert re.search(rf"{name}  \d+°\d\d′ [A-Z][a-z]+", text), name


def test_pack_without_midpoints_shows_planet_aspects_only(fake_astrolog: Path) -> None:
    import dataclasses

    pack = loader.load("psychological")
    pack = dataclasses.replace(pack, method=dataclasses.replace(pack.method, midpoint_choice=()))
    text = compose.compose(ViewData.build(cast(EINSTEIN, P.load("default")), pack), theme.load("default"), ["aspects"])
    plain = text.plain()
    assert "MIDPOINTS" not in plain and "midpoints" not in plain and "/" not in plain
    assert "aspects to other planets" in plain and len({len(line) for line in plain.splitlines()}) == 1


def test_orbs_follow_display_setting(fake_astrolog: Path) -> None:
    natal = cast(EINSTEIN, P.load("default"))
    pack = loader.load("vibrational")
    shown = ViewData.build(natal, pack, 7)
    as_natal = ViewData.build(natal, pack, 7, natal_orbs=True)
    assert (shown.orb_scale, as_natal.orb_scale) == (1, 7) and ViewData.build(
        natal, pack, natal_orbs=True
    ).orb_scale == 1
    a = compose.compose(shown, theme.load("default"), ["aspects"]).plain()
    b = compose.compose(as_natal, theme.load("default"), ["aspects"]).plain()
    assert "as measured in the H7 chart" in a and "new method ☌ 3°" in a  # the vibrational pack's midpoint orb
    assert "natal degrees" in b and "new method ☌ 0°25′" in b  # 3° ÷ 7

    def first_sun_orb(text: str) -> int:  # minutes, from the first row under the SUN heading
        lines = text.splitlines()
        row = lines[next(i for i, line in enumerate(lines) if "SUN " in line) + 1]
        d, m = re.search(r"(\d+)°(\d\d)′", row).groups()  # type: ignore[union-attr]
        return int(d) * 60 + int(m)

    assert abs(first_sun_orb(a) - 7 * first_sun_orb(b)) <= 7  # same aspect, × 7 (minutes truncate)


@pytest.mark.parametrize("pack", ["psychological", "vibrational"])
@pytest.mark.parametrize("prof", ["default", "many"])
def test_every_view_alone_fits_the_bang_limit(fake_astrolog: Path, pack: str, prof: str) -> None:
    from astrolog_skills.engine.objects import OBJECTS

    many = P.user_dir() / "many.toml"
    many.parent.mkdir(parents=True, exist_ok=True)
    many.write_text("[points]\nobjects = [" + ", ".join(f'"{o.key}"' for o in OBJECTS) + "]\n")
    data = ViewData.build(cast(EINSTEIN, P.load(prof)), loader.load(pack))
    th = theme.load("default")
    for name in [n for n in compose.VIEWS if n not in ("transits", "grid")]:  # grid refuses 20 bodies at 80 columns
        text, _ = compose.render_within_budget(data, th, [name], 80)
        assert len(text) <= compose.BUDGET, name
    # the aspects view pages: every page fits, the pages together hold every tree, and each names the next
    pages, seen = [], []
    request = ["aspects"]
    while request:
        text, request = compose.render_within_budget(data, th, request, 80)
        pages.append(text)
        seen += re.findall(r"^║ +\S+ ([A-Z][A-Z ]+?)  \d", ANSI.sub("", text), re.M)
    assert all(len(t) <= compose.BUDGET for t in pages) and len(seen) == len(set(seen))
    full = compose.compose(data, th, ["aspects"], 80).plain()
    assert sorted(seen) == sorted(re.findall(r"^║ +\S+ ([A-Z][A-Z ]+?)  \d", full, re.M))
    if len(pages) > 1:
        assert "page 1 of" in ANSI.sub("", pages[0])


def test_aspect_page_syntax() -> None:
    assert compose.parse_views("aspects:2,positions") == ["aspects:2", "positions"]
    for bad in ("aspects:0", "aspects:x", "chart:2"):
        with pytest.raises(AstroError):
            compose.parse_views(bad)


def test_all_leaves_out_the_grid() -> None:
    assert "grid" in compose.VIEWS and "grid" not in compose.parse_views("all")


def test_harmonic_view(fake_astrolog: Path) -> None:
    data = ViewData.build(cast(EINSTEIN, P.load("default")), loader.load("vibrational"), harmonic=7)
    text = compose.compose(data, theme.load("default"), ["chart", "patterns"], 80).plain()
    assert "HARMONIC 7" in text and "Mercury · Saturn · Pluto" in text


def test_budget_splits_views(data: ViewData, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compose, "BUDGET", 15_000)
    text, left_out = compose.render_within_budget(data, theme.load("default"), ["chart", "aspects", "positions"], 80)
    assert text and left_out and left_out[0] in ("aspects", "positions")


def test_parse_views() -> None:
    assert compose.parse_views("") == ["chart"]
    assert compose.parse_views("all") == ["chart", "aspects", "balance", "positions"]
    with pytest.raises(AstroError):
        compose.parse_views("chart,wheel")


def test_too_many_bodies_for_the_grid(fake_astrolog: Path) -> None:
    from astrolog_skills.engine.objects import OBJECTS

    many = P.user_dir() / "many.toml"
    many.parent.mkdir(parents=True, exist_ok=True)
    many.write_text("[points]\nobjects = [" + ", ".join(f'"{o.key}"' for o in OBJECTS) + "]\n")
    data = ViewData.build(cast(EINSTEIN, P.load("many")), loader.load("psychological"))
    with pytest.raises(AstroError) as err:
        compose.compose(data, theme.load("default"), ["grid"], 80)
    assert err.value.fix and "--width 120" in err.value.fix
    assert "ASPECTS" in compose.compose(data, theme.load("default"), ["aspects"], 80).plain()  # the list has no limit
