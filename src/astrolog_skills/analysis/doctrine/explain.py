"""The study: every doctrine and time-lord finding for a chart with the reason it holds here (built from the
engine's numbers) and the pack's own glossary entry for what it means. The terminal views and the HTML panels both
draw from this one structure."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from astrolog_skills.analysis.doctrine.engine import NatalDoctrine, analyse
from astrolog_skills.analysis.doctrine.rules import SEVEN, Doctrine, SectRules
from astrolog_skills.analysis.timing.profections import anniversary, profection
from astrolog_skills.analysis.timing.releasing import releaser
from astrolog_skills.analysis.timing.sect_light import sect_light_lords
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.meanings import slug

# finding → the glossary term that explains it (a pack's meanings.md `## Glossary` supplies the text)
TERMS = {
    "of_sect": "Of the sect", "contrary_to_sect": "Contrary to the sect", "rejoices_hemisphere": "Rejoicing by hemisphere",
    "rejoices_sign": "Rejoicing by sign", "domicile": "Domicile", "exaltation": "Exaltation", "depression": "Depression",
    "adversity": "Adversity", "bounds": "Own bounds", "decan": "Own decan", "triplicity": "Triplicity",
    "triplicity_sect_ruler": "Triplicity", "under_beams": "Under the beams", "in_heart": "In the heart",
    "chariot": "Chariot", "heliacal_emerging": "Emerging from the beams", "heliacal_sinking": "Sinking under the beams",
    "morning_riser": "Morning star", "evening_riser": "Evening star", "retrograde": "Retrograde", "additive": "Additive",
    "subtractive": "Subtractive", "stationary": "Stationary", "angular": "Angular", "succedent": "Succedent",
    "declining": "Declining", "good_place": "Good place", "bad_place": "Bad place", "busy": "Busy place",
    "not_busy": "Idle place", "joy": "Joy", "reception": "Reception", "exchange": "Exchange",
    "day": "Day and night charts", "lot": "Lots", "profection": "Annual profections", "releasing": "Zodiacal releasing",
    "peak": "Peak period", "loosing": "Loosing of the bond", "completion": "Completion", "triad": "Angular triads from Fortune",
    "lords": "Triplicity lords of the sect light",
    "proper_face": "Proper face", "running_in_the_void": "Running in the void", "busy_by_angle": "Busy place",
    "containment": "Containment", "assembly": "Assembly", "midheaven_degree": "Midheaven degree",
    "mercury_role": "Mercury's role",
}  # fmt: skip
SKIP = {"bonified", "maltreated", "bonified_by_sect_benefic", "maltreated_by_contrary_malefic", "reception", "exchange"}
CHECKLIST = {
    "lot_good_place": "in a good place", "lot_bad_place": "in a bad place", "benefic_copresent": "a benefic in its sign",
    "malefic_copresent": "a malefic in its sign", "benefic_configured": "a benefic sees it",
    "malefic_configured": "a malefic sees it", "malefic_in_aversion": "no malefic sees it",
    "benefic_in_aversion": "no benefic sees it", "lord_benefic": "lord is a benefic", "lord_malefic": "lord is a malefic",
    "lord_well_placed_by_sign": "lord in domicile or exaltation", "lord_poorly_placed_by_sign": "lord in adversity or depression",
    "lord_good_place": "lord in a good place", "lord_bad_place": "lord in a bad place", "lord_configured": "lord sees the lot",
    "lord_not_configured": "lord can't see the lot", "lord_configured_to_benefics": "lord seen by a benefic",
    "lord_in_aversion_to_benefics": "lord unseen by the benefics", "lord_in_aversion_to_malefics": "lord unseen by the malefics",
    "lord_configured_to_malefics": "lord seen by a malefic", "lord_bonified": "lord bonified",
    "lord_not_bonified": "lord not bonified", "lord_not_maltreated": "lord not maltreated", "lord_maltreated": "lord maltreated",
    "lord_not_under_beams": "lord clear of the beams", "lord_under_beams": "lord under the beams",
}  # fmt: skip
ASPECT_ANGLE = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def pos(lon: float) -> str:
    total = int(round((lon % 360) * 3600, 6)) // 60  # whole arcminutes, truncated like the engine
    s, rest = divmod(total, 1800)
    return f"{rest // 60}°{rest % 60:02d}′ {SIGNS[s]}"


def arc(x: float) -> str:
    total = int(round(abs(x) * 3600, 6)) // 60
    return f"{total // 60}°{total % 60:02d}′"


def pretty(name: str) -> str:
    return name.replace("_", " ").capitalize()


class _Study:
    def __init__(
        self, natal: ChartModel, doctrine: Doctrine, result: NatalDoctrine, glossary: dict[str, dict[str, str]]
    ):
        self.natal, self.d, self.r, self.glossary = natal, doctrine, result, glossary
        self.asc = natal.angles["asc"]
        self.lon = {k: natal.point(k).lon for k in SEVEN}
        self.name = {k: natal.point(k).name for k in SEVEN}
        self.sect = doctrine.sect or SectRules()
        self.members = set(self.sect.diurnal if result.day else self.sect.nocturnal)
        self.used: set[str] = set()

    def term(self, key: str) -> str:
        """The glossary slug for a finding (recorded so the page carries only the entries it uses)."""
        title = TERMS.get(key, pretty(key))
        s = slug(title)
        if s in self.glossary:
            self.used.add(s)
            return s
        return ""

    def label(self, key: str) -> str:
        s = self.term(key)
        return self.glossary[s]["title"] if s else TERMS.get(key, pretty(key))

    # ── reasons ──
    def place_why(self, k: str) -> str:
        p = self.r.planet(k).place
        rising = SIGNS[sign_index(self.asc)]
        seen = "sees" if p.good else "is in aversion to" if p.good is False else "relates to"
        return f"{self.name[k]} is in the {ordinal(p.place)} whole-sign place from {rising} rising, a place that {seen} the rising sign."

    def token_why(self, k: str, tok: str) -> str:
        pd = self.r.planet(k)
        chart = "day" if self.r.day else "night"
        if tok in ("of_sect", "contrary_to_sect") and pd.sect:
            extra = (
                f" Mercury takes its sect from its phase: here a {pd.phase.star} star."
                if k == "mercury" and pd.phase and pd.phase.star
                else ""
            )
            return f"{self.name[k]} belongs to the {pd.sect.sect} sect, and this is a {chart} chart.{extra}"
        if tok in ("good_place", "bad_place", "angular", "succedent", "declining", "busy", "not_busy"):
            return self.place_why(k)
        if tok == "joy":
            return f"{self.name[k]} rejoices in the {ordinal(pd.place.place)} place, and that is where it is."
        if (
            tok
            in (
                "domicile",
                "exaltation",
                "depression",
                "adversity",
                "bounds",
                "decan",
                "triplicity",
                "triplicity_sect_ruler",
            )
            and pd.dignities
        ):
            lords = pd.dignities.lords

            def nm(x: str) -> str:
                return self.name.get(x, "—")

            return (
                f"{self.name[k]} at {pos(self.lon[k])}: the sign's lord is {nm(lords.domicile)}, the bounds' {nm(lords.bounds)}, "
                f"the decan's {nm(lords.decan)}"
                + (f"; triplicity lords {', '.join(nm(x) for x in lords.triplicity)}" if lords.triplicity else "")
                + "."
            )
        if pd.phase and tok in (
            "under_beams",
            "in_heart",
            "chariot",
            "heliacal_emerging",
            "heliacal_sinking",
            "morning_riser",
            "evening_riser",
        ):
            dist = pd.phase.distance or 0.0
            if tok == "heliacal_emerging":
                return f"{self.name[k]} is {arc(dist)} from the Sun and clears the beams within the pack's days after birth."
            if tok == "heliacal_sinking":
                return f"{self.name[k]} is {arc(dist)} from the Sun and goes under the beams within the pack's days after birth."
            if tok in ("morning_riser", "evening_riser"):
                return f"{self.name[k]} is {arc(dist)} {'before' if tok == 'morning_riser' else 'after'} the Sun in the zodiac and clear of the beams."
            if tok == "chariot":
                return f"{self.name[k]} is {arc(dist)} from the Sun but holds {', '.join(pd.phase.chariot)} there."
            return f"{self.name[k]} is {arc(dist)} from the Sun."
        if tok == "rejoices_hemisphere" and pd.sect:
            return f"{self.name[k]} is {'above' if pd.sect.above else 'below'} the horizon in a {chart} chart, where a {pd.sect.sect} planet likes to be."
        if tok == "rejoices_sign" and pd.sect:
            return f"{self.name[k]} is in {SIGNS[sign_index(self.lon[k])]}, a sign that suits a {pd.sect.sect} planet."
        if tok == "proper_face":
            return (
                f"{self.name[k]} in {SIGNS[sign_index(self.lon[k])]} stands to the Sun in {SIGNS[sign_index(self.lon['sun'])]}"
                f" (or the Moon in {SIGNS[sign_index(self.lon['moon'])]}) as its own domicile stands to theirs."
            )
        if tok == "running_in_the_void" and self.r.void_moon:
            v = self.r.void_moon
            nxt = (
                f" (its next exact aspect, a {v.next_aspect}, is {arc(v.moon_travel or 0)} away)"
                if v.next_aspect
                else ""
            )
            return f"The Moon completes no exact aspect with any planet within the next {self.d.configs.void_range if self.d.configs else 30:g}°{nxt}."
        if tok == "busy_by_angle" and pd.busy_by:
            angle = {"asc": "Ascendant", "mc": "Midheaven"}[pd.busy_by]
            return f"{self.name[k]} is in a declining place but aspects the exact {angle} degree closely, which makes it busy."
        if (
            tok in ("retrograde", "additive", "subtractive", "stationary")
            and pd.phase
            and pd.phase.speed_ratio is not None
        ):
            return (
                f"{self.name[k]} moves at {pd.phase.speed_ratio:.2f} times its average daily motion"
                + (" and backwards" if tok == "retrograde" else "")
                + "."
            )
        return ""

    def condition_why(self, c: Any) -> str:
        t, actors = c.target, c.actor.split("+")
        names = " and ".join(self.name[a] for a in actors)
        verb = "bonifies" if c.effect == "bonify" else "maltreats"
        rule = self.d.conditions.get(c.condition)
        kind = rule.kind if rule else ""
        why = ""
        if kind == "overcoming":
            why = f"{names} at {pos(self.lon[actors[0]])} is a {c.aspect} earlier in the zodiac than {self.name[t]} at {pos(self.lon[t])}: on its right, it has the upper hand and {verb} it."
        elif kind in ("sign_aspect", "copresence"):
            why = f"{names} at {pos(self.lon[actors[0]])} is in {'the same sign as' if c.aspect == 'conjunction' else 'a sign-based ' + c.aspect + ' with'} {self.name[t]} at {pos(self.lon[t])}, so it {verb} it."
        elif kind == "adherence":
            why = f"{self.name[t]} at {pos(self.lon[t])} is {arc(c.distance or 0)} from {names} at {pos(self.lon[actors[0]])} and closing on the conjunction."
        elif kind == "degree_aspect" and c.aspect in ASPECT_ANGLE and rule:
            a = actors[0]
            if rule.direction == "backward":
                ray = (self.lon[a] - ASPECT_ANGLE[c.aspect]) % 360
                why = f"{names} at {pos(self.lon[a])} casts its {c.aspect} ray back to {pos(ray)}; {self.name[t]} at {pos(self.lon[t])} is {arc(c.distance or 0)} from it"
            else:
                why = f"{self.name[t]} at {pos(self.lon[t])} is {arc(c.distance or 0)} from an exact {c.aspect} with {names} at {pos(self.lon[a])}"
            why += " and closing." if c.applying else " and moving apart."
        elif kind == "enclosure":
            why = f"The nearest body or ray on each side of {self.name[t]} belongs to {names}, with nothing between."
        elif kind == "containment":
            why = f"{names} casts its rays by sign onto both signs either side of {self.name[t]}'s, and no other planet sees {self.name[t]}."
        elif kind == "counteraction":
            why = f"{self.name[t]} depends on its domicile lord {names}, which is in the {c.aspect.split()[-1]}{'th' if c.aspect.split()[-1].isdigit() else ''} place."
        for a in actors:
            of = a in self.members
            goes = (c.effect == "maltreat") != of
            why += f" {self.name[a]} is {'of' if of else 'contrary to'} the sect, so its part {'goes further' if goes else 'is moderated'}."
        if c.reception:
            why += " Reception: one is in the other's domicile, which softens a maltreatment and strengthens a bonification."
        return why.strip()

    # ── sections ──
    def planets(self) -> list[dict[str, Any]]:
        out = []
        for pd in self.r.planets:
            k = pd.key
            judged = self.r.testimony.get(k)
            tokens = []
            for tok in judged.tokens if judged else []:
                if tok in SKIP:
                    continue
                tone = "good" if judged and tok in judged.good else "bad" if judged and tok in judged.bad else ""
                tokens.append(
                    {
                        "token": tok,
                        "label": self.label(tok),
                        "tone": tone,
                        "why": self.token_why(k, tok),
                        "term": self.term(tok),
                    }
                )
            conds = [
                {
                    "condition": c.condition, "label": self.label(c.condition), "effect": c.effect, "actor": c.actor,
                    "actors": [self.name[a] for a in c.actor.split("+")], "aspect": c.aspect, "distance": c.distance,
                    "applying": c.applying, "reception": c.reception, "why": self.condition_why(c),
                    "term": self.term(c.condition), "cite": c.cite,
                }
                for c in self.r.conditions
                if c.target == k
            ]  # fmt: skip
            out.append({
                "key": k, "name": self.name[k], "lon": self.lon[k], "pos": pos(self.lon[k]), "place": pd.place.place,
                "sect": pd.sect.sect if pd.sect else "", "tokens": tokens, "conditions": conds,
                "good": judged.good if judged else [], "bad": judged.bad if judged else [],
            })  # fmt: skip
        return out

    def lots(self) -> list[dict[str, Any]]:
        out = []
        for name, lot in self.r.lots.items():
            topic = self.r.lot_topics[name]
            judged = self.r.lot_testimony.get(name)

            def nm(x: str) -> str:
                if x.startswith("lot:"):
                    other = self.r.lots.get(x[4:])
                    return f"Lot of {x[4:].title()}" + (f" ({pos(other.lon)})" if other else "")
                if x in self.lon:
                    return f"{self.name[x]} ({pos(self.lon[x])})"
                return x.replace(":", " ").replace("_", " ")

            a, b = lot.points
            start = "the Ascendant" if lot.project_from == "asc" else nm(lot.project_from)
            why = f"From {nm(a)} to {nm(b)}{' (reversed by night)' if lot.reversed else ''}, then the same distance from {start}"
            why += " — the pack's fallback formula" if lot.fallback else ""
            why += f": {pos(lot.lon)}."
            self.term("lot")
            out.append({
                "name": name, "title": name.replace("_", " ").title(), "lon": lot.lon, "pos": pos(lot.lon), "place": lot.place,
                "lord": lot.lord, "lord_name": self.name.get(lot.lord, ""), "lord_place": topic.lord_place, "why": why,
                "good": [CHECKLIST[x] for x in (judged.good if judged else [])],
                "bad": [CHECKLIST[x] for x in (judged.bad if judged else [])], "cite": lot.cite, "term": "lots" if "lots" in self.glossary else "",
            })  # fmt: skip
        return out

    def places(self) -> list[dict[str, Any]]:
        out = []
        for t in self.r.places:
            n = int(t.name.split()[-1])
            good = self.d.places is not None and n in self.d.places.good
            bad = self.d.places is not None and n in self.d.places.bad
            rising = SIGNS[sign_index(self.asc)]
            verdict = (
                "it sees the rising sign: a good place"
                if good
                else "it is in aversion to the rising sign: a bad place"
                if bad
                else ""
            )
            lord = (
                f" Its lord {self.name.get(t.lord, '')} is in the {ordinal(t.lord_place)} place."
                if t.lord and t.lord_place
                else ""
            )
            out.append({
                "place": n, "sign": t.sign, "good": good, "bad": bad, "lord": t.lord,
                "why": f"{t.sign} is the {ordinal(n)} place from {rising} rising{'; ' + verdict if verdict else ''}.{lord}",
                "term": self.term("good_place" if good else "bad_place") if (good or bad) else "",
            })  # fmt: skip
        return out

    # ── further techniques the pack switched on: the angles' degrees, assembly, the void Moon, Mercury's role ──
    def _aspect_to(self, text: str) -> str:
        """ "trine venus" → "trine to Venus"."""
        aspect, _, planet = text.partition(" ")
        return f"{aspect} to {self.name.get(planet, planet.title())}" if planet else text

    def further(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        mc = self.r.angle_places.get("mc")
        if mc:
            ic = self.r.angle_places.get("ic", 0)
            moved = mc != 10
            out.append({
                "key": "midheaven_degree", "title": "The Midheaven degree", "term": self.term("midheaven_degree"),
                "text": f"The Midheaven degree falls in the {ordinal(mc)} place and the IC degree in the {ordinal(ic)}"
                + (": their topics of career and home are added to those places." if moved else ", as usual."),
            })  # fmt: skip
        for a in self.r.assemblies:
            out.append({
                "key": f"assembly:{a.a}:{a.b}", "title": f"{self.name[a.a]} assembling with {self.name[a.b]}",
                "term": self.term("assembly"),
                "text": f"{self.name[a.a]} is {arc(a.distance)} from a conjunction with {self.name[a.b]} and closing.",
            })  # fmt: skip
        v = self.r.void_moon
        if v is not None:
            out.append({
                "key": "void_moon", "title": "The Moon running in the void" if v.void else "The Moon's next aspect",
                "term": self.term("running_in_the_void"),
                "text": (f"The Moon completes no exact aspect within the next {self.d.configs.void_range if self.d.configs else 30:g}°."
                         if v.void else f"The Moon's next exact aspect is a {self._aspect_to(v.next_aspect)}, {arc(v.moon_travel or 0)} ahead: it isn't void."),
            })  # fmt: skip
        m = self.r.mercury
        if m is not None:
            links = (
                "; ".join(f"{self.name[x['planet']]} ({x['how']})" for x in m.associations) or "no close associations"
            )
            out.append({
                "key": "mercury_role", "title": f"Mercury acts as a {m.role} planet" if m.role in ("benefic", "malefic") else f"Mercury's role: {m.role}",
                "term": self.term("mercury_role"),
                "text": f"Mercury takes on the role of what it is closely joined to: {links}.",
            })  # fmt: skip
        return out

    # ── life topics: the planet, the place and its ruler, the lot (the rule of three) ──
    def _lean(self, good: int, bad: int) -> str:
        return "good" if good > bad else "bad" if bad > good else "mixed"

    def _planet_summary(self, k: str) -> tuple[list[str], list[str]]:
        judged = self.r.testimony.get(k)
        if not judged:
            return [], []
        return [self.label(x).lower() for x in judged.good], [self.label(x).lower() for x in judged.bad]

    def topics(self) -> list[dict[str, Any]]:
        out = []
        for name, t in self.d.topics.items():
            comps: list[dict[str, Any]] = []
            for k in t.significators:
                good, bad = self._planet_summary(k)
                pd = self.r.planet(k)
                conds = [c for c in self.r.conditions if c.target == k]
                helped = sorted({self.name[a] for c in conds if c.effect == "bonify" for a in c.actor.split("+")})
                hurt = sorted({self.name[a] for c in conds if c.effect == "maltreat" for a in c.actor.split("+")})
                why = f"{self.name[k]} is in {SIGNS[sign_index(self.lon[k])]} in the {ordinal(pd.place.place)} place"
                why += f"; bonified by {', '.join(helped)}" if helped else ""
                why += f"; maltreated by {', '.join(hurt)}" if hurt else ""
                comps.append({
                    "kind": "planet", "ref": f"planet:{k}", "title": f"{self.name[k]}, its planet", "good": good, "bad": bad,
                    "lean": self._lean(len(good), len(bad)), "why": why + ".",
                })  # fmt: skip
            via = {n: "" for n in t.places}  # place → the degree that brings it into the topic ("" = its own place)
            for d in t.degrees:
                n = self.r.angle_places.get(d)
                if n and n not in via:
                    via[n] = d
            for n, degree in via.items():
                topic = self.r.places[n - 1]
                inside = [k for k in SEVEN if self.r.planet(k).place.place == n]
                good, bad = [], []
                if self.d.places and n in self.d.places.good:
                    good.append("a good place")
                if self.d.places and n in self.d.places.bad:
                    bad.append("a bad place")
                for k in inside:
                    (good if k in self.sect.benefics else bad if k in self.sect.malefics else []).append(
                        f"{self.name[k]} in it"
                    )
                lord_good, lord_bad = self._planet_summary(topic.lord) if topic.lord else ([], [])
                lord_lean = self._lean(len(lord_good), len(lord_bad))
                (good if lord_lean == "good" else bad if lord_lean == "bad" else []).append(
                    f"its ruler {self.name.get(topic.lord, '')} {'well' if lord_lean == 'good' else 'poorly' if lord_lean == 'bad' else 'evenly'} placed"
                )
                why = f"The {ordinal(n)} place is {topic.sign}" + (
                    f", holding {', '.join(self.name[k] for k in inside)}" if inside else ", with no planet in it"
                )
                why += (
                    f"; its ruler {self.name.get(topic.lord, '')} is in the {ordinal(topic.lord_place or 0)} place"
                    if topic.lord
                    else ""
                )
                title = f"The {ordinal(n)} place and its ruler"
                if degree:
                    angle = {"mc": "Midheaven", "ic": "IC"}[degree]
                    title = f"The {angle} degree's place (the {ordinal(n)}) and its ruler"
                    why = f"The {angle} degree falls in the {ordinal(n)} place and brings its topics there. " + why
                comps.append({
                    "kind": "place", "ref": f"place:{n}", "title": title, "good": good, "bad": bad,
                    "lean": self._lean(len(good), len(bad)), "why": why + ".",
                })  # fmt: skip
            for lot in t.lots:
                if lot not in self.r.lots:
                    continue
                judged = self.r.lot_testimony.get(lot)
                good = [CHECKLIST[x] for x in (judged.good if judged else [])]
                bad = [CHECKLIST[x] for x in (judged.bad if judged else [])]
                L = self.r.lots[lot]
                comps.append({
                    "kind": "lot", "ref": f"lot:{lot}", "title": f"Lot of {lot.replace('_', ' ').title()}", "good": good, "bad": bad,
                    "lean": self._lean(len(good), len(bad)),
                    "why": f"The Lot of {lot.replace('_', ' ').title()} is at {pos(L.lon)} in the {ordinal(L.place)} place" + (f", ruled by {self.name.get(L.lord, '')}" if L.lord else "") + ".",
                })  # fmt: skip
            ups = sum(1 for c in comps if c["lean"] == "good")
            downs = sum(1 for c in comps if c["lean"] == "bad")
            # the rule of three: unanimous testimonies make the outcome clear; a majority makes it lean
            if ups and not downs:
                verdict, tone = "favourable", "favourable"
            elif downs and not ups:
                verdict, tone = "difficult", "difficult"
            elif ups > downs:
                verdict, tone = "leans favourable", "favourable"
            elif downs > ups:
                verdict, tone = "leans difficult", "difficult"
            else:
                verdict, tone = "mixed", "mixed"
            agree = f"{ups} of {len(comps)} testimonies lean well and {downs} poorly"
            out.append({
                "name": name, "label": t.label, "cite": t.cite, "components": comps, "verdict": verdict, "tone": tone,
                "why": f"{agree}: by the rule of three, the more of them agree, the surer the outcome.",
            })  # fmt: skip
        return out

    def sect_part(self) -> dict[str, Any]:
        sun = self.lon["sun"]
        chart = "day" if self.r.day else "night"
        spectrum = []
        if len(self.sect.benefics) == 2 and len(self.sect.malefics) == 2:
            ben_of = next((b for b in self.sect.benefics if b in self.members), "")
            ben_contra = next((b for b in self.sect.benefics if b not in self.members), "")
            mal_of = next((m for m in self.sect.malefics if m in self.members), "")
            mal_contra = next((m for m in self.sect.malefics if m not in self.members), "")
            roles = [
                (ben_of, "most helpful"),
                (ben_contra, "helpful, restrained"),
                (mal_of, "difficult, restrained"),
                (mal_contra, "most difficult"),
            ]
            spectrum = [
                {"key": k, "name": self.name[k], "role": role, "of_sect": k in self.members,
                 "why": f"{self.name[k]} is a {'benefic' if k in self.sect.benefics else 'malefic'} {'of' if k in self.members else 'contrary to'} the sect in this {chart} chart.",
                 "term": self.term("of_sect" if k in self.members else "contrary_to_sect")}
                for k, role in roles if k
            ]  # fmt: skip
        return {
            "day": self.r.day, "light": "sun" if self.r.day else "moon", "spectrum": spectrum, "term": self.term("day"),
            "why": f"The Sun at {pos(sun)} is {'above' if self.r.day else 'below'} the horizon (the Ascendant is {pos(self.asc)}), so this is a {chart} chart.",
        }  # fmt: skip


CITE_KEYS = frozenset({"cite", "cites", "profection_cite", "releasing_cite"})


def without_citations(study: dict[str, Any]) -> dict[str, Any]:
    """The study with every page reference taken out (rule cites, glossary pages): citations are off by default."""

    def strip(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in CITE_KEYS}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o

    out: dict[str, Any] = strip(study)
    if isinstance(out.get("glossary"), dict):
        out["glossary"] = {k: {f: v for f, v in e.items() if f != "pages"} for k, e in out["glossary"].items()}
    return out


def configurations_table(natal: ChartModel) -> list[dict[str, Any]]:
    """Every pair among the seven planets and the angles: the configuration by whole sign (None = aversion), how far
    from exact by degree, applying or not, and who overcomes whom."""
    from astrolog_skills.analysis.doctrine.configurations import closest, is_applying, overcoming, sign_aspect

    keys = [*SEVEN, "asc", "mc"]
    lon = {k: natal.point(k).lon for k in SEVEN} | {k: natal.angles[k] for k in ("asc", "mc")}
    speed = {k: natal.point(k).speed for k in SEVEN} | {"asc": 0.0, "mc": 0.0}
    out = []
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            aspect = sign_aspect(lon[a], lon[b])
            row: dict[str, Any] = {"a": a, "b": b, "aspect": aspect}
            if aspect is not None:
                d = closest(lon[a], lon[b], aspect)
                row["distance"] = round(abs(d), 4)
                row["applying"] = is_applying(d, speed[a], speed[b]) if d else None
                row["overcomes"] = a if overcoming(lon[a], lon[b]) else b if overcoming(lon[b], lon[a]) else ""
            out.append(row)
    return out


def build_study(
    natal: ChartModel,
    doctrine: Doctrine,
    glossary: dict[str, dict[str, str]],
    later: ChartModel | None = None,
    years: int = 90,
) -> dict[str, Any]:
    """Everything the study views show, as plain data (JSON-ready)."""
    result = analyse(natal, doctrine, later)
    s = _Study(natal, doctrine, result, glossary)
    birth = date.fromisoformat(str(natal.moment.get("date", "2000-01-01")))
    utc_text = str(natal.moment.get("utc") or f"{birth.isoformat()}T00:00:00")
    birth_utc = datetime.fromisoformat(utc_text).replace(tzinfo=None)
    end = anniversary(birth, years)
    out: dict[str, Any] = {
        "birth": birth.isoformat(),
        "end": end.isoformat(),
        "rising": SIGNS[sign_index(s.asc)],
        "asc": s.asc,
        "sect": s.sect_part(),
        "planets": s.planets(),
        "lots": s.lots(),
        "places": s.places(),
        "topics": s.topics(),
        "configurations": configurations_table(natal),
        "further": s.further(),
        "life": {"title": "The life as a whole"},
        "cites": result.cites,
        "notes": result.notes,
    }
    if doctrine.profections:
        out["profections"] = [
            profection(natal, doctrine, birth, age, start).to_dict()
            for age in range(years + 1)
            for start in doctrine.profections.starts
        ]
        out["profection_cite"] = doctrine.profections.cite
        s.term("profection")
    if doctrine.releasing and len(doctrine.releasing.periods) == 12:
        until = datetime.combine(end, datetime.min.time())
        out["releasing"] = {}
        for lot in doctrine.releasing.lots:
            try:
                r = releaser(natal, doctrine, birth_utc, lot)
            except AstroError:
                continue
            out["releasing"][lot] = {
                "shifted": r.shifted,
                "periods": [p.to_dict() for p in r.periods(until, 2)],
            }
        out["releasing_cite"] = doctrine.releasing.cite
        for t in ("releasing", "peak", "loosing", "completion", "triad"):
            s.term(t)
    if doctrine.dignities and doctrine.dignities.triplicity:
        try:
            out["lords"] = sect_light_lords(natal, doctrine, float(natal.moment.get("lat", 0.0))).to_dict()
            s.term("lords")
        except AstroError:
            pass
    out["glossary"] = {k: glossary[k] for k in sorted(s.used)}
    assign_keys(out)
    return out


# ── reading notes: one stable key per study item, so a written reading can speak to each one ──

REQUIRED_EXACT = {"sect", "life", "lot:fortune", "lot:spirit", "place:1", "place:10", "lords"}
REQUIRED_PREFIX = ("planet:", "condition:", "topic:")


def assign_keys(study: dict[str, Any]) -> None:
    """Give every item a `note_key` (and a plain `note_label` for the notes workflow)."""
    study["sect"]["note_key"], study["sect"]["note_label"] = "sect", "The chart's sect"
    study["life"]["note_key"], study["life"]["note_label"] = "life", "The life as a whole: an overview of the reading"
    for t in study.get("topics", []):
        t["note_key"], t["note_label"] = f"topic:{t['name']}", f"{t['label']} — the topic's reading"
    for p in study["planets"]:
        p["note_key"], p["note_label"] = f"planet:{p['key']}", f"{p['name']} as a whole"
        for t in p["tokens"]:
            t["note_key"], t["note_label"] = f"finding:{p['key']}:{t['token']}", f"{p['name']}: {t['label'].lower()}"
        for c in p["conditions"]:
            c["note_key"] = f"condition:{p['key']}:{c['condition']}:{c['actor']}"
            verb = "bonified" if c["effect"] == "bonify" else "maltreated"
            c["note_label"] = f"{p['name']} {verb} by {' and '.join(c['actors'])} ({c['label'].lower()})"
    for lot in study["lots"]:
        lot["note_key"], lot["note_label"] = f"lot:{lot['name']}", f"Lot of {lot['title']}"
    for pl in study["places"]:
        pl["note_key"], pl["note_label"] = f"place:{pl['place']}", f"The {ordinal(pl['place'])} place and its ruler"
    if "lords" in study:
        study["lords"]["note_key"], study["lords"]["note_label"] = "lords", "The sect light's triplicity lords"
    for y in study.get("profections", []):
        y["note_key"] = f"profection:{y['start']}:{y['age']}"
        start = {"asc": "", "sect_light": " from the sect light", "contrary_light": " from the other light"}.get(
            y["start"], f" from {y['start']}"
        )
        y["note_label"] = f"Age {y['age']}{start}: {ordinal(y['place'])} place {y['sign']}, lord {y['lord'].title()}"
    for lot, rel in study.get("releasing", {}).items():
        for r in rel["periods"]:
            r["note_key"] = f"releasing:{lot}:{r['level']}:{r['begins']}"
            r["note_label"] = f"{lot.title()} L{r['level']} {r['sign']} {r['begins']} to {r['ends']}"


def study_items(study: dict[str, Any]) -> list[dict[str, Any]]:
    """Every keyed item in the study."""
    items: list[dict[str, Any]] = [study["sect"], study["life"], *study.get("topics", [])]
    for p in study["planets"]:
        items += [p, *p["tokens"], *p["conditions"]]
    items += study["lots"] + study["places"]
    if "lords" in study:
        items.append(study["lords"])
    items += study.get("profections", [])
    for rel in study.get("releasing", {}).values():
        items += rel["periods"]
    return items


def attach_notes(study: dict[str, Any], notes: dict[str, str]) -> int:
    """Put the reading's note on every item that has one; returns how many were attached."""
    n = 0
    for item in study_items(study):
        text = notes.get(item.get("note_key", ""))
        if text:
            item["note"] = text
            n += 1
    return n


