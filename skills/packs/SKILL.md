---
name: packs
description: Tradition packs in astrolog-skills — list, inspect, copy and build the per-tradition rules (aspects, orbs, harmonics, patterns, traditional doctrine) and meaning files, including building a pack from the user's own books. Use when the user asks which schools/traditions/methods are available, what rules a tradition uses, wants to change orbs or aspect sets, wants their own version of a tradition, or wants rules drafted from a book or text they have.
---

# Tradition packs

A pack is one folder per tradition, e.g. `vibrational` (vibrational astrology) or `psychological`:

| File | Read by | Holds |
|---|---|---|
| `method.toml` | the toolkit | aspect set, orbs (`fixed` table, or `harmonic`: 16°/harmonic), harmonic range, pattern rules, pair weights |
| `meanings.md` | you (Claude) | what planets, aspects, harmonics and patterns mean in this tradition |
| `process.md` | you (Claude) | how to read a chart in this tradition |
| `sources.toml` | both | citations for the rules and meanings |
| `REVIEW.md` | the user | open questions (source typos, assumptions, things not computed yet) |

The user's profile names its pack (`astro profile show` → `pack`). Aspect lists, pattern scores and chart views all use
that pack's `method.toml`, so what the user sees always matches the rules you interpret with.

## Commands (read `--json` yourself)

- `astro --json packs list` — packs, which one is active, built-in vs the user's own.
- `astro --json packs show [NAME]` — orbs per aspect, harmonic range, pattern rules, which files exist, sources.
- `astro --json packs settings NAME [--houses …] [--zodiac …] [--node …] [--points …] [--reset]` — the pack's chart
  settings, the user's saved adjustments and the result; options save adjustments.
- `astro packs copy NAME [--as NEW]` — copies into `~/.astrolog-skills/traditions/`. Same name ⇒ their copy
  replaces the built-in everywhere; a new name ⇒ a separate pack they can select by setting `[links] pack` in a profile.
- `astro --json aspects --chart NAME [--pack P] [--harmonic H]` and `astro --json patterns --chart NAME [--range 1-32]`
  show the rules in action.

## Sources (the pack's private library)

A pack can keep the user's own books and texts in `~/.astrolog-skills/traditions/<pack>/sources/` — private, never
shared or copied into the plugin. Always cite what these commands return: a book's **printed** page (`cite: "p. 488"`)
or a section of notes or a transcript (`cite: "§ 12"`, with its `label` — timestamp, lesson or heading — and `where`,
the form a person can find: "Course, Lesson 3, 41:10").

- `astro --json sources add PACK FILE` — copy the file into the pack and index it. A PDF (or text with form feeds):
  every page, the book's printed page numbers, front/back matter (a scanned PDF without a text layer is refused).
  A scanned PDF is read by OCR first when `ocrmypdf` is installed (otherwise the error gives the install line).
  A web page's address (`https://…`): fetched once and kept privately — HTML as Markdown by its headings, a PDF as a
  book; `sources.toml` records the `url` and `fetched` date (fetch again by adding it again).
  Notes and transcripts (`.md`, `.txt`, `.srt`, `.vtt`): sections by timestamp (with "Lesson N" markers), by
  Markdown heading, or in parts. One file per lesson is fine — the file's title names the lesson; set `title` in
  `sources.toml` to what the user calls it.
- `astro --json sources search PACK "words or phrase" [--limit N] [--source ID]` — ranked passages from every source
  in the pack (or one), each with its `source`, page or section (contents and index pages rank last). Words are all required; `"quoted phrases"`; `--raw` for FTS syntax (OR, NEAR).
- `astro --json sources page PACK REF` — the full text of printed page or section N; for sections also a timestamp
  (`"41:10"`, `"lesson 3, 41:10"`) or words from a heading (`--pdf` for a PDF page number).
- `astro sources render PACK N` — an image of the page (read tables and figures from it; their text is often garbled).
- `astro --json sources list PACK`.

Read only the pages you need (search first); quote briefly with the page number.

## Traditional doctrine sections (method.toml)

A pack can describe a tradition's doctrine as cited data (format and checks: `src/astrolog_skills/analysis/doctrine/rules.py`):

