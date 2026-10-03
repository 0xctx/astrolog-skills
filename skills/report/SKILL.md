---
name: report
description: Write astrology readings and reports with astrolog-skills in a chosen tradition — psychological/modern natal readings, vibrational (harmonic) readings, traditional readings from a pack built on the user's own books (e.g. Hellenistic: sect, condition, lots, rulers, time lords), with page citations when asked, or a blend — grounded in exact chart data and the tradition pack's own method and meanings, saved as Markdown and woven into the interactive chart. Use when the user asks for an interpretation, reading, report, "what does my chart say", a written analysis in a style or tradition, or to combine traditions.
---

# Written readings

A reading follows the tradition pack's **process.md** (method, structure, rules) and **meanings.md** (what things mean),
applied to the toolkit's exact data. Packs: `astro --json packs list` (the profile's pack is the default).

## Steps

1. **Chart.** Use a saved chart (`--chart NAME`) or birth data; if new, save it first with the `chart` skill.
2. **Data.** `astro --json report-data --chart NAME [--pack P] [--pack Q]` — repeat `--pack` to blend traditions.
   It returns the chart (positions, houses, speeds), balance, and per pack: aspects with orbs/strength/applying,
   natal patterns, strongest harmonics (`strongest_harmonics`: midpoint structures in σ above a typical chart in that harmonic by the new
   method, the old method and two-planet aspects alongside, and the strongest structures each at its own vibration —
   see the harmonics skill), the pack's file paths, and `export_path`.