FORECAST_MONTHS = 24


def _months_after(day: str, months: int) -> str:
    y, m, d = int(day[:4]), int(day[5:7]), int(day[8:10])
    y, m = y + (m - 1 + months) // 12, (m - 1 + months) % 12 + 1
    return f"{y:04d}-{m:02d}-{min(d, 28):02d}"


def study_contacts(study: dict[str, Any], on: str | None = None) -> list[dict[str, Any]]:
    """The keys a reading can write notes for: everything natal, every chapter of the life, and — the forecast — the
    profection years and releasing subperiods running on `on` or starting within the next two years."""
    out = []
    horizon = _months_after(on, FORECAST_MONTHS) if on else None
    for item in study_items(study):
        key = item.get("note_key", "")
        timed = key.startswith(("profection:", "releasing:"))
        chapter = key.startswith("releasing:") and item.get("level") == 1  # the chapters of the life: all of them
        ahead = bool(on and horizon and item.get("ends", "") > on and item.get("begins", "9999") < horizon)
        if timed and not chapter and not ahead:
            continue
        required = key in REQUIRED_EXACT or key.startswith(REQUIRED_PREFIX)
        side_year = key.startswith("profection:") and not key.startswith("profection:asc:")
        out.append({
            "key": key, "kind": "study", "label": item.get("note_label", key),
            "required": required or (timed and not side_year), "forecast": timed and not chapter,
        })  # fmt: skip
    return out