- `[chart]` — the chart settings the tradition uses: `zodiac` ("tropical", "sidereal" + `ayanamsa`), `houses`,
  `node`, `objects`, with a `cite`. Used whenever the pack is; the user adjusts them with `astro packs settings P` or
  per command (`astro --houses …`). Draft it from what the source says about zodiac, houses and which planets.
- `[sect]` — day/night rule, diurnal/nocturnal planets, Mercury's rule, benefics/malefics, `[sect.rejoicing]`.
- `[dignities]` — domicile, exaltation `[sign, degree]`, triplicity `[day, night, participating]`,
  `[dignities.bounds.<scheme>]` as `[[planet, end], …]`, decans, `twelfth_parts = { multiplier = 12 }`.
- `[phase]` — `under_beams`, `weak_within`, `heart`, `heliacal_days`, `visible_beyond`, `chariot`, optional
  `stationary_ratio` / `mean_motion`.
- `[lots.<name>]` — `points` (planets, `lot:x`, `sign:x`, `place:n`, `ruler:place:n`) or `day`/`night`; `reverse` by
  night, `project_from`, `distance = "shortest"`, `fallback = { when = "saturn_under_beams", points = […] }`, named
  versions + `version`, `variants` (notes).
- `[conditions.<name>]` — `kind`: `overcoming` (sign-based, from the right), `sign_aspect` (`side = "right"` optional),
  `copresence`, `degree_aspect` (`orb`, `moon_orb`, `direction = "backward"` for a ray cast back, `applying`),
  `adherence` (the planet applies to a conjunction; `orb`, `moon_orb`), `enclosure` (`rays`, `orb`, `body_orb`; any
  nearer body or ray intervenes), `counteraction` (`maltreat_places`, `bonify_places` for the lord's place), `custom`
  (not computed). `bonify` / `maltreat` list the aspects by which a benefic / malefic acts.
- `[places]` (good, bad, busy, joys).
- `[timing.profections]` (`starts` = asc, sect_light, contrary_light, a planet, `lot:x`, `place:n`; `step_signs`;
  `planets_in_sign`), `[timing.periods]` (`minor_years` per planet), `[timing.sect_light]` (`quality` per angularity,
  `changeover` = minor_years / ascensional_time), `[timing.transits]` (`kinds` = ingress, sign_configurations, exact),
  `[timing.releasing]` (`lots`, `periods`, `year_days`, `levels`, `peaks` = places from Fortune strongest first,
  `loosing_of_bond`, `same_sign_shift`).
- `[scoring]` — `good` / `bad` finding tokens (e.g. `of_sect`, `domicile`, `under_beams`, `bonified`,
  `maltreated_by_contrary_malefic`), `mode = "weights"` + `weights`; `[scoring.lots]` `good` / `bad` checklist tokens
  (`lot_good_place`, `lord_configured`, `lord_maltreated`, …). Without lists the toolkit reports findings, no verdict.

Every section, lot and condition takes `cite = "p. …"` (printed pages) — except in a sample pack marked
`cited = false` at the top of `method.toml`. `astro --json packs check [NAME]` lists
missing citations, broken tables and bad formulas (exit 1 on errors) — run it after every edit.

`astro --json doctrine --chart NAME [--pack P] [--show planets,testimony,conditions,lots,places|all]` applies the rules:
day or night, each planet's sect, dignities (with the lords of its degree), solar phase and place; configurations
(aversion, overcoming, applying); every bonification and maltreatment with its actor, aspect, orb, sect and reception;
each lot with its lord and checklist; each place's lord; and the good and bad testimony per planet. JSON carries every
rule's citation (`cites`). Anything the pack doesn't define is absent.

## Build a pack from sources

When the user wants a pack drafted from their own book or texts. Nothing reaches the live pack until they approve.

If a built-in pack has that name (e.g. `hellenistic`, a sample of the tradition's common doctrine with
`cited = false` and no page citations), the draft starts from its files: keep its structure, check each rule against
the user's sources, give it a `cite` and an evidence claim, change what their sources teach differently (noting it in
`REVIEW.md`), drop rules their sources don't support, and remove `cited = false` when every rule is cited. The
user's applied pack then replaces the built-in one on their computer.

1. **Index** — `astro --json sources add PACK FILE` (once per source).
2. **Outline** — `astro --json packs outline PACK` → chapters and sections with printed page ranges, plus the lists of
   figures and tables. Agree with the user which chapters to cover; plan one pass per chapter (or a few sections).