3. **Read the pack files** at the returned paths: `process.md` fully, `meanings.md` fully, and `REVIEW.md` if present
   (open questions — don't present them as settled). Follow process.md's steps and writing rules.
4. **Write** the reading in Markdown:
   - Title with name, date, time, place, tradition(s); a one-paragraph overview.
   - Headings following process.md; every claim tied to data ("Moon 14°31′ Sagittarius, 6th house",
     "Mercury–Saturn conjunction, 1°03′ applying", "H17: Sun on the Venus/Pluto midpoint, 0.97").
   - Use only meanings from meanings.md; if something isn't covered, say so rather than inventing doctrine.
   - Blends: one tradition's process shapes the reading; the other's findings are introduced by name.
5. **Hover notes for the HTML chart.** After the reading, write short snippets of it for the contacts it discusses, so
   the interactive chart can show them when a row is hovered:
   - `astro --json notes keys --chart NAME --pack P --harmonics H[,H…]` — every aspect and midpoint contact at the
     harmonics the user will export (default 1), with its `key`, a plain `label`, orb and strength, and the file `path`
     (also `notes_path` in report-data).
   - Write that file: `{"chart": NAME, "pack": P, "contacts": {key: note}}`. A note for every **tight** contact
     (strength ≥ 0.5) — two-planet aspects *and* midpoints — among bodies the pack's meanings.md defines, at each
     exported harmonic. Midpoint notes say what the three bodies do together (the body on the midpoint joins what the
     pair share), in plain words. Looser contacts can go without.
   - Each note: 1–2 plain sentences (≤ ~50 words) in the reading's voice, saying what it means *for this person* in
     the context of the whole chart. No orbs, degrees, harmonic numbers or jargon; consistent with the reading.
   - `astro notes check --chart NAME --pack P --harmonics …` → fix unknown keys; it lists tight aspects still missing
     (skipping bodies the pack's meanings.md doesn't define — leave those without a note rather than invent one).
   - Notes show only in exports made with `--interp`; rows without a note show just the contact's title.
6. **Save** the reading to `export_path` (create the `exports` folder if needed) and tell the user the path. Offer the interactive chart with the notes
   (`astro export html --chart NAME --pack P --harmonics … --interp`), the colour chart
   (`! astro view --chart NAME --show chart,aspects`) and, for vibrational readings, the harmonic view
   (`! astro view --chart NAME --harmonic N --pack vibrational --show chart,patterns`).

## Packs built from sources (doctrine, topics and time lords, e.g. `--pack hellenistic`)

When `report-data` returns `study`, `timing` and `sources`, write a **full traditional reading**: the life as a whole,
then every topic, then the chapters, then the present — with the techniques as evidence, not as the structure.

**Voice — the most important rule.** Write it like a good astrologer talking to the person, not like a textbook:
- **Plain language in the main text.** Talk about work, money, love, family, health, friends, energy, timing and
  decisions. No technical terms in the body of a section — no "bonified", "maltreated", "malefic", "sect", "lord",
  "place", "lot", "profection", "releasing", "triplicity". Translate: "a strong supporter in your chart", "your
  career", "this year's focus", "a peak period for your work". The technique goes in one short line at the end of the
  section: *How the chart shows this:* … — that is the only place for jargon. The popovers carry the rest.
- **Citations are off by default.** No page numbers anywhere in the reading or the notes unless `report-data` says
  `"citations": true` (the user ran `astro config set readings.citations true`, or passed `--cite`) or the user asks
  for them in this conversation. Then add printed pages "(p. 488)" — or for notes and transcripts the `where` that
  `sources search` gives, "(Course, Lesson 3, 41:10)" — to the *How the chart shows this* lines, and
  re-run `report-data` and `export html` with `astro --cite …` so the page shows them too.
- **Practical and actionable.** For each area: what it looks like in daily life; the strengths to lean on; the
  pressures and how to work with them; two or three concrete suggestions that follow from what the pack's meanings
  say (application, not new doctrine). Tendencies, not fate. No medical, legal or financial directives — point to
  professionals for those.
- **Predictive.** Always include **The next two years**: the theme of this year and next (with dates), the windows
  ahead for work/direction and for body/circumstance (with dates), turning points and peaks, the dates when the
  year's ruling planet is activated by transit — what each is likely to bring and how to use it. Be specific about
  timing; say how confident the chart is (testimonies agreeing or not).

1. `astro --json report-data --chart NAME --pack P [--on DATE] [--transits-days 365]`. `study.topics` gives each life
   topic with its three testimonies (its planet; its place and that place's ruler; its lot and the lot's ruler), how
   each leans and why, and a verdict by the rule of three; `study.planets`, `lots`, `places`, `sect` hold the findings
   with reasons; `study.releasing` holds every chapter (level 1) of the life; `timing` the date's time lords;
   `study.glossary` the pack's definitions; `sources` how to search the books.
2. Read the pack's `process.md`, `meanings.md` and `REVIEW.md`. Use `study` for every fact; never recompute.
3. **Structure of the reading** (3,000–5,000 words for a full natal reading):
   - **Overview** — the life in a few plain paragraphs: who this person is, what they are here to do, where life
     comes easily and where it pushes back, and the shape of the life's chapters. This is what the page opens on.
   - **Character and direction** — the rising sign, its ruler's place and condition, Mercury and the Sun, Spirit.
   - **Each topic in `study.topics`** (work and reputation, money, partnership, parents, siblings, children, friends,
     travel and belief, body and health, enemies and hardship): weigh its three testimonies together. Say what each
     shows, where they agree or pull apart, and what that means *in life* — concrete, specific, in plain words. Name
     the bonifications and maltreatments that decide it, and the source's principle behind each judgement.
   - **The chapters of the life** — every level-1 releasing period from Spirit (direction, career) and from Fortune
     (body, circumstance), birth to old age: the chapter's sign, the planets in or squaring it, its ruler, peaks and the
     loosing of the bond, and what kind of chapter it is. Tie chapters together into a story.
   - **The next two years** (from the date asked about, default today) — see Voice above; every window in
     `astro --json notes keys … --on DATE` marked `forecast`, in order, with dates and guidance.
   - **Open questions** — where the reading rests on a REVIEW.md choice.
4. **Go to the source for depth** (when `report-data` lists `sources`; the built-in sample Hellenistic pack has none —
   then read from the pack's `meanings.md` alone). For every topic and chapter, search the pack's books
   (`astro --json sources search P "…"`, then `astro --json sources page P N`) and build on what the source teaches —
   its delineations, its worked examples, its principles (pages only when citations are on). Paraphrase; quote at
   most a short phrase (≤ 25 words) when the wording matters. Where the source is silent, say so. If the source discusses
   this very chart, use it.
5. **Notes for the chart.** `astro --json notes keys --chart NAME --pack P --on DATE` lists the keys; `required` ones
   must have a note, **in the plain, practical voice**: `life` (the overview, 4–6 sentences), each `topic:…` (3–4
   sentences: what it means in daily life and what to do with it), each chapter `releasing:…:1:…` (2–3 sentences:
   what that stretch of life is about), each forecast window (`forecast: true` — the year themes and the windows of
   the next two years: what it is likely to bring and how to use it), the sect, each `planet:…`, each `condition:…`,
   Fortune and Spirit, the 1st and 10th places, and the lords. Write the file as `{"chart": NAME, "pack": P, "on": "YYYY-MM-DD", "contacts":
   {key: note}}` — `on` makes the page's timeline open on that date. Plain language, for this person, no degrees,
   page numbers only when citations are on. `astro notes check …` until `missing_study` is empty.
6. Save the reading to `export_path`, then `astro export html --chart NAME --pack P --harmonic 1`: the page opens on
   **Life** (overview, topics with their verdicts and testimonies, chapters), with the full text in **Reading** and the
   techniques in the tabs behind; every popover leads with the reading. Terminal:
   `! astro view --chart NAME --pack P --show life,doctrine,timelords`.

## Always

- Tendencies and potentials, not fate. No medical, legal, financial or death predictions.
- If the birth time is uncertain (rating below A), say which conclusions depend on it (houses, angles, high harmonics).
- Match the user's requested length and tone; default to ~800–1,500 words for a full natal reading.