3. **Draft** — `astro --json packs draft PACK` creates `traditions/PACK/draft/` (copies of the live files, or
   skeletons for a new pack). Edit only the draft.
4. **Each pass** — read only that pass's pages (`sources page`), then write:
   - `method.toml` sections in the documented format (above), each with `cite = "p. …"` (or `"§ …"` for a section);
   - `meanings.md` / `process.md` entries **in your own words** with `(p. …)` or `(§ …)` after each — never copy
     sentences;
   - `evidence.toml` — for every rule, a `[[claim]]` with `rule` (`sect.diurnal`, `lots.fortune`,
     `meanings.md#Heading`), `page` (printed, e.g. `"190"` or `"190-191"`; a section, e.g. `"§ 12"`), `source` when
     the pack has several, and `quote` (5–20 exact words from that page or section that state the rule). It stays
     private, beside the sources.
   - `REVIEW.md` — every variant, disagreement or gap the source leaves open, with pages, phrased as a question. Pick
     the source's own default in `method.toml`; never settle a variant silently. Techniques the user asked for that
     the source doesn't teach go here too.
5. **Tables** — `astro sources render PACK N` for each table page from the outline; transcribe from the image, never
   from the garbled text layer. `packs verify` checks the invariants (bounds cover 30° with each of the five planets
   once, the classical totals, triplicities, decans); re-read the image for anything it flags.
6. **Verify** — `astro --json packs verify PACK` until there are no errors: each quote must be on its cited page
   ("wrong citation: the words are on p. N" means fix the cite), each cited rule needs evidence, no wording copied
   from the source, and the rules parse and pass their checks. Warnings are for you to judge and mention.
7. **Show** — `astro packs diff PACK`; summarise per file what changed and list the REVIEW.md questions.
8. **Apply** — only after the user says yes: `astro --json packs apply PACK --yes` (refused while verify has errors;
   the old files go to `PACK/.history/`). To extend a pack later, start a new draft — it begins from the live files.
   `astro packs discard PACK` throws a draft away.

Then try it: `astro --json doctrine --chart NAME --pack PACK`, and compare a few findings with the cited pages.

### Adding a source to a pack that already exists

When the user adds another book, course or set of notes to a pack ("add this course to my Hellenistic tradition"):

1. `astro --json sources add PACK FILE`, then `astro --json packs outline PACK --source ID` for its chapters or
   lessons. Ask which parts to work through if it is long.
2. `astro --json packs draft PACK` — the draft starts from the live pack (or, before the user has one, from the
   built-in pack of that name).
3. Read the new source pass by pass and **merge, don't rebuild**:
   - a rule it **confirms** — add an evidence claim with `source = "ID"` (and its page or § to the rule's `cite`);
   - something **new** — a lot, a condition, a timing variant, a topic, a delineation, a reading step — add it to
     `method.toml`, `meanings.md` or `process.md` in your own words, cited;
   - a **disagreement** with the current rule — keep the current default, put the new source's version in
     `REVIEW.md` with both citations, and ask the user which to use (a `version`/`variants` entry where the format
     has one). The rule's `cite` names its sources, the chosen one first: `cite = "book p. 525; course § 12"`.
   - `packs verify` checks each claim against the pages its own source is cited for, and reports `backing` (which
     sources' evidence was found per rule) and `several_sources` (rules more than one source supports) — mention
     both when summarising.
4. `packs verify` → `packs diff` → summarise what each source added or changed → apply only on a yes.

**The owner's own edits are kept.** Every apply records what it wrote; lines the owner changed by hand since then
carry into the next draft (`packs draft` says how many). If a draft would change one, `packs diff` marks it
"changes your own edit" and `packs verify` warns — keep the owner's line unless they agree to the change.

Readings then draw on every source: `sources search` looks through all of a pack's sources unless `--source` is
given, and each hit names its source.

## Editing rules

- To change orbs or aspects, copy the pack first, then edit `method.toml` in the copy (explain each change; show the
  before/after orbs with `astro --json packs show NAME`). Never edit files inside the plugin folder.
- A pack can build on another: `extends = "vibrational"` at the top of `method.toml`, then only the changed tables.
- Surface `REVIEW.md` items when they matter (e.g. an assumed weight) rather than presenting assumptions as fact.
- Building a pack from source material (books, notes, transcripts) is coming in a later version.
